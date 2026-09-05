"""
修复版 - 端点路径修正
"""

import httpx
import os
import asyncio
import json


class DebugMCPClient:
    """修复后的 MCP 客户端"""

    def __init__(self, endpoint: str, api_key: str):
        self.endpoint = endpoint
        self.session_id = None
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def _request(self, method: str, params: dict = None):
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
        }
        if params:
            body["params"] = params

        req_headers = {}
        if self.session_id:
            req_headers["Mcp-Session-Id"] = self.session_id

        print(f"\n{'='*60}")
        print(f"📤 请求 URL: {self.endpoint}")
        print(f"📤 请求方法: {method}")
        print(f"📤 请求体: {json.dumps(body, indent=2, ensure_ascii=False)}")

        # ⚠️ 关键修复：直接用 endpoint，不用 base_url
        resp = await self.client.post(self.endpoint, json=body, headers=req_headers)

        print(f"\n📥 状态码: {resp.status_code}")
        print(f"📥 Content-Type: {resp.headers.get('content-type')}")
        print(f"📥 原始内容 (前500字符): {resp.text[:500]}")

        sid = resp.headers.get("mcp-session-id")
        if sid:
            self.session_id = sid

        # 尝试解析 JSON
        if resp.text.strip():
            return resp.json()
        else:
            return {"error": "empty response", "status_code": resp.status_code}

    async def initialize(self):
        result = await self._request("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "debug-client", "version": "1.0.0"}
        })
        return result

    async def list_tools(self):
        return await self._request("tools/list")

    async def call_tool(self, name: str, arguments: dict):
        return await self._request("tools/call", {
            "name": name,
            "arguments": arguments
        })

    async def close(self):
        await self.client.aclose()


async def main():
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("❌ 请设置环境变量 DASHSCOPE_API_KEY")
        return

    client = DebugMCPClient(
        "https://dashscope.aliyuncs.com/api/v1/mcps/market-cmgjmcp00074946/mcp",
        api_key
    )

    try:
        # 1. 初始化
        result = await client.initialize()
        print(f"\n🔍 解析结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

        if "result" in result:
            print("\n✅ 初始化成功！")
            # 2. 列出工具
            tools = await client.list_tools()
            print(f"\n📦 工具列表: {json.dumps(tools, indent=2, ensure_ascii=False)}")

    finally:
        await client.close()


if __name__ == "__main__":
    api_key = os.getenv("DASHSCOPE_API_KEY")
    print(api_key)
    asyncio.run(main())