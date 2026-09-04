"""订单查询 MCP 客户端：通过 Streamable HTTP 调用独立的 order-mcp-server。

对上层（CustomerServiceWorkflow）保持与原 OrderAgent 相同的 lookup() 接口，
只是底层从本地纯逻辑改为远程 MCP 工具调用。
"""

import json
import logging
from contextlib import AsyncExitStack

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.models import OrderDTO

logger = logging.getLogger(__name__)

# MCP 服务端暴露的工具名（见 order-mcp-server/order_mcp/server.py）
_LOOKUP_TOOL = "lookup_order"


class OrderMCPClient:
    """订单查询客户端，通过 MCP（Streamable HTTP）调用独立订单服务。"""

    def __init__(self, url: str):
        self._url = url

    async def lookup(self, user_query: str | None, order_no: str | None = None) -> OrderDTO:
        """提取订单号并查询订单，返回 OrderDTO。

        每次调用建立一条独立 MCP 连接（简单可靠）；后续如需高频调用可改为复用会话/连接池。
        """
        async with AsyncExitStack() as stack:
            read, write = await stack.enter_async_context(streamable_http_client(self._url))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            result = await session.call_tool(
                _LOOKUP_TOOL,
                {"user_query": user_query, "order_no": order_no},
            )

        # 工具返回 dict，SDK 会序列化成 JSON 文本放在首个 content 块
        text = result.content[0].text
        data = json.loads(text)
        return OrderDTO(**data)
