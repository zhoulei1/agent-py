"""客服入口工作流：意图识别 -> 条件分发 -> 生成回答。

使用 LangGraph 的 StateGraph 表达：

    START -> recognize(意图+参数) -> 条件边
                ├─ PRODUCT_CONSULT -> product_consult -> END     （回答已润色）
                ├─ QUERY_ORDER     -> order -> polish -> END     （原始订单结果 -> 润色）
                ├─ COMPLAINT       -> complaint -> polish -> END （投诉内容 -> 润色）
                └─ UNKNOWN/其它    -> fallback -> END            （兜底提示）
"""

import logging
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.workflow.intents import Intent

logger = logging.getLogger(__name__)

_FALLBACK_ANSWER = "抱歉，暂时无法理解您的需求，请重新输入或补充更多信息。"


class WorkflowState(TypedDict):
    """工作流状态：节点之间传递的数据。"""

    conversation_id: str
    user_query: str
    user_id: str | None
    intent: str
    order_no: str | None    # 意图识别提取的订单号
    complaint: str | None   # 意图识别提取的投诉要点
    raw_result: str         # 待润色的原始结果（订单/投诉）
    answer: str             # 最终回答


class CustomerServiceWorkflow:
    """客服工作流（LangGraph 实现），对上层（AiService）提供 chat() 入口。"""

    def __init__(self, intent_recognizer, product_consult_agent, order_agent, polisher, memory_store):
        self._intent_recognizer = intent_recognizer
        self._product_consult_agent = product_consult_agent
        self._order_agent = order_agent
        self._polisher = polisher
        self._memory_store = memory_store
        self._graph = self._build_graph()

    # ---------- 图结构 ----------
    def _build_graph(self):
        graph = StateGraph(WorkflowState)

        graph.add_node("recognize", self._recognize)
        graph.add_node("product_consult", self._product_consult)
        graph.add_node("order", self._order)
        graph.add_node("complaint", self._complaint)
        graph.add_node("polish", self._polish)
        graph.add_node("fallback", self._fallback)

        graph.add_edge(START, "recognize")
        graph.add_conditional_edges(
            "recognize",
            self._route,
            {
                "product_consult": "product_consult",
                "order": "order",
                "complaint": "complaint",
                "fallback": "fallback",
            },
        )
        # 产品咨询已润色，直接结束；订单/投诉走润色节点后结束
        graph.add_edge("product_consult", END)
        graph.add_edge("order", "polish")
        graph.add_edge("complaint", "polish")
        graph.add_edge("polish", END)
        graph.add_edge("fallback", END)

        return graph.compile()

    # ---------- 节点 ----------
    async def _recognize(self, state: WorkflowState) -> dict:
        """意图识别 + 参数提取，结果写入状态。"""
        result = await self._intent_recognizer.recognize(state["user_query"])
        logger.info("[工作流] 意图识别结果：intent=%s", result.intent.value)
        return {"intent": result.intent.value, "order_no": result.order_no, "complaint": result.complaint}

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

    def _order(self, state: WorkflowState) -> dict:
        """查询订单（纯逻辑），结果交给润色节点。"""
        order = self._order_agent.lookup(state["user_query"], state.get("order_no"))
        logger.info("[工作流] 订单查询结果：order_no=%s", order.orderNo)
        return {"order_no": order.orderNo, "raw_result": order.model_dump_json()}

    def _complaint(self, state: WorkflowState) -> dict:
        """整理投诉内容（优先用意图识别提取的要点），结果交给润色节点。"""
        raw = state.get("complaint") or state["user_query"]
        return {"raw_result": raw}

    async def _polish(self, state: WorkflowState) -> dict:
        """把订单/投诉的原始结果润色成友好话术。"""
        intent = Intent.parse(state.get("intent", ""))
        if intent == Intent.QUERY_ORDER:
            answer = await self._polisher.polish(
                "把订单对象信息整理成友好客服话术返回给用户",
                f"用户问题：{state['user_query']}，订单信息：{state['raw_result']}",
            )
        elif intent == Intent.COMPLAINT:
            answer = await self._polisher.polish(
                "你是客服投诉处理助手，安抚用户情绪、提取投诉要点，并给出受理答复话术。",
                f"用户投诉：{state['raw_result']}",
            )
        else:
            answer = state.get("raw_result") or _FALLBACK_ANSWER
        return {"answer": answer or _FALLBACK_ANSWER}

    def _fallback(self, state: WorkflowState) -> dict:
        return {"answer": self._polisher.fallback()}

    # ---------- 入口 ----------
    async def chat(self, conversation_id: str, user_query: str, user_id: str | None) -> str:
        """处理一轮用户提问，返回最终回答文本。"""
        result = await self._graph.ainvoke(
            {
                "conversation_id": conversation_id,
                "user_query": user_query,
                "user_id": user_id,
                "intent": "",
                "order_no": None,
                "complaint": None,
                "raw_result": "",
                "answer": "",
            }
        )
        answer = result.get("answer") or _FALLBACK_ANSWER

        # 持久化 chat memory（与旧版一致：只有产品咨询分支使用 memory）
        if Intent.parse(result.get("intent", "")) == Intent.PRODUCT_CONSULT:
            await self._memory_store.append_turn(conversation_id, user_query, answer)

        return answer
