"""Redis 持久化的 chat memory，对应旧项目 CustomChatMemoryStore。

存储约定：
    key   = "chat:memory:{conversationId}"
    value = json 字符串，形如 [{"role":"user","content":"..."}, {"role":"assistant","content":"..."}]

只保留最近 N 条消息（滑动窗口），与旧项目 MessageWindowChatMemory.maxMessages(3) 对应。
"""

import json
import logging

from redis.asyncio import Redis

from app.models import ChatMemoryMessage

logger = logging.getLogger(__name__)


class RedisChatMemoryStore:
    """把对话历史存进 Redis，供产品咨询分支加载上下文使用。"""

    KEY_PREFIX = "chat:memory:"
    DEFAULT_MAX_MESSAGES = 3  # 与旧版 maxMessages(3) 一致

    def __init__(self, redis: Redis, max_messages: int = DEFAULT_MAX_MESSAGES):
        self._redis = redis
        self._max_messages = max_messages

    def _key(self, conversation_id: str) -> str:
        return f"{self.KEY_PREFIX}{conversation_id}"

    async def get_messages(self, conversation_id: str) -> list[ChatMemoryMessage]:
        """读取某个会话的历史消息；不存在或为空时返回空列表。"""
        raw = await self._redis.get(self._key(conversation_id))
        if not raw:
            return []
        # json 解析失败时兜底为空列表，避免历史数据损坏影响对话
        try:
            items = json.loads(raw)
            result = [ChatMemoryMessage.model_validate(item) for item in items]
            logger.info("[记忆] 读取历史：conversationId=%s, 条数=%d", conversation_id, len(result))
            return result
        except (json.JSONDecodeError, TypeError, ValueError):
            return []

    async def set_messages(self, conversation_id: str, messages: list[ChatMemoryMessage]) -> None:
        """整体覆盖保存（只保留最近 max_messages 条）。"""
        trimmed = messages[-self._max_messages:] if self._max_messages > 0 else []
        payload = json.dumps([m.model_dump(mode="json") for m in trimmed], ensure_ascii=False)
        await self._redis.set(self._key(conversation_id), payload)
        logger.info("[记忆] 保存历史：conversationId=%s, 条数=%d", conversation_id, len(trimmed))

    async def append_turn(self, conversation_id: str, user_text: str, ai_text: str) -> None:
        """追加一轮对话（一条用户消息 + 一条助手消息），并裁剪到窗口大小。"""
        history = await self.get_messages(conversation_id)
        history.append(ChatMemoryMessage(role="user", content=user_text))
        history.append(ChatMemoryMessage(role="assistant", content=ai_text))
        await self.set_messages(conversation_id, history)

    async def delete(self, conversation_id: str) -> None:
        """删除某个会话的 chat memory（对应旧版 deleteMessages）。"""
        await self._redis.delete(self._key(conversation_id))
        logger.info("[记忆] 删除历史：conversationId=%s", conversation_id)
