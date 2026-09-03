"""稠密向量（bge）+ Qdrant 的入库与检索测试。

入库数据源：tests/init.docx 与 tests/init.pdf。
"""

import unittest
from pathlib import Path

from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

# 测试资源目录（tests/）
DATA_DIR = Path(__file__).parent
# 本地 bge 稠密向量模型路径
EMBEDDING_MODEL_PATH = "D:/gitwork/bge-small-zh-v1.5"
COLLECTION_NAME = "bge-small-zh-v1.5-search-test"


def _load_chunks() -> list:
    """从 docx / pdf 读取文档并切分，返回片段列表。"""
    docs = Docx2txtLoader(str(DATA_DIR / "init.docx")).load()
    docs += PyPDFLoader(str(DATA_DIR / "init.pdf")).load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
    return splitter.split_documents(docs)


class MyTestCase(unittest.TestCase):
    def setUp(self):
        """创建向量模型、Qdrant 客户端、集合与向量库。"""
        self.embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL_PATH,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True},
        )
        self.client = QdrantClient(url="http://localhost:6333", api_key=None)
        if not self.client.collection_exists(COLLECTION_NAME):
            self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=512, distance=Distance.DOT),
            )
        self.vector_store = QdrantVectorStore(
            client=self.client,
            collection_name=COLLECTION_NAME,
            embedding=self.embeddings,
            distance=Distance.DOT,
        )

    def test_ingest_and_search(self):
        """入库：把 docx / pdf 写入向量库，再检索验证。"""
        chunks = _load_chunks()
        self.assertGreater(len(chunks), 0, "未从 docx/pdf 读取到内容，请确认文件非空")

        # 清空旧数据后重新入库，保证测试可重复
        if self.client.collection_exists(COLLECTION_NAME):
            self.client.delete_collection(COLLECTION_NAME)
        self.client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=512, distance=Distance.DOT),
        )
        self.vector_store.add_documents(chunks)

        retriever = self.vector_store.as_retriever(
            search_type="mmr",
            search_kwargs={
                "k": 3,       # 最终返回数
                "fetch_k": 10,  # 候选池大小
                "lambda_mult": 0.6,  # 0=多样 1=相关
            },
        )
        user_query = "阿里云百炼X1 手机"
        documents = retriever.invoke(user_query)
        print(f"检索到 {len(documents)} 条：")
        for d in documents:
            print("  -", d.page_content[:50])


if __name__ == '__main__':
    unittest.main()
