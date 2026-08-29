"""LLM 交互日志回调：统一记录每次与大模型交互的请求与返回。

实现方式：LangChain 的回调（BaseCallbackHandler）。各 Agent 在调用模型时
通过 config={"callbacks": [llm_logging_handler]} 传入，即可自动记录，
无需在每个调用点手动写日志。
"""

import logging

from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger(__name__)


class LLMLoggingHandler(BaseCallbackHandler):
    """记录 LLM 的请求（prompts）与返回（文本 / 工具调用）。"""

    def on_llm_start(self, serialized, prompts, **kwargs):
        """模型调用开始：打印发送给模型的请求内容。"""
        for prompt in prompts:
            logger.info("[LLM 请求]\n%s", prompt)

    def on_llm_end(self, response, **kwargs):
        """模型调用结束：打印模型返回的内容。"""
        for generations in response.generations:
            for generation in generations:
                message = getattr(generation, "message", None)
                # 返回的是工具调用（而非纯文本）时，打印工具调用信息
                if message is not None and getattr(message, "tool_calls", None):
                    logger.info("[LLM 返回] 工具调用: %s", message.tool_calls)
                else:
                    text = getattr(generation, "text", "") or str(generation)
                    logger.info("[LLM 返回]\n%s", text)

    def on_llm_error(self, error, **kwargs):
        """模型调用出错。"""
        logger.error("[LLM 错误] %s", error)


# 全局单例，供各 Agent 在 invoke 时通过 config 传入
llm_logging_handler = LLMLoggingHandler()
