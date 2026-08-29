"""FastAPI 应用工厂：初始化依赖、注册路由、配置 CORS 与生命周期。

依赖的创建与组装都集中在 app/deps.py 的 Deps 容器里，这里只负责：
    1. 启动时拿到全局唯一的 deps 并挂在 app.state 上
    2. 启动时把知识库写入向量库
    3. 注册路由与 CORS
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.ai import build_ai_router
from app.deps import get_deps
from app.rag.vector_store import ingest_knowledge_base

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用。"""
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 启动时：初始化依赖（Deps 内部会创建 Mongo / Redis / 模型 / Qdrant / 工作流）
        logger.info("[启动] 开始初始化依赖（Mongo / Redis / 模型 / Qdrant / 工作流）...")
        deps = get_deps()
        app.state.deps = deps
        logger.info("[启动] 依赖初始化完成")

        # 知识库入库（Qdrant 未就绪 / 模型未放置时只告警，不阻止启动）
        try:
            ingest_knowledge_base(deps.vector_store, deps.settings)
            logger.info("[启动] 知识库入库完成")
        except Exception:
            logger.exception(
                "知识库入库失败，请检查 Qdrant 是否启动、模型文件是否已按 resources/onnx 说明放置"
            )

        yield
        # 关闭时：释放连接
        logger.info("[启动] 应用关闭，释放连接")
        await deps.close()

    app = FastAPI(title="agent-py", lifespan=lifespan)

    # CORS：允许所有来源（旧项目 CorsConfig 曾配置，前端可能以 file:// 打开）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(build_ai_router())

    return app
