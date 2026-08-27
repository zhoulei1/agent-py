"""Qdrant 向量库：启动时把知识库文本入库，并提供检索器。

对应旧项目 VectorStoreComponent（ingest）与 AiConfig.contentRetriever（检索）。
"""

import logging
from pathlib import Path

from langchain_qdrant import QdrantVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from app.config import Settings, get_settings, resolve_path
from app.rag.embeddings import BgeOnnxEmbeddings

logger = logging.getLogger(__name__)

# 向量维度：bge-small-zh-v1.5 输出 512 维
VECTOR_SIZE = 512


def build_qdrant_client(settings: Settings | None = None) -> QdrantClient:
    """根据配置创建 Qdrant 客户端。

    走 HTTP REST 接口（Qdrant 默认 6333），而不是 gRPC（6334）：
    新版 qdrant-client 走 gRPC 与 Qdrant 1.16 存在兼容问题（连接被重置），
    因此这里统一使用 HTTP，更稳定。
    """
    settings = settings or get_settings()
    scheme = "https" if settings.qdrant_use_tls else "http"
    url = f"{scheme}://{settings.qdrant_host}:{settings.qdrant_port}"
    return QdrantClient(url=url, api_key=settings.qdrant_api_key or None)


def build_embeddings(settings: Settings | None = None) -> BgeOnnxEmbeddings:
    """创建本地 ONNX 向量模型实例。"""
    settings = settings or get_settings()
    return BgeOnnxEmbeddings(
        model_path=resolve_path(settings.embedding_model_path),
        tokenizer_path=resolve_path(settings.embedding_tokenizer_path),
        pooling_mode=settings.embedding_pooling_mode,
    )


def build_vector_store(
    client: QdrantClient,
    embeddings: BgeOnnxEmbeddings,
    settings: Settings | None = None,
) -> QdrantVectorStore:
    """创建 LangChain 的 Qdrant 向量库包装（供 ingest 与检索共用）。"""
    settings = settings or get_settings()
    return QdrantVectorStore(
        client=client,
        collection_name=settings.qdrant_collection_name,
        embedding=embeddings,
    )


def ingest_knowledge_base(
    client: QdrantClient,
    vector_store: QdrantVectorStore,
    settings: Settings | None = None,
) -> None:
    """读取 resources/embedding/init.txt，切分后写入向量库。

    对应旧项目 VectorStoreComponent.ingestEmbedding：
        递归切分(300, 50) -> 清空向量库 -> 入库。
    """
    settings = settings or get_settings()
    collection_name = settings.qdrant_collection_name

    # 先删除旧集合（存在才删）再重建，保证幂等
    if client.collection_exists(collection_name):
        client.delete_collection(collection_name=collection_name)
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )

    # 读取知识库文本（resolve_path 返回字符串，用 Path 包装后读文件）
    init_path = resolve_path("resources/embedding/init.txt")
    text = Path(init_path).read_text(encoding="utf-8")

    # 文本切分：chunk_size=300, chunk_overlap=50（对应旧版 DocumentSplitters.recursive(300, 50)）
    splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
    docs = splitter.create_documents([text])
    logger.info("知识库切分为 %d 个片段，开始写入 Qdrant", len(docs))

    vector_store.add_documents(docs)
    logger.info("知识库入库完成")


class QdrantMinScoreRetriever:
    """自定义检索器：按「原始余弦相似度」阈值过滤结果。

    为什么不用 QdrantVectorStore 自带的 as_retriever(score_threshold=...)：
    当前 langchain-qdrant 版本的 score_threshold 用的是「相关性分数 (1+cos)/2」，
    且行为不稳定（实测阈值过滤不生效）。这里直接用 similarity_search_with_score
    拿到原始余弦分数，再按阈值过滤，与旧项目 minScore(0.8) 的行为完全对齐。
    """

    def __init__(self, vector_store: QdrantVectorStore, min_score: float = 0.8, k: int = 5):
        self._vector_store = vector_store
        self._min_score = min_score
        self._k = k

    def invoke(self, query: str):
        """同步检索（供测试 / 非异步场景使用）。"""
        docs_and_scores = self._vector_store.similarity_search_with_score(query, k=self._k)
        return [doc for doc, score in docs_and_scores if score >= self._min_score]

    async def ainvoke(self, query: str):
        """异步检索（供工作流里的 await 调用）。"""
        docs_and_scores = await self._vector_store.asimilarity_search_with_score(query, k=self._k)
        return [doc for doc, score in docs_and_scores if score >= self._min_score]


def build_retriever(
    vector_store: QdrantVectorStore,
    settings: Settings | None = None,
) -> QdrantMinScoreRetriever:
    """创建检索器：余弦相似度阈值 + 最大返回数（默认对应旧版 minScore / maxResults，可在配置里调整）。"""
    settings = settings or get_settings()
    return QdrantMinScoreRetriever(
        vector_store,
        min_score=settings.qdrant_min_score,
        k=settings.qdrant_max_results,
    )
