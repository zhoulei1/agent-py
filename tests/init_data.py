"""mMARCO 中文评测的共享初始化与数据工具。

职责：
1. 抽离 test_embedding.py / test_hybrid_search.py 里的公共初始化逻辑
   （向量模型、Qdrant 客户端、docx/pdf 片段加载），后续可复用；
2. 把 chinese_collection.tsv（约 3GB / 880 万条）以「流式 + 分批」方式写入 Qdrant，
   避免一次性读入内存，并支持断点续传；
3. 加载 queries / qrels / bm25 run，提供检索与评测指标计算。

入库用法（在项目根目录下执行）：
    python tests/init_data.py --limit 10000   # 先入库前 1 万条做冒烟测试
    python tests/init_data.py                 # 全量入库（默认按 CPU 核数多进程分片并行）
    python tests/init_data.py --workers 1     # 单进程顺序入库（带进度条，适合冒烟/单核）
    中断后再次执行同样的命令即可从断点自动续传（不重复入库）。

说明：
    - 集合 mmarco-hybrid 同时保存 dense 与 sparse 两路向量；
      单查询检测（test_mmarco_dense.py）只取其中的 dense 向量做检索，
      联合检测（test_mmarco_hybrid.py）走 dense + sparse 的 RRF 融合，
      因此 880 万条只需向量化一次，无需建两份集合。
"""

from __future__ import annotations

import argparse
import logging
import math
import os
import sys
from pathlib import Path
from typing import Callable, Iterator

# 让直接 `python tests/xxx.py` 运行时也能 import 项目根目录下的 app 包与同目录模块
sys.path.insert(0, str(Path(__file__).resolve().parent))        # tests/（同目录模块）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 项目根目录（app 包）

from fastembed import SparseTextEmbedding
from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient, models
from qdrant_client.models import Distance, VectorParams
from tqdm import tqdm

from app.rag.vector_store import HybridVectorStore

logger = logging.getLogger(__name__)

# ---------- 路径与常量 ----------
TEST_DIR = Path(__file__).resolve().parent
MMARCO_DIR = Path("D:/gitwork/mmarco")

COLLECTION_FILE = MMARCO_DIR / "chinese_collection.tsv"
QUERIES_DEV_SMALL = MMARCO_DIR / "chinese_queries.dev.small.tsv"
QRELS_DEV_SMALL = MMARCO_DIR / "qrels.dev.small.tsv"
RUN_BM25 = MMARCO_DIR / "run.bm25_chinese-msmarco.txt"

EMBEDDING_MODEL_PATH = "D:/gitwork/bge-small-zh-v1.5"
BM25_MODEL_PATH = "D:/gitwork/bm25"
# bge 的 ONNX 导出文件（onnxruntime 推理，CPU 上比 torch 快；--backend onnx 使用）
ONNX_MODEL_PATH = "D:/gitwork/bge-small-zh/bge-small-zh-v1.5.onnx"
ONNX_TOKENIZER_PATH = "D:/gitwork/bge-small-zh/bge-small-zh-v1.5-tokenizer.json"
QDRANT_URL = "http://localhost:6333"

# 稠密向量后端：torch（sentence-transformers）或 onnx（onnxruntime）
# 实测本机 torch 更快（27 vs 14 条/s），故默认 torch；onnx 保留作备选
BACKEND = "torch"

VECTOR_SIZE = 512
DENSE_VECTOR = "dense"
SPARSE_VECTOR = "sparse"
HYBRID_COLLECTION = "mmarco-hybrid-test"

# ---------- 入库配置 ----------
BATCH_SIZE = 512      # 每批向量化 + 写入条数（太小往返开销大，太大单个 HTTP 负载过重）
FLUSH_EVERY = 100     # 每写这么多批，强制 wait=True 同步一次并落盘断点
CHECKPOINT_FILE = TEST_DIR / ".mmarco_ingest_checkpoint"  # 记录已入库行号，用于断点续传


# ---------- 模型 / 客户端 / 向量库（抽离自两个测试文件） ----------

def _detect_device(preferred: str | None = None) -> str:
    """选择稠密向量模型的运行设备：显式指定 > 自动检测 CUDA > 回退 CPU。"""
    cuda_available = False
    try:
        import torch
        cuda_available = torch.cuda.is_available()
    except ImportError:
        cuda_available = False
    if preferred:
        if preferred == "cuda" and not cuda_available:
            logger.warning("请求 --device cuda，但 torch 无可用 CUDA，回退到 CPU")
            return "cpu"
        return preferred
    return "cuda" if cuda_available else "cpu"


