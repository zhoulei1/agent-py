"""订单查询分支：提取订单号 -> 查询订单（纯逻辑，不负责话术润色）。

对应旧项目 OrderAction（提取/查询，纯 Java）。话术润色已挪到 ReplyPolisher。
"""

import logging
import re

from app.models import OrderDTO

logger = logging.getLogger(__name__)

# 匹配字母数字组成的订单号（长度 >= 4），与旧版 ORDER_NO_PATTERN 一致
_ORDER_NO_PATTERN = re.compile(r"[A-Za-z0-9]{4,}")


class OrderAgent:
    """订单查询（纯逻辑）：提取订单号 + 查询订单，返回原始订单信息。"""

    def lookup(self, user_query: str | None, order_no: str | None = None) -> OrderDTO:
        """提取订单号并查询订单。优先用意图识别出的 order_no，否则正则兜底。"""
        order_no = order_no or self._extract_order_no(user_query)
        return self._search_order(order_no)

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
