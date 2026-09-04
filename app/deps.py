"""依赖组装（组合根 / Composition Root）。

所有依赖集中在这一个 Deps 类里，用注释按「领域」分组，方便一眼看清全貌。
每个对象的「怎么创建」抽成独立的 build_* 函数，让 __init__ 保持是清晰的赋值。
"""

import logging

from langchain_openai import ChatOpenAI
from motor.motor_asyncio import AsyncIOMotorClient
from redis.asyncio import Redis
from pydantic import SecretStr

from app.config import Settings, get_settings
from app.rag.vector_store import (
    build_retriever,
    build_vector_store,
)
from app.services.ai_service import AiService
from app.services.chat_message_service import ChatMessageService
from app.services.conversation_service import ConversationService
from app.services.redis_memory import RedisChatMemoryStore
from app.workflow.customer_service import CustomerServiceWorkflow
from app.workflow.intent_recognizer import IntentRecognizer
from app.workflow.order_mcp_client import OrderMCPClient
from app.workflow.product_consult import ProductConsultAgent
from app.workflow.reply_polisher import ReplyPolisher
from app.workflow.tools import query_last_year_min_price

logger = logging.getLogger(__name__)


def build_chat_model(settings: Settings) -> ChatOpenAI:
    return ChatOpenAI(
        api_key=SecretStr(settings.qianwen_api_key) ,
        base_url=settings.qianwen_base_url,
        model=settings.qianwen_model_name,
        temperature=0,
        timeout=120,
    )


def build_workflow(deps: "Deps") -> CustomerServiceWorkflow:
    """组装客服工作流及其各个分支 Agent（意图识别 / 产品咨询 / 订单 / 润色兜底）。"""
    intent_recognizer = IntentRecognizer(deps.chat_model)
    product_consult_agent = ProductConsultAgent(
        deps.chat_model, deps.retriever, deps.memory_store, [query_last_year_min_price]
    )
    order_agent = OrderMCPClient(deps.settings.order_mcp_url)
    polisher = ReplyPolisher(deps.chat_model)

    return CustomerServiceWorkflow(
        intent_recognizer=intent_recognizer,
        product_consult_agent=product_consult_agent,
        order_agent=order_agent,
        polisher=polisher,
        memory_store=deps.memory_store,
    )


class Deps:
    """应用运行期依赖容器：集中持有所有共享对象，按领域分组。

    - __init__ 里创建连接与对象
    - close() 里统一释放连接（应用退出时调用）
    """

    def __init__(self, settings: Settings):
        self.settings = settings

        # ---------- 底层客户端 ----------
        self.mongo_client = AsyncIOMotorClient(settings.mongodb_uri)
        self.redis_client = Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password or None,
            db=settings.redis_database,
            decode_responses=True,
        )

        # ---------- 服务层 ----------
        self.db = self.mongo_client.get_default_database()
        self.conversation_service = ConversationService(self.db)
        self.chat_message_service = ChatMessageService(self.db)
        self.memory_store = RedisChatMemoryStore(self.redis_client)

        # ---------- 大模型 ----------
        self.chat_model = build_chat_model(settings)

        self.vector_store = build_vector_store(settings)
        self.retriever = build_retriever(self.vector_store)

        # ---------- 工作流与 AI 服务 ----------
        self.workflow = build_workflow(self)
        self.ai_service = AiService(self.chat_message_service, self.workflow)

    async def close(self) -> None:
        """释放底层连接。"""
        self.mongo_client.close()
        await self.redis_client.aclose()


# 全局单例（进程内复用，避免重复建连）
_deps: Deps | None = None


def get_deps() -> Deps:
    """返回全局唯一的 Deps 容器。"""
    global _deps
    if _deps is None:
        _deps = Deps(get_settings())
    return _deps