def build_dense_embeddings(
    model_path: str = EMBEDDING_MODEL_PATH,
    device: str | None = None,
    backend: str = BACKEND,
) -> Embeddings:
    """稠密向量模型（bge-small-zh，L2 归一化 + DOT 即余弦相似度）。

    backend="onnx" 用 onnxruntime 推理（CPU 上比 torch 快），device 忽略；
    backend="torch" 用 sentence-transformers，device 为 None 时自动检测 CUDA/CPU。
    """
    if backend == "onnx":
        from app.rag.embeddings import BgeOnnxEmbeddings
        return BgeOnnxEmbeddings(
            model_path=ONNX_MODEL_PATH,
            tokenizer_path=ONNX_TOKENIZER_PATH,
        )
    device = _detect_device(device)
    return HuggingFaceEmbeddings(
        model_name=model_path,
        model_kwargs={"device": device},
        # GPU 上加大批提升吞吐；CPU 上用中等批避免内存/缓存抖动
        encode_kwargs={"normalize_embeddings": True, "batch_size": 256 if device == "cuda" else 64},
    )


def build_sparse_embeddings(model_path: str = BM25_MODEL_PATH) -> SparseTextEmbedding:
    """稀疏向量模型（BM25，关键词检索，中文不做词干提取）。"""
    return SparseTextEmbedding(
        model_name="Qdrant/bm25",
        specific_model_path=model_path,
        disable_stemmer=True,
    )


def build_client(url: str = QDRANT_URL) -> QdrantClient:
    """Qdrant 客户端（走 HTTP，兼容本地 server 与 client 的版本差）。"""
    return QdrantClient(url=url, api_key=None, check_compatibility=False, timeout=30)


def build_hybrid_store(
    collection_name: str = HYBRID_COLLECTION,
    device: str | None = None,
    backend: str = BACKEND,
) -> HybridVectorStore:
    """构建混合向量库（dense + sparse），供入库与检索共用。backend 选稠密向量后端。"""
    client = build_client()
    store = HybridVectorStore(
        client=client,
        dense_embeddings=build_dense_embeddings(device=device, backend=backend),
        sparse_embeddings=build_sparse_embeddings(),
        collection_name=collection_name,
    )
    if not client.collection_exists(collection_name):
        store._create_collection()
    return store


def load_chunks() -> list[Document]:
    """从 tests/init.docx 与 tests/init.pdf 读取文档并切分（抽离自两个测试文件）。"""
    docs = Docx2txtLoader(str(TEST_DIR / "init.docx")).load()
    docs += PyPDFLoader(str(TEST_DIR / "init.pdf")).load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
    return splitter.split_documents(docs)


# ---------- chinese_collection.tsv 流式入库 ----------

def iter_collection(
    path: Path = COLLECTION_FILE,
    start: int = 0,
    limit: int | None = None,
) -> Iterator[tuple[int, str]]:
    """逐行读取集合文件，产出 (pid, passage_text)，不把整个文件读入内存。

    start：跳过前 start 行（断点续传时从已入库行号继续）；limit：最多产出 limit 条。
    依赖集合文件的 pid 就是 0 起的连续行号（mMARCO 官方格式即如此）。
    """
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i < start:
                continue
            if limit is not None and i >= start + limit:
                return
            pid, text = line.rstrip("\n").split("\t", 1)
            yield int(pid), text


def _resume_line(client: QdrantClient, collection_name: str, checkpoint: Path) -> int:
    """返回应从集合文件第几行继续入库（0 表示从头开始）。

    优先读 checkpoint 里记录的行号；没有则回退到集合内已有点数。
    因为点 id == pid == 0 起的连续行号，已有点数即已入库行数。
    """
    if checkpoint.exists():
        try:
            return int(checkpoint.read_text(encoding="utf-8").strip())
        except ValueError:
            pass
    if client.collection_exists(collection_name):
        return client.count(collection_name).count
    return 0


def _save_checkpoint(checkpoint: Path, line: int) -> None:
    """落盘断点：记录已入库的行号（下次从该行继续）。"""
    checkpoint.write_text(str(line), encoding="utf-8")


