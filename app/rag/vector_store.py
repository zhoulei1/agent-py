"""Qdrant 向量库：启动时把知识库文本入库，并提供检索器。

对应旧项目 VectorStoreComponent（ingest）与 AiConfig.contentRetriever（检索）。
"""

import logging
from pathlib import Path

from langchain_core.vectorstores import VectorStoreRetriever
from langchain_qdrant import QdrantVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from langchain_huggingface import HuggingFaceEmbeddings


from app.config import Settings, get_settings, resolve_path

logger = logging.getLogger(__name__)

# 向量维度：bge-small-zh-v1.5 输出 512 维
VECTOR_SIZE = 512


def _build_qdrant_client(settings: Settings) -> QdrantClient:
    """创建qdrant客户端。"""
    settings = settings or get_settings()
    return QdrantClient(url=settings.qdrant_url,api_key= None)


def _build_embeddings(settings: Settings) -> HuggingFaceEmbeddings:
    """创建向量模型（HuggingFaceEmbeddings，支持模型 ID 或本地目录路径）。"""
    return HuggingFaceEmbeddings(
        model_name=settings.embedding_model_path,
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True},
    )


def build_vector_store(
    settings: Settings,
) -> QdrantVectorStore:
    """创建 LangChain 的 Qdrant 向量库包装（供 ingest 与检索共用）。"""
    embeddings = _build_embeddings(settings)
    client = _build_qdrant_client(settings)

    collection_name = settings.qdrant_collection_name
    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.DOT),
        )

    return QdrantVectorStore(
        client=client,
        collection_name=settings.qdrant_collection_name,
        embedding=embeddings,
        distance=Distance.DOT
    )


def build_retriever(
    vector_store: QdrantVectorStore,
) -> VectorStoreRetriever:
    return vector_store.as_retriever(
    search_type="mmr",
    search_kwargs={
        "k": 3,           # 最终返回数
        "fetch_k": 10,    # 候选池大小
        "lambda_mult": 0.6,  # 0=多样 1=相关
    }
)



def ingest_knowledge_base(
    vector_store: QdrantVectorStore,
    settings: Settings | None = None,
) -> None:
    """
    读取 app/rag/init.txt，切分后写入向量库。
    """
    settings = settings or get_settings()
    collection_name = settings.qdrant_collection_name
    client = vector_store.client
    # 先删除旧集合（存在才删）再重建，保证幂等
    if client.collection_exists(collection_name):
        client.delete_collection(collection_name=collection_name)
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.DOT),
    )

    # 读取知识库文本（resolve_path 返回字符串，用 Path 包装后读文件）
    init_path = resolve_path("app/rag/init.txt")
    text = Path(init_path).read_text(encoding="utf-8")

    # 文本切分：chunk_size=300, chunk_overlap=50）
    splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
    docs = splitter.create_documents([text])
    logger.info("知识库切分为 %d 个片段，开始写入 Qdrant", len(docs))

    vector_store.add_documents(docs)
    logger.info("知识库入库完成")
