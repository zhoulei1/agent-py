"""客服入口工作流：意图识别 -> 条件分发，对应旧项目 CustomerServiceWorkflow / AgentFlowConfig。

与旧版一致的路由：
    PRODUCT_CONSULT -> 产品咨询（RAG + memory + 工具）
    QUERY_ORDER     -> 订单查询
    COMPLAINT       -> 售后投诉
    UNKNOWN / 其它  -> 兜底提示
"""

import logging

from app.services.redis_memory import RedisChatMemoryStore
from app.workflow.intents import Intent

logger = logging.getLogger(__name__)

# 兜底文案：与旧版 AgentFlowConfig.FALLBACK_ANSWER 一致
_FALLBACK_ANSWER = "抱歉，暂时无法理解您的需求，请重新输入或补充更多信息。"


class CustomerServiceWorkflow:
    """编排整个客服流程，对上层（AiService）提供 chat() 入口。"""

    def __init__(
        self,
        intent_classifier,
        product_consult_agent,
        order_agent,
        complaint_agent,
        memory_store: RedisChatMemoryStore,
    ):
        self._intent_classifier = intent_classifier
        self._product_consult_agent = product_consult_agent
        self._order_agent = order_agent
        self._complaint_agent = complaint_agent
        self._memory_store = memory_store

    async def chat(self, conversation_id: str, user_query: str, user_id: str | None) -> str:
        """处理一轮用户提问，返回最终回答文本。"""

        # 1. 意图识别
        intent = await self._intent_classifier.classify(user_query)
        logger.info("[工作流] 意图识别结果：intent=%s", intent.value)

        # 2. 条件分发
        if intent == Intent.PRODUCT_CONSULT:
            logger.info("[工作流] 进入「产品咨询」分支（RAG + 记忆 + 工具）")
            answer = await self._product_consult_agent.answer(conversation_id, user_query)
        elif intent == Intent.QUERY_ORDER:
            logger.info("[工作流] 进入「订单查询」分支")
            answer = await self._order_agent.answer(user_query)
        elif intent == Intent.COMPLAINT:
            logger.info("[工作流] 进入「售后投诉」分支")
            answer = await self._complaint_agent.answer(user_query)
        else:
            logger.info("[工作流] 进入「兜底」分支（意图未知 / 转人工）")
            answer = _FALLBACK_ANSWER

        answer = answer or _FALLBACK_ANSWER

        # 3. 持久化 chat memory（与旧版一致：只有产品咨询分支使用 memory，
        #    这里对产品咨询分支写入本轮对话，让 Redis 历史真正生效）
        if intent == Intent.PRODUCT_CONSULT:
            await self._memory_store.append_turn(conversation_id, user_query, answer)

        return answer
