# 本地 ONNX 向量模型（bge-small-zh-v1.5）

需要两个模型文件：

- `bge-small-zh-v1.5.onnx`（约 95 MB）
- `bge-small-zh-v1.5-tokenizer.json`（约 439 KB）

## 建议放在项目目录之外

`.onnx` 文件有 95MB，如果放在项目目录里，PyCharm 等 IDE 打开项目时会去索引这个
大二进制文件，容易导致卡顿甚至内存耗尽。

因此建议把模型放到项目外的独立目录（本机已放在）：

```
D:/gitwork/agent-py-models/bge-small-zh/
```

然后在 `.env` 里用绝对路径指向它：

```env
EMBEDDING_MODEL_PATH=D:/gitwork/agent-py-models/bge-small-zh/bge-small-zh-v1.5.onnx
EMBEDDING_TOKENIZER_PATH=D:/gitwork/agent-py-models/bge-small-zh/bge-small-zh-v1.5-tokenizer.json
EMBEDDING_POOLING_MODE=CLS
```

## 如果坚持放在项目里

把文件复制到本目录后，在 PyCharm 中右键 `resources/onnx` → Mark Directory as → Excluded，
把它排除出索引即可。
