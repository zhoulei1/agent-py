"""数据模型（Pydantic）。

注意：为了与旧项目 AiController 的 JSON 输出、以及前端 agent-front/src/types/index.ts
完全对齐，这里的字段名刻意使用 camelCase（如 conversationId），而不是 Python 惯例的
snake_case。这是有意为之，请不要改成下划线命名，否则前端会拿不到字段。
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


def _now() -> datetime:
    """统一的创建时间戳（UTC）。"""
    return datetime.now(timezone.utc)


class ChatMessageType(str, Enum):
    """消息角色。旧项目只会写入 USER / AI 两种（其余为 langchain4j 的枚举值）。"""

    USER = "USER"
    AI = "AI"
    SYSTEM = "SYSTEM"
    TOOL_EXECUTION_RESULT = "TOOL_EXECUTION_RESULT"
    CUSTOM = "CUSTOM"


class QueryVo(BaseModel):
    """前端发送聊天请求时的请求体，对应旧项目 pojo/QueryVo。"""

    message: str
    conversationId: str
    userId: Optional[str] = None


class Conversation(BaseModel):
    """会话，对应旧项目 entity/Conversation，持久化到 MongoDB 的 conversation 集合。

    注意：conversationId 设为可选 —— 前端「新建会话」时只传 conversationName，
    由后端在保存时生成 conversationId；重命名 / 删除时才会带上 conversationId。
    """

    userId: Optional[str] = None
    conversationId: Optional[str] = None
    conversationName: Optional[str] = None
    createTime: Optional[datetime] = None
    updateTime: Optional[datetime] = None

    # 允许从字符串解析时间（从 Mongo 读回时 createTime 可能是字符串）
    model_config = ConfigDict(populate_by_name=True)


class ChatMessage(BaseModel):
    """一条聊天消息，对应旧项目 entity/ChatMessage，持久化到 MongoDB 的 chatMessage 集合。"""

    messageId: Optional[str] = None
    conversationId: str
    userId: Optional[str] = None
    messageText: Optional[str] = None
    chatMessageType: ChatMessageType
    createTime: Optional[datetime] = None

    model_config = ConfigDict(populate_by_name=True)


class ChatMemoryMessage(BaseModel):
    """Redis chat memory 里的一条消息（仅内部使用，字段与前端无关）。"""

    role: str  # user / assistant
    content: str


class OrderDTO(BaseModel):
    """订单信息，对应旧项目 pojo/OrderDTO，在工作流内传递。"""

    orderNo: Optional[str] = None
    des: Optional[str] = None
    userId: Optional[str] = None
