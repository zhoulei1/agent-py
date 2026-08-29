"""产品咨询分支：RAG 检索 + chat memory + 工具调用。

对应旧项目 ProductConsultAgent（走 contentRetriever + chatMemory + phonePriceTool）。
"""

import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.workflow.llm_logger import llm_logging_handler

logger = logging.getLogger(__name__)

# 系统提示词：与旧版 ProductConsultAgent 的 @SystemMessage 一致
_SYSTEM_PROMPT = "产品咨询客服，给客户提供产品信息，回答要求简单明了。"


class ProductConsultAgent:
    """回答产品 / 业务咨询，需要时调用工具（如手机价格查询）。"""

    def __init__(self, chat_model, retriever, memory_store, tools):
        self._chat_model = chat_model
        self._retriever = retriever
        self._memory_store = memory_store
        self._tools = tools or []
        # 有工具就绑定，让模型回答过程中可以调用；没有就当成普通聊天
        self._model = chat_model.bind_tools(self._tools) if self._tools else chat_model
        self._tools_by_name = {t.name: t for t in self._tools}

    async def answer(self, conversation_id: str, user_query: str) -> str:
        """处理一轮产品咨询，返回最终回答文本。"""
        # 1. 读取历史会话
        history = await self._memory_store.get_messages(conversation_id)

        # 2. RAG 检索知识片段
        context = await self._retrieve(user_query)

        # 3. 组装消息：系统提示词（含知识上下文） -> 历史 -> 当前问题
        messages = [SystemMessage(content=self._system_prompt(context))]
        for m in history:
            messages.append(
                HumanMessage(content=m.content) if m.role == "user" else AIMessage(content=m.content)
            )
        messages.append(HumanMessage(content=user_query))

        # 4. 调用模型；若模型请求调用工具，执行工具后把结果回传，再让模型生成最终回答
        response = await self._model.ainvoke(messages, config={"callbacks": [llm_logging_handler]})
        while response.tool_calls:
            messages.append(response)
            for call in response.tool_calls:
                result = await self._execute_tool(call)
                messages.append(ToolMessage(content=str(result), tool_call_id=call.get("id", "")))
            response = await self._model.ainvoke(messages, config={"callbacks": [llm_logging_handler]})

        return response.content or ""

    @staticmethod
    def _system_prompt(context: str) -> str:
        """把检索到的上下文拼进系统提示词；没有上下文时只返回基础提示词。"""
        if not context:
            return _SYSTEM_PROMPT
        return f"{_SYSTEM_PROMPT}\n\n参考以下产品信息回答：\n{context}"

    async def _retrieve(self, user_query: str) -> str:
        """RAG 检索；失败时返回空上下文，不影响正常回答。"""
        try:
            docs = await self._retriever.ainvoke(user_query)
            logger.info("[产品咨询] RAG 检索命中 %d 条知识片段", len(docs))
            return "\n\n".join(d.page_content for d in docs)
        except Exception:
            logger.exception("RAG 检索失败，忽略上下文继续回答")
            return ""

    async def _execute_tool(self, call: dict) -> str:
        """执行一次工具调用，返回结果文本。"""
        name = call.get("name")
        args = call.get("args", {})
        tool = self._tools_by_name.get(name)
        if tool is None:
            return f"工具 {name} 不存在"
        result = await tool.ainvoke(args)
        return "未查询到该手机的价格" if result is None else str(result)
