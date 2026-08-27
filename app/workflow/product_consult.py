"""产品咨询分支：RAG 检索 + chat memory + 工具调用。

对应旧项目 ProductConsultAgent（走 contentRetriever + chatMemory + phonePriceTool）。
"""

import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.services.redis_memory import RedisChatMemoryStore

logger = logging.getLogger(__name__)

# 系统提示词：与旧版 ProductConsultAgent 的 @SystemMessage 一致
_SYSTEM_PROMPT = "产品咨询客服，给客户提供产品信息，回答要求简单明了。"


class ProductConsultAgent:
    """回答产品 / 业务咨询，需要时调用工具（如手机价格查询）。"""

    def __init__(self, chat_model, retriever, memory_store: RedisChatMemoryStore, phone_price_tool):
        self._chat_model = chat_model
        self._retriever = retriever
        self._memory_store = memory_store
        # 绑定工具：模型可在回答过程中选择调用 phone_price_tool
        self._model_with_tools = chat_model.bind_tools([phone_price_tool])
        # 保存工具映射，便于根据工具名执行
        self._tools_by_name = {phone_price_tool.name: phone_price_tool}

    async def answer(self, conversation_id: str, user_query: str) -> str:
        """处理一轮产品咨询，返回最终回答文本。"""

        # 1. 从 Redis 加载历史会话（滑动窗口）
        history = await self._memory_store.get_messages(conversation_id)
        logger.info("[产品咨询] 加载历史：conversationId=%s, 历史条数=%d", conversation_id, len(history))

        # 2. RAG 检索相关知识片段
        try:
            docs = await self._retriever.ainvoke(user_query)
            context = "\n\n".join(d.page_content for d in docs) if docs else ""
            logger.info("[产品咨询] RAG 检索命中 %d 条知识片段", len(docs))
        except Exception:
            logger.exception("RAG 检索失败，忽略上下文继续回答")
            context = ""

        # 3. 组装消息：系统提示词（含知识库上下文） -> 历史 -> 当前问题
        system_text = _SYSTEM_PROMPT
        if context:
            system_text += f"\n\n可参考的产品信息：\n{context}"

        messages = [SystemMessage(content=system_text)]
        for m in history:
            if m.role == "user":
                messages.append(HumanMessage(content=m.content))
            else:
                messages.append(AIMessage(content=m.content))
        messages.append(HumanMessage(content=user_query))

        # 4. 调用模型；若模型请求调用工具，则执行工具后再次调用
        response = await self._model_with_tools.ainvoke(messages)
        while response.tool_calls:
            messages.append(response)
            for tool_call in response.tool_calls:
                # tool_call 是一个 dict，含 name / args / id（不同版本键名可能略有差异，做兜底）
                name = tool_call.get("name")
                args = tool_call.get("args", {})
                call_id = tool_call.get("id") or tool_call.get("tool_call_id") or ""

                tool = self._tools_by_name.get(name)
                logger.info("[产品咨询] 模型请求调用工具：name=%s, args=%s", name, args)
                if tool is None:
                    result = "未知工具"
                else:
                    result = await tool.ainvoke(args)
                    if result is None:
                        result = "未查询到该手机的价格"
                messages.append(ToolMessage(content=str(result), tool_call_id=call_id))
            response = await self._model_with_tools.ainvoke(messages)

        # 5. 返回纯文本回答
        return response.content or ""
