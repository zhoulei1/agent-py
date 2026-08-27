"""AI 相关接口，对应旧项目 AIController（/ai/*），路径与返回格式保持一致。

前端 agent-front 无需改动即可对接。
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.models import ChatMessage, Conversation, QueryVo

logger = logging.getLogger(__name__)

# 模拟登录用户（旧项目 getLoginUserId() 固定返回 "1"）
_LOGIN_USER_ID = "1"


def build_ai_router() -> APIRouter:
    """构建 /ai 路由。deps 从 request.app.state 取，便于依赖注入。"""
    router = APIRouter(prefix="/ai", tags=["ai"])

    def _deps(request: Request):
        return request.app.state.deps

    @router.post("/streamChat")
    async def stream_chat(request: Request, query: QueryVo) -> StreamingResponse:
        """流式聊天接口（SSE）。

        返回 text/event-stream，帧格式复刻 Spring WebFlux：
            data:{正文}\n\n  （正文里的换行拆成多行 data:）
        """
        deps = _deps(request)
        logger.info("[接口] streamChat 收到请求：conversationId=%s, message=%s", query.conversationId, query.message)
        answer = await deps.ai_service.chat(query)
        logger.info("[接口] streamChat 完成，回答长度=%d", len(answer))

        async def event_stream():
            yield _to_sse(answer)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    @router.get("/conversations", response_model=list[Conversation])
    async def list_conversations(request: Request) -> list[Conversation]:
        deps = _deps(request)
        result = await deps.conversation_service.list_by_user(_LOGIN_USER_ID)
        logger.info("[接口] 查询会话列表，数量=%d", len(result))
        return result

    @router.post("/conversation", response_model=Conversation)
    async def create_conversation(request: Request, conversation: Conversation) -> Conversation:
        deps = _deps(request)
        # 登录用户固定为 "1"，与旧项目一致
        conversation.userId = _LOGIN_USER_ID
        saved = await deps.conversation_service.save(conversation)
        logger.info("[接口] 新建会话：conversationId=%s", saved.conversationId)
        return saved

    @router.put("/conversation")
    async def rename_conversation(request: Request, conversation: Conversation) -> None:
        deps = _deps(request)
        logger.info("[接口] 重命名会话：conversationId=%s, name=%s", conversation.conversationId, conversation.conversationName)
        await deps.conversation_service.update_name(
            conversation.conversationId, conversation.conversationName or ""
        )

    @router.delete("/conversation/{conversation_id}")
    async def delete_conversation(request: Request, conversation_id: str) -> None:
        deps = _deps(request)
        logger.info("[接口] 删除会话：conversationId=%s", conversation_id)
        # 先删消息，再删会话，最后删 Redis memory（与旧版删除顺序一致）
        await deps.chat_message_service.delete_by_conversation(conversation_id)
        await deps.conversation_service.delete(conversation_id)
        await deps.memory_store.delete(conversation_id)

    @router.get("/chatMessages", response_model=list[ChatMessage])
    async def list_chat_messages(request: Request, conversationId: str) -> list[ChatMessage]:
        deps = _deps(request)
        result = await deps.chat_message_service.list_by_conversation(conversationId)
        logger.info("[接口] 查询会话消息：conversationId=%s, 数量=%d", conversationId, len(result))
        return result

    return router


def _to_sse(text: str) -> str:
    """把正文编码成 SSE 帧（复刻 Spring WebFlux 的编码规则）。

    Spring 规则：每个换行拆成一行 data:（冒号后无空格），帧末尾以空行结束。
    前端 sseParser.ts 会把这些 data: 行再按换行拼回原文。
    """
    lines = text.split("\n")
    data_lines = "".join(f"data:{line}\n" for line in lines)
    return f"{data_lines}\n"
