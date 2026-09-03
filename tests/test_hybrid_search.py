"""混合检索（稠密 + BM25 稀疏，RRF 融合）的入库与检索测试。

入库数据源：tests/init.docx 与 tests/init.pdf。
"""

import unittest
from pathlib import Path

from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import Settings
from app.rag.vector_store import build_vector_store

# 测试资源目录（tests/）
DATA_DIR = Path(__file__).parent
# 本地模型路径
EMBEDDING_MODEL_PATH = "D:/gitwork/bge-small-zh-v1.5"
BM25_MODEL_PATH = "D:/gitwork/bm25"
COLLECTION_NAME = "hybrid-search-test"


def _load_chunks() -> list:
    """从 docx / pdf 读取文档并切分，返回片段列表。"""
    docs = Docx2txtLoader(str(DATA_DIR / "init.docx")).load()
    docs += PyPDFLoader(str(DATA_DIR / "init.pdf")).load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
    return splitter.split_documents(docs)


class HybridSearchTest(unittest.TestCase):
    def setUp(self):
        """构建混合向量库（稠密 + 稀疏，测试专用集合）。"""
        self.settings = Settings(
            qdrant_url="http://localhost:6333",
            qdrant_collection_name=COLLECTION_NAME,
            embedding_model_path=EMBEDDING_MODEL_PATH,
            bm25_model_path=BM25_MODEL_PATH,
        )
        self.store = build_vector_store(self.settings)

    def tearDown(self):
        """清理测试集合，避免污染。"""
        if self.store.client.collection_exists(COLLECTION_NAME):
            self.store.client.delete_collection(COLLECTION_NAME)

    def test_hybrid_ingest_and_search(self):
        """入库（docx + pdf）后混合检索，验证能命中相关内容。"""
        chunks = _load_chunks()
        self.assertGreater(len(chunks), 0, "未从 docx/pdf 读取到内容，请确认文件非空")
        self.store.add_documents(chunks)

        documents = self.store.search("阿里云百炼X1 手机价格")
        print(f"混合检索到 {len(documents)} 条：")
        for d in documents:
            print(f"  - score={d.metadata.get('score')} | {d.page_content[:50]}")
        self.assertGreater(len(documents), 0, "混合检索应返回结果")


if __name__ == '__main__':
    unittest.main()
