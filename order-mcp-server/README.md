# order-mcp-server

订单查询 MCP 服务，从 `agent-py` 的 `app/workflow/order.py`（OrderAgent）剥离出来的独立服务。

- 暴露一个 MCP 工具 `lookup_order(user_query, order_no)`：提取订单号 -> 查询订单，返回 `{orderNo, des, userId}`。
- 纯逻辑，不依赖主应用（`app.models` / `app.config` 等），可单独部署、单独扩容。
- 话术润色仍由主应用的 `ReplyPolisher` 负责。

## 运行

```bash
# 在 order-mcp-server 目录下（或用 `pip install -e .` 后直接 `order-mcp`）
python -m order_mcp                     # Streamable HTTP，默认 http://127.0.0.1:8000/mcp
python -m order_mcp --port 8001
python -m order_mcp --transport stdio   # 子进程方式
```

主应用通过环境变量 `ORDER_MCP_URL` 指定该服务地址（默认 `http://127.0.0.1:8000/mcp`）。
