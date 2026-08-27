"""聊天消息（ChatMessage）的 MongoDB 持久化，对应旧项目 ChatMessageService。"""

import logging
import uuid
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models import ChatMessage

logger = logging.getLogger(__name__)


class ChatMessageService:
    """封装 chatMessage 集合的增删改查（异步）。"""

    COLLECTION = "chatMessage"

    def __init__(self, db: AsyncIOMotorDatabase):
        self._collection = db[self.COLLECTION]

    async def save(self, chat_message: ChatMessage) -> ChatMessage:
        """保存一条消息：生成 messageId 与创建时间后写入。"""
        chat_message.messageId = uuid.uuid4().hex
        chat_message.createTime = datetime.now(timezone.utc)
        await self._collection.insert_one(chat_message.model_dump(mode="json"))
        logger.info("[消息] 保存消息：type=%s, conversationId=%s", chat_message.chatMessageType.value, chat_message.conversationId)
        return chat_message

    async def list_by_conversation(self, conversation_id: str) -> list[ChatMessage]:
        """按会话列出消息，创建时间正序（对应旧版 sort ASC createTime）。"""
        cursor = self._collection.find({"conversationId": conversation_id}).sort("createTime", 1)
        return [ChatMessage.model_validate(doc) async for doc in cursor]

    async def delete_by_conversation(self, conversation_id: str) -> None:
        """删除某个会话下的全部消息。"""
        result = await self._collection.delete_many({"conversationId": conversation_id})
        logger.info("[消息] 删除会话消息：conversationId=%s, 删除数=%d", conversation_id, result.deleted_count)
