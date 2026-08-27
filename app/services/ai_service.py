"""AI 对话编排服务，对应旧项目 AiService。

职责：
    1. 保存用户消息
    2. 调用客服工作流（意图识别 -> 分发 -> 生成回答）
    3. 保存 AI 回复
"""

import logging

from app.models import ChatMessage, ChatMessageType, QueryVo
from app.services.chat_message_service import ChatMessageService
from app.workflow.customer_service import CustomerServiceWorkflow

logger = logging.getLogger(__name__)

# 回答为空时的兜底文案，与旧版 AiService 一致
_EMPTY_ANSWER = "抱歉，暂时无法处理您的请求，请稍后再试。"


class AiService:
    """聊天主流程（供 API 层调用）。"""

    def __init__(
        self,
        chat_message_service: ChatMessageService,
        workflow: CustomerServiceWorkflow,
    ):
        self._chat_message_service = chat_message_service
        self._workflow = workflow

    async def chat(self, query: QueryVo) -> str:
        """处理一轮聊天，返回 AI 回答文本。"""
        logger.info("[AiService] 第1步：保存用户消息")
        # 1. 保存用户消息
        await self._chat_message_service.save(
            ChatMessage(
                conversationId=query.conversationId,
                userId=query.userId,
                messageText=query.message,
                chatMessageType=ChatMessageType.USER,
            )
        )

        logger.info("[AiService] 第2步：调用客服工作流（意图识别->分发->回答）")
        # 2. 执行入口工作流
        answer = await self._workflow.chat(
            conversation_id=query.conversationId,
            user_query=query.message,
            user_id=query.userId,
        )
        if not answer:
            answer = _EMPTY_ANSWER
        logger.info("[AiService] 工作流完成，回答长度=%d", len(answer))

        logger.info("[AiService] 第3步：保存 AI 回复")
        # 3. 保存 AI 回复
        await self._chat_message_service.save(
            ChatMessage(
                conversationId=query.conversationId,
                userId=query.userId,
                messageText=answer,
                chatMessageType=ChatMessageType.AI,
            )
        )

        return answer
