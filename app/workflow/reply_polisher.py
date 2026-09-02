"""回复润色器 + 兜底提示，供各工作流复用。

把各分支的「原始结果」统一润色成友好客服话术（LLM），
以及未知意图的兜底提示。产品咨询等已润色的分支可跳过润色。
"""

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from app.workflow.llm_logger import llm_logging_handler

logger = logging.getLogger(__name__)

# 未知意图的兜底文案（与旧版 AgentFlowConfig.FALLBACK_ANSWER 一致）
FALLBACK_ANSWER = "抱歉，暂时无法理解您的需求，请重新输入或补充更多信息。"


class ReplyPolisher:
    """把原始结果润色成友好话术（LLM），并负责未知意图兜底。"""

    def __init__(self, chat_model):
        self._chat_model = chat_model

    async def polish(self, system_prompt: str, content: str) -> str:
        """用 LLM 按 system_prompt 把 content 润色成友好话术。"""
        logger.info("[润色] 开始润色回复")
        response = await self._chat_model.ainvoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=content)],
            config={"callbacks": [llm_logging_handler]},
        )
        return response.content or ""

    def fallback(self) -> str:
        """未知意图兜底提示。"""
        return FALLBACK_ANSWER
