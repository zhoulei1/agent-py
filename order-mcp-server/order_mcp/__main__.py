"""运行入口。

用法：
    python -m order_mcp                          # 推荐：在 order-mcp-server 目录下
    python order_mcp/__main__.py                 # 或直接运行脚本文件
    python -m order_mcp --port 8001
    python -m order_mcp --transport stdio        # 以子进程方式运行（主应用拉起）
"""

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    # 直接以脚本方式运行时没有包上下文，把项目根目录加入 sys.path，
    # 保证下面的 `order_mcp` 绝对导入能命中。
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from order_mcp.server import server


def main() -> None:
    parser = argparse.ArgumentParser(description="订单查询 MCP 服务")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址（http 传输时生效）")
    parser.add_argument("--port", type=int, default=8000, help="监听端口（http 传输时生效）")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="streamable-http",
        help="传输方式，默认 streamable-http",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        server.run(transport="stdio")
    elif args.transport == "sse":
        server.run(transport="sse", host=args.host, port=args.port)
    else:
        server.run(transport="streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
