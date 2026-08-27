"""会话（Conversation）的 MongoDB 持久化，对应旧项目 ConversationService。"""

import logging
import uuid
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models import Conversation

logger = logging.getLogger(__name__)


class ConversationService:
    """封装 conversation 集合的增删改查。

    - 使用 motor 的异步 API（await）
    - 时间字段在入库时序列化为 ISO 字符串，读回时由 Pydantic 自动解析回 datetime
    """

    COLLECTION = "conversation"

    def __init__(self, db: AsyncIOMotorDatabase):
        self._collection = db[self.COLLECTION]

    async def save(self, conversation: Conversation) -> Conversation:
        """新建会话：生成 conversationId 与时间戳后写入。"""
        conversation.conversationId = uuid.uuid4().hex  # 32 位无横线 UUID
        now = datetime.now(timezone.utc)
        conversation.createTime = now
        conversation.updateTime = now

        # mode="json"：datetime -> ISO 字符串，enum -> 字符串，直接入库
        await self._collection.insert_one(conversation.model_dump(mode="json"))
        logger.info("[会话] 保存会话：conversationId=%s", conversation.conversationId)
        return conversation

    async def list_by_user(self, user_id: str) -> list[Conversation]:
        """按用户列出会话，创建时间倒序（对应旧版 sort DESC createTime）。"""
        cursor = self._collection.find({"userId": user_id}).sort("createTime", -1)
        return [Conversation.model_validate(doc) async for doc in cursor]

    async def get_by_id(self, conversation_id: str) -> Conversation | None:
        doc = await self._collection.find_one({"conversationId": conversation_id})
        return Conversation.model_validate(doc) if doc else None

    async def update_name(self, conversation_id: str, conversation_name: str) -> None:
        """重命名会话，并刷新更新时间。"""
        await self._collection.update_one(
            {"conversationId": conversation_id},
            {"$set": {
                "conversationName": conversation_name,
                "updateTime": datetime.now(timezone.utc).isoformat(),
            }},
        )
        logger.info("[会话] 重命名会话：conversationId=%s", conversation_id)

    async def delete(self, conversation_id: str) -> None:
        await self._collection.delete_one({"conversationId": conversation_id})
        logger.info("[会话] 删除会话：conversationId=%s", conversation_id)
