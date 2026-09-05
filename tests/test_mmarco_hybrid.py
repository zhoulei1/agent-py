"""联合检测：混合检索（dense + sparse，RRF 融合）的 mMARCO 检索质量评测。

与 test_hybrid_search.py 同思路（稠密语义 + BM25 关键词两路融合），
数据源换成 chinese_collection.tsv，评测指标：MRR@10 / Recall@1 / Recall@10 / nDCG@10，
并与官方 BM25 run 基线对照。

需先运行 `python tests/init_data.py` 完成入库。

冒烟测试：把 MAX_QUERIES 设成一个较小的数字（如 20）只评测前 N 条查询；None 为全量。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))        # tests/（同目录模块）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 项目根目录（app 包）

from init_data import (
    HYBRID_COLLECTION,
    QUERIES_DEV_SMALL,
    QRELS_DEV_SMALL,
    RUN_BM25,
    build_hybrid_store,
    compute_metrics,
    hybrid_search,
    load_bm25_run,
    load_qrels,
    load_queries,
    print_metrics,
)

K = 10
MAX_QUERIES: int | None = None  # None 表示全量（6980 条）；设小值用于冒烟测试


def _limit_queries(queries: dict) -> dict:
    if MAX_QUERIES is None:
        return queries
    return dict(list(queries.items())[:MAX_QUERIES])


class MmarcoHybridEval(unittest.TestCase):
    def setUp(self):
        self.store = build_hybrid_store(HYBRID_COLLECTION)
        ingested = (
            self.store.client.collection_exists(HYBRID_COLLECTION)
            and self.store.client.count(HYBRID_COLLECTION).count > 0
        )
        self.assertTrue(ingested, "请先运行 `python tests/init_data.py` 完成入库")
        self.queries = _limit_queries(load_queries(QUERIES_DEV_SMALL))
        self.qrels = load_qrels(QRELS_DEV_SMALL)

    def test_hybrid_retrieval_quality(self):
        metrics = compute_metrics(
            self.queries, self.qrels, lambda qid, q: hybrid_search(self.store, q, K), K
        )

        # 官方 BM25 run 基线，仅对同一批 query 计算
        bm25 = load_bm25_run(RUN_BM25)
        bm25_metrics = compute_metrics(
            self.queries, self.qrels, lambda qid, q: bm25.get(qid, []), K
        )

        print_metrics("混合检索（dense + sparse RRF）", metrics)
        print_metrics("官方 BM25 基线（run）", bm25_metrics)

        self.assertGreater(metrics["mrr@10"], 0.0, "MRR@10 应大于 0，请检查集合是否已入库")


if __name__ == "__main__":
    unittest.main()
