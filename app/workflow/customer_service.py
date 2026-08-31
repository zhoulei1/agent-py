"""客服入口工作流：意图识别 -> 条件分发，对应旧项目 CustomerServiceWorkflow / AgentFlowConfig。

使用 LangGraph 的 StateGraph 表达「意图识别 -> 按意图分发」：

    START -> classify(意图识别) -> 条件边
                ├─ PRODUCT_CONSULT -> product_consult -> END
                ├─ QUERY_ORDER     -> order           -> END
                ├─ COMPLAINT       -> complaint       -> END
                └─ UNKNOWN/其它    -> fallback        -> END
"""

import logging
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.workflow.intents import Intent

logger = logging.getLogger(__name__)

# 兜底文案：与旧版 AgentFlowConfig.FALLBACK_ANSWER 一致
_FALLBACK_ANSWER = "抱歉，暂时无法理解您的需求，请重新输入或补充更多信息。"


class WorkflowState(TypedDict):
    """工作流状态：节点之间传递的数据。"""

    conversation_id: str
    user_query: str
    user_id: str | None
    intent: str   # 意图分类结果
    answer: str   # 最终回答


class CustomerServiceWorkflow:
    """客服工作流（LangGraph 实现），对上层（AiService）提供 chat() 入口。"""

    def __init__(self, intent_classifier, product_consult_agent, order_agent, complaint_agent, memory_store):
        self._intent_classifier = intent_classifier
        self._product_consult_agent = product_consult_agent
        self._order_agent = order_agent
        self._complaint_agent = complaint_agent
        self._memory_store = memory_store
        # 图只编译一次，之后每次请求复用
        self._graph = self._build_graph()

    # ---------- 图结构 ----------
    def _build_graph(self):
        graph = StateGraph(WorkflowState)

        # 节点
        graph.add_node("classify", self._classify)
        graph.add_node("product_consult", self._product_consult)
        graph.add_node("order", self._order)
        graph.add_node("complaint", self._complaint)
        graph.add_node("fallback", self._fallback)

        # 边：入口 -> 意图识别 -> 条件分发 -> 各分支 -> 结束
        graph.add_edge(START, "classify")
        graph.add_conditional_edges(
            "classify",
            self._route,
            {
                "product_consult": "product_consult",
                "order": "order",
                "complaint": "complaint",
                "fallback": "fallback",
            },
        )
        graph.add_edge("product_consult", END)
        graph.add_edge("order", END)
        graph.add_edge("complaint", END)
        graph.add_edge("fallback", END)

        return graph.compile()

    # ---------- 节点 ----------
    async def _classify(self, state: WorkflowState) -> dict:
        """意图识别：把分类结果写入状态。"""
        intent = await self._intent_classifier.classify(state["user_query"])
        logger.info("[工作流] 意图识别结果：intent=%s", intent.value)
        return {"intent": intent.value}

    def _route(self, state: WorkflowState) -> str:
        """条件分发：根据 intent 返回下一个节点名。"""
        intent = Intent.parse(state.get("intent", ""))
        if intent == Intent.PRODUCT_CONSULT:
            logger.info("[工作流] 进入「产品咨询」分支（RAG + 记忆 + 工具）")
            return "product_consult"
        if intent == Intent.QUERY_ORDER:
            logger.info("[工作流] 进入「订单查询」分支")
            return "order"
        if intent == Intent.COMPLAINT:
            logger.info("[工作流] 进入「售后投诉」分支")
            return "complaint"
        logger.info("[工作流] 进入「兜底」分支（意图未知 / 转人工）")
        return "fallback"

    async def _product_consult(self, state: WorkflowState) -> dict:
        answer = await self._product_consult_agent.answer(state["conversation_id"], state["user_query"])
        return {"answer": answer or _FALLBACK_ANSWER}

    async def _order(self, state: WorkflowState) -> dict:
        answer = await self._order_agent.answer(state["user_query"])
        return {"answer": answer or _FALLBACK_ANSWER}

    async def _complaint(self, state: WorkflowState) -> dict:
        answer = await self._complaint_agent.answer(state["user_query"])
        return {"answer": answer or _FALLBACK_ANSWER}

    def _fallback(self, state: WorkflowState) -> dict:
        return {"answer": _FALLBACK_ANSWER}

    # ---------- 入口 ----------
    async def chat(self, conversation_id: str, user_query: str, user_id: str | None) -> str:
        """处理一轮用户提问，返回最终回答文本。"""
        result = await self._graph.ainvoke(
            {
                "conversation_id": conversation_id,
                "user_query": user_query,
                "user_id": user_id,
                "intent": "",
                "answer": "",
            }
        )
        answer = result.get("answer") or _FALLBACK_ANSWER

        # 持久化 chat memory（与旧版一致：只有产品咨询分支使用 memory）
        if Intent.parse(result.get("intent", "")) == Intent.PRODUCT_CONSULT:
            await self._memory_store.append_turn(conversation_id, user_query, answer)

        return answer