def _upsert_hybrid(
    store: HybridVectorStore,
    pids: list[int],
    texts: list[str],
    wait: bool = True,
) -> None:
    """一批文本同时向量化（dense + sparse）后写入集合，点 id 即原始 pid。

    wait=False 时 Qdrant 把写入排队异步落盘（吞吐更高），配合定期 wait=True 同步。
    """
    dense = store.dense.embed_documents(texts)
    sparse = list(store.sparse.embed(texts))
    points = [
        models.PointStruct(
            id=pid,
            vector={
                DENSE_VECTOR: dense[i],
                SPARSE_VECTOR: models.SparseVector(
                    indices=[int(x) for x in sparse[i].indices],
                    values=[float(v) for v in sparse[i].values],
                ),
            },
            payload={"page_content": text, "pid": pid},
        )
        for i, (pid, text) in enumerate(zip(pids, texts))
    ]
    store.client.upsert(collection_name=store.collection_name, points=points, wait=wait)


def ingest_hybrid_collection(
    store: HybridVectorStore,
    path: Path = COLLECTION_FILE,
    batch_size: int = BATCH_SIZE,
    flush_every: int = FLUSH_EVERY,
    limit: int | None = None,
    resume_from: int | None = None,
    checkpoint: Path = CHECKPOINT_FILE,
) -> None:
    """把集合流式分批写入混合集合，支持断点续传。

    - 流式读取 + 分批向量化，不整体载入内存；
    - wait=False 异步写入，每 flush_every 批强制 wait=True 同步一次并落盘断点；
    - 再次运行时自动从 checkpoint / 集合已有点数继续（点 id == pid，重复 upsert 幂等覆盖）。
    """
    client, name = store.client, store.collection_name
    if not client.collection_exists(name):
        store._create_collection()

    start = resume_from if resume_from is not None else _resume_line(client, name, checkpoint)
    if start:
        logger.info("断点续传：跳过前 %d 行（集合内已入库 %d 条）", start, client.count(name).count)

    ingested = start  # 已成功入库的行数（含本次运行）
    pids: list[int] = []
    texts: list[str] = []
    processed = 0  # 本次运行已处理的完整批数

    iterator = tqdm(
        iter_collection(path, start=start, limit=limit),
        desc=f"入库 {name}",
        unit=" 条",
        initial=start,
    )
    for pid, text in iterator:
        pids.append(pid)
        texts.append(text)
        if len(texts) >= batch_size:
            processed += 1
            sync = processed % flush_every == 0
            _upsert_hybrid(store, pids, texts, wait=sync)
            ingested += len(texts)
            if sync:
                _save_checkpoint(checkpoint, ingested)
            pids.clear()
            texts.clear()
    if texts:  # 尾巴：强制同步并落盘最终断点
        _upsert_hybrid(store, pids, texts, wait=True)
        ingested += len(texts)
        _save_checkpoint(checkpoint, ingested)

    checkpoint.unlink(missing_ok=True)  # 全部完成，清除断点
    logger.info("集合 %s 入库完成，共 %d 条", name, client.count(name).count)


# ---------- 多进程分片并行入库 ----------

def count_lines(path: Path = COLLECTION_FILE) -> int:
    """快速统计文件行数（按字节数换行符），用于多进程分片。"""
    n = 0
    tail = b""
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            n += chunk.count(b"\n")
            tail = chunk
    if tail and not tail.endswith(b"\n"):
        n += 1  # 最后一行无换行符
    return n


def _make_shards(total: int, workers: int) -> list[tuple[int, int, int]]:
    """把 total 行均分成 workers 个区间，返回 [(序号, start, end)]。"""
    chunk = math.ceil(total / workers)
    return [
        (k, k * chunk, min((k + 1) * chunk, total))
        for k in range(workers)
        if k * chunk < total
    ]


def _ensure_collection(collection_name: str = HYBRID_COLLECTION) -> None:
    """只创建 Qdrant 集合（不加载模型），主进程在派发 worker 前调用，避免并发建集合冲突。"""
    client = build_client()
    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config={DENSE_VECTOR: VectorParams(size=VECTOR_SIZE, distance=Distance.DOT)},
            sparse_vectors_config={SPARSE_VECTOR: models.SparseVectorParams()},
        )


