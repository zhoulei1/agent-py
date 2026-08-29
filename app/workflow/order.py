"""订单查询分支：提取订单号 -> 查询订单 -> 生成客服话术。

对应旧项目 OrderAction（提取/查询，纯 Java）与 OrderReplyAgent（LLM 话术）。
"""

import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.models import OrderDTO
from app.workflow.llm_logger import llm_logging_handler

logger = logging.getLogger(__name__)

# 匹配字母数字组成的订单号（长度 >= 4），与旧版 ORDER_NO_PATTERN 一致
_ORDER_NO_PATTERN = re.compile(r"[A-Za-z0-9]{4,}")

# 系统提示词：与旧版 OrderReplyAgent 的 @SystemMessage 一致
_SYSTEM_PROMPT = "把订单对象信息整理成友好客服话术返回给用户"


class OrderAgent:
    """处理「查询订单」类问题。"""

    def __init__(self, chat_model):
        self._chat_model = chat_model

    async def answer(self, user_query: str) -> str:
        # 1. 提取订单号
        order_no = self._extract_order_no(user_query)
        logger.info("[订单查询] 提取订单号：%s", order_no)

        # 2. 查询订单（演示逻辑，对应旧版 searchOrder）
        order = self._search_order(order_no)
        logger.info("[订单查询] 查询结果：%s", order.model_dump_json())

        # 3. 用 LLM 把订单信息整理成客服话术
        prompt = f"用户问题：{user_query}，订单信息：{order.model_dump_json()}"
        response = await self._chat_model.ainvoke(
            [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=prompt)],
            config={"callbacks": [llm_logging_handler]},
        )
        return response.content or ""

    @staticmethod
    def _extract_order_no(user_query: str | None) -> str | None:
        """从用户输入里提取第一个疑似订单号；没有则返回 None。"""
        if not user_query:
            return None
        match = _ORDER_NO_PATTERN.search(user_query)
        return match.group() if match else None

    @staticmethod
    def _search_order(order_no: str | None) -> OrderDTO:
        """查询订单（演示逻辑）。对应旧版 OrderAction.searchOrder。"""
        order = OrderDTO(orderNo=order_no)
        if order_no == "abc123":
            order.des = "小米K100订单"
        else:
            order.des = "未查询到相关订单，请确认订单号是否正确"
        return order
