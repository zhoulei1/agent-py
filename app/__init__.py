"""客服 Agent 后端应用包。

对外接口与旧项目 AiController 保持一致（/ai/*），前端无需改动即可对接。
"""

from .application import create_app

__all__ = ["create_app"]