def _ingest_shard(args: tuple) -> int:
    """多进程 worker：处理集合文件的 [start, end) 行区间并入库，返回 shard 序号。

    每个进程独立加载模型与 Qdrant 客户端；每进程内单线程，靠多进程吃满所有核。
    """
    shard_index, start, end, collection_name, checkpoint, batch_size, flush_every, device, backend = args

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if backend == "onnx":
        # onnxruntime 靠 OMP 线程做 intra-op 并行，限成 1 避免与其它 worker 抢核
        os.environ["OMP_NUM_THREADS"] = "1"
        os.environ["MKL_NUM_THREADS"] = "1"
    elif device == "cpu":
        try:
            import torch
            torch.set_num_threads(1)          # 每进程单线程，避免与其它 worker 抢核
            torch.set_num_interop_threads(1)
        except ImportError:
            pass

    store = build_hybrid_store(collection_name, device=device, backend=backend)

    resume = start
    if checkpoint.exists():
        try:
            c = int(checkpoint.read_text(encoding="utf-8").strip())
            if start <= c < end:
                resume = c
        except ValueError:
            pass
    if resume > start:
        logger.info("shard %d 从第 %d 行续传", shard_index, resume)

    shard_total = end - start
    ingested = resume
    pids: list[int] = []
    texts: list[str] = []
    processed = 0
    for pid, text in iter_collection(COLLECTION_FILE, start=resume, limit=end - resume):
        pids.append(pid)
        texts.append(text)
        if len(texts) >= batch_size:
            processed += 1
            sync = processed % flush_every == 0
            _upsert_hybrid(store, pids, texts, wait=sync)
            ingested += len(texts)
            if sync:
                _save_checkpoint(checkpoint, ingested)
                logger.info("shard %d 已入库 %d / %d 条", shard_index, ingested - start, shard_total)
            pids.clear()
            texts.clear()
    if texts:
        _upsert_hybrid(store, pids, texts, wait=True)
        ingested += len(texts)
        _save_checkpoint(checkpoint, ingested)

    checkpoint.unlink(missing_ok=True)
    logger.info("shard %d 完成，共入库 %d 条", shard_index, ingested - start)
    return shard_index


def ingest_hybrid_collection_parallel(
    workers: int,
    collection_name: str = HYBRID_COLLECTION,
    batch_size: int = BATCH_SIZE,
    flush_every: int = FLUSH_EVERY,
    limit: int | None = None,
    device: str | None = None,
    backend: str = BACKEND,
) -> None:
    """多进程分片并行入库：把集合按行号切成 workers 份，每个进程各入库一份。

    主进程先建好集合再 spawn 子进程；每个子进程独立加载模型、维护各自的断点文件，
    中断后再次执行可续传。适合 CPU 多核场景；backend 选 onnx 时每个进程用 onnxruntime。
    """
    import multiprocessing as mp

    total = count_lines(COLLECTION_FILE)
    if limit is not None:
        total = min(total, limit)

    _ensure_collection(collection_name)

    shards = _make_shards(total, workers)
    specs = [
        (
            k,
            start,
            end,
            collection_name,
            CHECKPOINT_FILE.with_name(f"{CHECKPOINT_FILE.name}.{k}"),
            batch_size,
            flush_every,
            device,
            backend,
        )
        for k, start, end in shards
    ]

    logger.info("开始多进程入库：%d 个 worker，共 %d 行，集合 %s", len(shards), total, collection_name)
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=len(shards)) as pool:
        pool.map(_ingest_shard, specs)

    logger.info("多进程入库完成，集合 %s 共 %d 条", collection_name, build_client().count(collection_name).count)


# ---------- queries / qrels / bm25 run 加载 ----------

def load_queries(path: Path = QUERIES_DEV_SMALL) -> dict[int, str]:
    """加载 chinese_queries.dev.small.tsv -> {qid: query_text}。"""
    queries: dict[int, str] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            qid, text = line.rstrip("\n").split("\t", 1)
            queries[int(qid)] = text
    return queries


def load_qrels(path: Path = QRELS_DEV_SMALL) -> dict[int, set[int]]:
    """加载 qrels.dev.small.tsv -> {qid: {相关 pid 集合}}。"""
    rels: dict[int, set[int]] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            rels.setdefault(int(parts[0]), set()).add(int(parts[2]))
    return rels


def load_bm25_run(path: Path = RUN_BM25, depth: int = 1000) -> dict[int, list[int]]:
    """加载官方 BM25 run -> {qid: 按排名升序的 pid 列表（前 depth 条）}，作基线对比。"""
    run: dict[int, list[tuple[int, int]]] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            qid, pid, rank = line.rstrip("\n").split("\t")
            run.setdefault(int(qid), []).append((int(rank), int(pid)))
    return {qid: [pid for _, pid in sorted(lst)[:depth]] for qid, lst in run.items()}


# ---------- 检索（返回 pid 列表） ----------

def dense_search(store: HybridVectorStore, query: str, k: int = 10) -> list[int]:
    """稠密单路检索：仅用 dense 向量，返回按分数降序的 pid 列表。"""
    vector = store.dense.embed_query(query)
    results = store.client.query_points(
        collection_name=store.collection_name,
        query=vector,
        using=DENSE_VECTOR,
        limit=k,
    )
    return [int(hit.id) for hit in results.points]


