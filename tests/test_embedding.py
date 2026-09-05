"""稠密向量（bge）+ Qdrant 的入库与检索测试。

入库数据源：tests/init.docx 与 tests/init.pdf。
公共初始化逻辑（向量模型 / 客户端 / 文档片段加载）已抽离到 init_data.py 复用。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))        # tests/（同目录模块）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 项目根目录（app 包）

from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from init_data import build_client, build_dense_embeddings, load_chunks

COLLECTION_NAME = "bge-small-zh-v1.5-search-test"


class MyTestCase(unittest.TestCase):
    def setUp(self):
        """创建向量模型、Qdrant 客户端、集合与向量库。"""
        self.embeddings = build_dense_embeddings()
        self.client: QdrantClient = build_client()
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
        chunks = load_chunks()
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
