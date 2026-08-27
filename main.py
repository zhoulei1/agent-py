"""程序入口：启动 FastAPI 应用。

用法（在项目根目录下）：
    uv run python main.py
或：
    python -m app
"""

import logging

import uvicorn

from app import create_app

# 统一配置日志：INFO 级别，带时间 / 级别 / 模块名，方便看清业务处理流程
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# 创建应用实例（配置、依赖、路由都在 create_app 里完成组装）
app = create_app()


if __name__ == "__main__":
    # host=0.0.0.0 便于本机 / 局域网访问；端口与旧项目保持一致（8080）
    uvicorn.run(app, host="0.0.0.0", port=8080)