def hybrid_search(store: HybridVectorStore, query: str, k: int = 10) -> list[int]:
    """混合检索：dense + sparse 两路 RRF 融合，返回按分数降序的 pid 列表。"""
    return [int(d.metadata["pid"]) for d in store.search(query, k=k)]


# ---------- 评测指标 ----------

def compute_metrics(
    queries: dict[int, str],
    qrels: dict[int, set[int]],
    retrieve: Callable[[int, str], list[int]],
    k: int = 10,
) -> dict[str, float]:
    """计算 MRR@k / Recall@1 / Recall@k / nDCG@k。

    retrieve(qid, query_text) -> 按分数降序的 pid 列表；qrels 中相关度为二值（0/1）。
    """
    mrr = r1 = r10 = ndcg = 0.0
    n = 0
    for qid, qtext in tqdm(queries.items(), desc="评测", unit=" query"):
        rel = qrels.get(qid)
        if not rel:
            continue
        ranked = retrieve(qid, qtext)[:k]
        if not ranked:
            continue
        # MRR@k：第一个相关文档的倒数排名
        for i, pid in enumerate(ranked, start=1):
            if pid in rel:
                mrr += 1.0 / i
                break
        # Recall@1 / Recall@k：命中相关文档占比
        r1 += sum(1 for pid in ranked[:1] if pid in rel) / len(rel)
        r10 += sum(1 for pid in ranked if pid in rel) / len(rel)
        # nDCG@k（二值相关）：DCG = Σ 1/log2(rank+1)，IDCG 取理想排序
        dcg = sum(1.0 / math.log2(i + 1) for i, pid in enumerate(ranked, start=1) if pid in rel)
        idcg = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(rel), k) + 1))
        ndcg += dcg / idcg if idcg else 0.0
        n += 1
    n = n or 1
    return {
        "num_queries": float(n),
        "mrr@10": mrr / n,
        "recall@1": r1 / n,
        "recall@10": r10 / n,
        "ndcg@10": ndcg / n,
    }


def print_metrics(title: str, metrics: dict[str, float]) -> None:
    """统一打印指标，便于两份评测对照输出。"""
    print(f"\n===== {title} =====")
    for key, val in metrics.items():
        if key == "num_queries":
            print(f"  {key}: {int(val)}")
        else:
            print(f"  {key}: {val:.4f}")


def main() -> None:
    """入库入口：python tests/init_data.py [--workers N] [--backend onnx|torch] [--limit N] [--resume-from N]。"""
    parser = argparse.ArgumentParser(description="mMARCO 中文集合入库 Qdrant")
    parser.add_argument("--limit", type=int, default=None, help="仅入库前 N 条（冒烟测试用）")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="每批入库条数")
    parser.add_argument("--flush-every", type=int, default=FLUSH_EVERY, help="每多少批同步一次并落盘断点")
    parser.add_argument("--collection", default=HYBRID_COLLECTION, help="目标集合名")
    parser.add_argument("--resume-from", type=int, default=None, help="强制从第 N 行开始（仅单进程生效）")
    parser.add_argument("--device", default=None, choices=["cpu", "cuda"], help="稠密向量设备（默认自动检测，仅 torch 后端）")
    parser.add_argument("--backend", default=BACKEND, choices=["torch", "onnx"], help="稠密向量后端（onnx 更快，torch 兼容）")
    parser.add_argument("--workers", type=int, default=None, help="多进程 worker 数（1 为单进程顺序入库）")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    backend = args.backend
    device = _detect_device(args.device) if backend == "torch" else "cpu"
    logger.info("稠密向量后端：%s（设备 %s）", backend, device)

    workers = args.workers or 4
    logger.info("workers：%d", workers)
    if workers > 1:
        # 多进程分片：每个进程内单线程，靠多进程吃满所有核
        ingest_hybrid_collection_parallel(
            workers=workers,
            collection_name=args.collection,
            batch_size=args.batch_size,
            flush_every=args.flush_every,
            limit=args.limit,
            device=device,
            backend=backend,
        )
    else:
        # 单进程顺序入库：单进程内多线程吃满所有核，带 tqdm 进度条
        if backend == "torch" and device == "cpu":
            try:
                import torch
                torch.set_num_threads(os.cpu_count() or 4)
            except ImportError:
                pass
        store = build_hybrid_store(args.collection, device=device, backend=backend)
        ingest_hybrid_collection(
            store,
            limit=args.limit,
            batch_size=args.batch_size,
            flush_every=args.flush_every,
            resume_from=args.resume_from,
        )


if __name__ == "__main__":
    main()
