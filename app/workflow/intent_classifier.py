"""意图识别，对应旧项目 service/agent/IntentAgent。

用 LLM 结构化输出（with_structured_output）把用户输入分类为 Intent 枚举。
"""

import logging

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.workflow.intents import Intent

logger = logging.getLogger(__name__)


class IntentResult(BaseModel):
    """LLM 结构化输出：意图枚举。"""

    intent: Intent = Field(description="识别出的用户意图")

# 系统提示词：与旧版 IntentAgent 的 @SystemMessage 内容一致
_SYSTEM_PROMPT = """你是客服意图识别助手。分析用户输入，只输出以下枚举之一（不要输出任何其它内容）：
PRODUCT_CONSULT：普通业务/产品咨询、政策、使用问题
QUERY_ORDER：查询订单、物流
COMPLAINT：投诉、售后、退款、维权
UNKNOWN：无法识别，或者用户明确要求转人工"""


class IntentClassifier:
    """封装「输入用户问题 -> 输出 Intent」的 LLM 调用。"""

    def __init__(self, chat_model):
        self._chat_model = chat_model
        # 用结构化输出约束模型只返回 IntentResult 里的枚举值
        self._structured_model = chat_model.with_structured_output(IntentResult)
        self._prompt = ChatPromptTemplate.from_messages(
            [
                ("system", _SYSTEM_PROMPT),
                ("human", "用户问题：{user_query}"),
            ]
        )

    async def classify(self, user_query: str) -> Intent:
        """识别用户意图，解析失败时兜底为 UNKNOWN。"""
        messages = self._prompt.format_messages(user_query=user_query)

        try:
            result: IntentResult = await self._structured_model.ainvoke(messages)
            intent = Intent.parse(result.intent.value)
            logger.info("[意图识别] 输入=%s -> intent=%s", user_query, intent.value)
            return intent
        except Exception as exc:  # 结构化输出解析失败等异常，统一按 UNKNOWN 处理
            logger.warning("[意图识别] 识别失败，兜底为 UNKNOWN：%s", exc)
            return Intent.UNKNOWN
