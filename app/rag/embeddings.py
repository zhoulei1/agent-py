"""本地 ONNX 向量模型（bge-small-zh-v1.5）的 LangChain Embeddings 实现。

对应旧项目 AiConfig 里的 OnnxEmbeddingModel。工作流程：
    文本 -> tokenizer 分词 -> ONNX 推理 -> 取 [CLS] 向量（CLS pooling）-> L2 归一化
"""

from pathlib import Path

import numpy as np
import onnxruntime as ort
from langchain_core.embeddings import Embeddings
from tokenizers import Tokenizer


class BgeOnnxEmbeddings(Embeddings):
    """使用本地 ONNX 模型对文本做向量化。

    使用说明：
        - 模型文件较大，不在代码仓库内，需按 resources/onnx/bge-small-zh/README 自行放置。
        - 本类实现 LangChain 的 Embeddings 接口，可被 Qdrant / retriever 直接使用。
    """

    def __init__(self, model_path: str, tokenizer_path: str, pooling_mode: str = "CLS"):
        # 先检查文件是否存在，缺失时给出清晰提示（避免底层抛出难懂的 os error 2）
        for path in (model_path, tokenizer_path):
            if not Path(path).is_file():
                raise FileNotFoundError(
                    f"找不到模型文件：{path}\n"
                    "请按 resources/onnx/bge-small-zh/README.md 的说明，"
                    "把 bge-small-zh-v1.5.onnx 与 bge-small-zh-v1.5-tokenizer.json 复制到该目录。"
                )

        # 加载 tokenizer（HuggingFace tokenizer.json 格式）
        self._tokenizer = Tokenizer.from_file(tokenizer_path)

        # 创建 ONNX 推理会话（CPU 即可）
        self._session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])

        # 保存 ONNX 模型要求的输入名（通常是 input_ids / attention_mask / token_type_ids）
        self._input_names = [inp.name for inp in self._session.get_inputs()]

        # 输出名：BERT 类模型的 last_hidden_state
        self._output_name = self._session.get_outputs()[0].name

        if pooling_mode.upper() != "CLS":
            # 当前知识库模型使用 CLS pooling，其余模式预留
            raise ValueError(f"暂不支持 pooling_mode={pooling_mode}，仅支持 CLS")

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """核心：一批文本 -> 一批向量。"""
        # 1. tokenize（padding + truncation，与训练时一致）
        encodings = self._tokenizer.encode_batch(texts)
        max_len = max(len(e.ids) for e in encodings)

        input_ids = []
        attention_masks = []
        token_type_ids = []
        for e in encodings:
            pad_len = max_len - len(e.ids)
            input_ids.append(e.ids + [0] * pad_len)  # [PAD] 用 0
            attention_masks.append(e.attention_mask + [0] * pad_len)
            # token_type_ids：部分 tokenizer 默认不返回，此时按全 0 处理（单句输入本就是全 0）
            tids = e.type_ids if e.type_ids is not None else [0] * len(e.ids)
            token_type_ids.append(tids + [0] * pad_len)

        # 2. 组装 ONNX 输入（按模型要求的输入名取用）
        available = {
            "input_ids": np.array(input_ids, dtype=np.int64),
            "attention_mask": np.array(attention_masks, dtype=np.int64),
            "token_type_ids": np.array(token_type_ids, dtype=np.int64),
        }
        feeds = {name: available[name] for name in self._input_names if name in available}

        # 3. 推理得到 last_hidden_state: [batch, seq_len, hidden]
        outputs = self._session.run([self._output_name], feeds)
        last_hidden_state = outputs[0]

        # 4. CLS pooling：取每个样本第 0 个 token（[CLS]）的向量
        cls_vectors = last_hidden_state[:, 0, :]

        # 5. L2 归一化（配合 Qdrant 余弦相似度使用）
        norms = np.linalg.norm(cls_vectors, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)  # 避免除零
        normalized = cls_vectors / norms

        return normalized.astype(np.float32).tolist()

    # ---- 实现 LangChain Embeddings 接口 ----

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量向量化（用于文档入库）。"""
        if not texts:
            return []
        return self._embed(texts)

    def embed_query(self, text: str) -> list[float]:
        """向量化单个查询（用于检索）。"""
        return self._embed([text])[0]
