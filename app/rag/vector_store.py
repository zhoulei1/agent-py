"""Qdrant 混合检索：稠密向量 + BM25 稀疏向量，RRF 融合。

对应旧项目 VectorStoreComponent（ingest）与 AiConfig.contentRetriever（检索）。

「混合检索」= 语义检索 + 关键词检索两条路，最后用 RRF（倒数排名融合）合并：
    - 稠密向量（dense）：bge-small-zh-v1.5，衡量「语义相近」，能召回换一种说法但意思相近的内容；
    - 稀疏向量（sparse）：BM25，衡量「关键词命中」，能精确命中用户提到的专有名词（如手机型号）。
两条路各取若干候选，RRF 按排名打分合并，兼顾「说得像」和「字面像」。
"""

import asyncio
import logging
from pathlib import Path

from fastembed import SparseTextEmbedding
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient, models
from qdrant_client.models import Distance, VectorParams

from app.config import Settings, get_settings, resolve_path

logger = logging.getLogger(__name__)

# 向量维度：bge-small-zh-v1.5 输出 512 维
VECTOR_SIZE = 512
# 两个具名向量的名字，Qdrant 里一条数据同时存这两份向量
DENSE_VECTOR = "dense"    # 稠密向量（语义）
SPARSE_VECTOR = "sparse"  # 稀疏向量（关键词）


def _build_qdrant_client(settings: Settings) -> QdrantClient:
    """创建 Qdrant 客户端（走 HTTP，端口见 settings.qdrant_url）。"""
    settings = settings or get_settings()
    return QdrantClient(
        url=settings.qdrant_url,
        api_key=None,
        check_compatibility=False,  # 本地 server 1.16 与 client 1.19 存在版本差，已知可兼容，跳过告警
        timeout=30,                 # 首次启动加载模型时机器较忙，放宽超时避免误判连接失败
    )


def _build_dense_embeddings(settings: Settings) -> HuggingFaceEmbeddings:
    """稠密向量模型（bge-small-zh，支持模型 ID 或本地目录路径）。"""
    return HuggingFaceEmbeddings(
        model_name=settings.embedding_model_path,
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True},  # L2 归一化，配合 DOT 距离即余弦相似度
    )


def _build_sparse_embeddings(settings: Settings) -> SparseTextEmbedding:
    """稀疏向量模型（BM25，Qdrant 官方轻量模型，用于关键词检索）。

    直接加载本地模型目录（settings.bm25_model_path），不联网下载。
    disable_stemmer=True：中文无需词干提取（fastembed 的 BM25 也不支持中文 stemmer）。
    """
    return SparseTextEmbedding(
        model_name="Qdrant/bm25",
        specific_model_path=settings.bm25_model_path,
        disable_stemmer=True,
    )


class HybridVectorStore:
    """混合向量库：负责建集合、入库、混合检索。"""

    def __init__(self, client, dense_embeddings, sparse_embeddings, collection_name):
        self.client = client
        self.dense = dense_embeddings
        self.sparse = sparse_embeddings
        self.collection_name = collection_name

    def _create_collection(self) -> None:
        """创建集合：同时声明稠密向量与稀疏向量两个字段。"""
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={DENSE_VECTOR: VectorParams(size=VECTOR_SIZE, distance=Distance.DOT)},
            sparse_vectors_config={SPARSE_VECTOR: models.SparseVectorParams()},
        )

    def add_documents(self, docs: list[Document]) -> None:
        """把文档片段向量化（稠密 + 稀疏）后写入集合（幂等：先删后建）。

        这是入库的核心逻辑，供启动时的 ingest() 与测试共用。
        """
        if not docs:
            logger.warning("没有文档需要入库，跳过")
            return
        # 先删后建，保证每次入库都是干净、可重复的
        if self.client.collection_exists(self.collection_name):
            self.client.delete_collection(self.collection_name)
        self._create_collection()

        contents = [d.page_content for d in docs]
        # 两路向量化：稠密（语义）+ 稀疏（关键词）
        dense_vectors = self.dense.embed_documents(contents)
        sparse_vectors = list(self.sparse.embed(contents))

        points = [
            models.PointStruct(
                id=i,
                vector={
                    DENSE_VECTOR: dense_vectors[i],
                    SPARSE_VECTOR: models.SparseVector(
                        indices=[int(i) for i in sparse_vectors[i].indices],
                        values=[float(v) for v in sparse_vectors[i].values],
                    ),
                },
                payload={"page_content": contents[i]},
            )
            for i in range(len(contents))
        ]
        self.client.upsert(collection_name=self.collection_name, points=points)
        logger.info("知识库入库完成（共 %d 条）", len(points))

    def ingest(self, settings: Settings | None = None) -> None:
        """读取 app/rag/init.txt，切分后入库（供启动时调用）。"""
        init_path = resolve_path("app/rag/init.txt")
        text = Path(init_path).read_text(encoding="utf-8")
        splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
        docs = splitter.create_documents([text])
        logger.info("知识库切分为 %d 个片段，开始向量化", len(docs))
        self.add_documents(docs)

    def search(self, query: str, k: int = 3) -> list[Document]:
        """混合检索：稠密 + 稀疏两路 prefetch，RRF 融合后返回 top-k 片段。"""
        dense_vector = self.dense.embed_query(query)
        # query_embed 返回生成器，取第一个（单条查询只有一个结果）
        sparse = next(iter(self.sparse.query_embed(query)))
        sparse_vector = models.SparseVector(
            indices=[int(i) for i in sparse.indices],
            values=[float(v) for v in sparse.values],
        )

        results = self.client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                # 每一路先各自召回 k*4 个候选，供融合使用
                models.Prefetch(query=dense_vector, using=DENSE_VECTOR, limit=k * 4),
                models.Prefetch(query=sparse_vector, using=SPARSE_VECTOR, limit=k * 4),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),  # RRF 倒数排名融合
            limit=k,
        )
        return [
            Document(page_content=hit.payload["page_content"], metadata={"score": hit.score})
            for hit in results.points
        ]


def build_vector_store(settings: Settings) -> HybridVectorStore:
    """创建混合向量库（稠密 + 稀疏），供入库与检索共用。"""
    client = _build_qdrant_client(settings)
    store = HybridVectorStore(
        client=client,
        dense_embeddings=_build_dense_embeddings(settings),
        sparse_embeddings=_build_sparse_embeddings(settings),
        collection_name=settings.qdrant_collection_name,
    )
    # 集合不存在时先建好（正式入库时仍会删后重建）
    if not client.collection_exists(settings.qdrant_collection_name):
        store._create_collection()
    return store


class HybridRetriever:
    """把混合检索包装成 LangChain retriever 接口（ainvoke 返回 Document 列表）。

    检索是 CPU 密集的同步操作（本地模型推理），用 asyncio.to_thread 丢到线程池，
    避免阻塞事件循环、影响其他并发请求。
    """

    def __init__(self, store: HybridVectorStore, k: int = 3):
        self._store = store
        self._k = k

    async def ainvoke(self, query: str, config=None, **kwargs) -> list[Document]:
        return await asyncio.to_thread(self._store.search, query, self._k)


def build_retriever(vector_store: HybridVectorStore) -> HybridRetriever:
    """创建混合检索器。"""
    return HybridRetriever(vector_store, k=3)


def ingest_knowledge_base(vector_store: HybridVectorStore, settings: Settings | None = None) -> None:
    """启动时把知识库写入向量库（入口，供 application.py 调用）。"""
    vector_store.ingest(settings)
