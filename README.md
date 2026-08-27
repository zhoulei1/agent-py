# agent-py

客服 Agent 后端（由 `ai-langchain4j-agent` 迁移的 Python 版本）。

- 只复用业务逻辑，代码结构按 Python 风格从零设计
- 对外接口路径与返回格式与原 `AiController` 一致，前端 `agent-front` 无需改动即可对接
- 技术栈：FastAPI + LangChain + 本地 ONNX(bge-small-zh) + Qdrant + Redis + MongoDB

## 目录结构

```
app/
├── config.py            # 配置（.env / 环境变量）
├── deps.py              # 依赖容器（连接与客户端）
├── application.py       # FastAPI 应用工厂（路由 / CORS / 生命周期）
├── models.py            # Pydantic 数据模型（字段名 camelCase，与前端对齐）
├── api/ai.py            # /ai 接口（等价 AIController）
├── services/            # Mongo 持久化 + Redis chat memory + AI 编排
├── rag/                 # ONNX 向量化 + Qdrant 向量库
└── workflow/            # 意图识别 -> 条件分发（产品咨询 / 订单 / 投诉）
```

## 环境准备

### 1. 安装 Python 3.12 与依赖

onnxruntime 官方最高支持 Python 3.12，因此本项目使用 3.12：

```bash
uv python install 3.12
uv sync
```

### 2. 放置本地模型文件

按 `resources/onnx/bge-small-zh/README.md` 的说明，把 `bge-small-zh-v1.5.onnx`
与 `bge-small-zh-v1.5-tokenizer.json` 放到**项目目录之外**（推荐 `D:/gitwork/agent-py-models/bge-small-zh/`），
避免 IDE 索引 95MB 大文件导致卡顿；然后在 `.env` 里用绝对路径指向它们。

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，至少填入 QIANWEN_API_KEY
```

### 4. 启动依赖服务

需要本地可用的 MongoDB(27017，库 `ai`)、Redis(6379)、Qdrant(6334)。

### 5. 启动应用

```bash
uv run python main.py
```

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/ai/streamChat` | 流式聊天（SSE），body：`{message, conversationId, userId}` |
| GET | `/ai/conversations` | 会话列表 |
| POST | `/ai/conversation` | 新建会话 |
| PUT | `/ai/conversation` | 重命名会话 |
| DELETE | `/ai/conversation/{conversationId}` | 删除会话及其消息 |
| GET | `/ai/chatMessages?conversationId=` | 会话消息列表 |
