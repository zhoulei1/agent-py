"""订单查询 MCP 服务（纯逻辑，不依赖主应用）。

从 agent-py 的 app/workflow/order.py（OrderAgent）剥离而来：
提取订单号 -> 查询订单，返回订单信息。话术润色仍由主应用负责。
"""

import re

from mcp.server.mcpserver import MCPServer

# 匹配字母数字组成的订单号（长度 >= 4），与旧版 ORDER_NO_PATTERN 一致
_ORDER_NO_PATTERN = re.compile(r"[A-Za-z0-9]{4,}")

# 演示订单数据（与旧版 OrderAction.searchOrder 一致）
_KNOWN_ORDERS = {
    "abc123": "小米K100订单",
}

server = MCPServer(
    name="order-mcp-server",
    title="订单查询服务",
    description="提取订单号并查询订单，返回订单信息（orderNo / des / userId）。",
    version="0.1.0",
)


def _extract_order_no(user_query: str | None) -> str | None:
    """从用户输入里提取第一个疑似订单号；没有则返回 None。"""
    if not user_query:
        return None
    match = _ORDER_NO_PATTERN.search(user_query)
    return match.group() if match else None


def _search_order(order_no: str | None) -> dict:
    """查询订单（演示逻辑），返回订单信息字典。"""
    order = {"orderNo": order_no, "des": "", "userId": None}
    order["des"] = _KNOWN_ORDERS.get(order_no, "未查询到相关订单，请确认订单号是否正确")
    return order


@server.tool()
def lookup_order(user_query: str | None = None, order_no: str | None = None) -> dict:
    """提取订单号并查询订单。

    优先用意图识别出的 order_no，否则从 user_query 里正则兜底提取。
    返回包含 orderNo / des / userId 的订单信息字典。

    Args:
        user_query: 用户原始输入，可能包含订单号。
        order_no: 已识别的订单号（可选，优先级更高）。
    """
    order_no = order_no or _extract_order_no(user_query)
    return _search_order(order_no)
