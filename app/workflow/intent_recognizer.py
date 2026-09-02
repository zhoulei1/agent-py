"""意图识别 + 参数提取，对应旧项目 IntentAgent。

用 LLM 结构化输出，一次同时得到「意图」和「意图相关参数」：
- QUERY_ORDER 提取订单号 order_no
- COMPLAINT 提取投诉要点 complaint
参数供后续分支 Agent 直接使用，避免重复解析用户原话。
"""

import logging
from typing import Optional

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.workflow.intents import Intent
from app.workflow.llm_logger import llm_logging_handler

logger = logging.getLogger(__name__)


class IntentResult(BaseModel):
    """识别结果：意图 + 参数。"""

    intent: Intent = Field(description="识别出的用户意图")
    order_no: Optional[str] = Field(default=None, description="订单号，仅 QUERY_ORDER 时提取")
    complaint: Optional[str] = Field(default=None, description="投诉要点，仅 COMPLAINT 时提取")


# 系统提示词：在旧版 IntentAgent 基础上补充「参数提取」要求
_SYSTEM_PROMPT = """你是客服意图识别助手。分析用户输入，输出意图枚举及对应参数：
PRODUCT_CONSULT：产品/业务咨询，无需参数
QUERY_ORDER：查询订单/物流，需提取订单号 order_no
COMPLAINT：投诉/售后/退款/维权，需提取投诉要点 complaint
UNKNOWN：无法识别或要求转人工，无需参数"""


class IntentRecognizer:
    """识别用户意图并提取参数。"""

    def __init__(self, chat_model):
        self._structured_model = chat_model.with_structured_output(IntentResult)
        self._prompt = ChatPromptTemplate.from_messages(
            [
                ("system", _SYSTEM_PROMPT),
                ("human", "用户问题：{user_query}"),
            ]
        )

    async def recognize(self, user_query: str) -> IntentResult:
        """识别意图与参数；解析失败时兜底为 UNKNOWN。"""
        messages = self._prompt.format_messages(user_query=user_query)
        try:
            result: IntentResult = await self._structured_model.ainvoke(
                messages, config={"callbacks": [llm_logging_handler]}
            )
            logger.info(
                "[意图识别] 输入=%s -> intent=%s, order_no=%s, complaint=%s",
                user_query, result.intent.value, result.order_no, result.complaint,
            )
            return result
        except Exception as exc:
            logger.warning("[意图识别] 识别失败，兜底为 UNKNOWN：%s", exc)
            return IntentResult(intent=Intent.UNKNOWN)
