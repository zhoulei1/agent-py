"""售后投诉分支，对应旧项目 ComplaintAgent。"""

import logging

from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

# 系统提示词：与旧版 ComplaintAgent 的 @SystemMessage 一致
_SYSTEM_PROMPT = "你是客服投诉处理助手，安抚用户情绪、提取投诉要点，并给出受理答复话术。"


class ComplaintAgent:
    """处理投诉 / 售后 / 退款 / 维权类问题。"""

    def __init__(self, chat_model):
        self._chat_model = chat_model

    async def answer(self, user_query: str) -> str:
        logger.info("[售后投诉] 生成受理话术")
        response = await self._chat_model.ainvoke(
            [
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(content=f"用户投诉：{user_query}"),
            ]
        )
        return response.content or ""
