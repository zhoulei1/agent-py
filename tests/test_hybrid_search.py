"""混合检索（稠密 + BM25 稀疏，RRF 融合）的入库与检索测试。

入库数据源：tests/init.docx 与 tests/init.pdf。
公共初始化逻辑（向量库构建 / 文档片段加载）已抽离到 init_data.py 复用。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))        # tests/（同目录模块）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 项目根目录（app 包）

from init_data import build_hybrid_store, load_chunks

COLLECTION_NAME = "hybrid-search-test"


class HybridSearchTest(unittest.TestCase):
    def setUp(self):
        """构建混合向量库（稠密 + 稀疏，测试专用集合）。"""
        self.store = build_hybrid_store(COLLECTION_NAME)

    def tearDown(self):
        """清理测试集合，避免污染。"""
        if self.store.client.collection_exists(COLLECTION_NAME):
            self.store.client.delete_collection(COLLECTION_NAME)

    def test_hybrid_ingest_and_search(self):
        """入库（docx + pdf）后混合检索，验证能命中相关内容。"""
        chunks = load_chunks()
        self.assertGreater(len(chunks), 0, "未从 docx/pdf 读取到内容，请确认文件非空")
        self.store.add_documents(chunks)

        documents = self.store.search("阿里云百炼X1 手机价格")
        print(f"混合检索到 {len(documents)} 条：")
        for d in documents:
            print(f"  - score={d.metadata.get('score')} | {d.page_content[:50]}")
        self.assertGreater(len(documents), 0, "混合检索应返回结果")


if __name__ == '__main__':
    unittest.main()
