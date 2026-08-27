"""用户意图枚举，对应旧项目 annotation/UserIntent。"""

from enum import Enum


class Intent(str, Enum):
    """客服意图分类。

    - PRODUCT_CONSULT：产品 / 业务咨询
    - QUERY_ORDER：查询订单 / 物流
    - COMPLAINT：投诉 / 售后 / 退款 / 维权
    - UNKNOWN：无法识别或要求转人工
    """

    PRODUCT_CONSULT = "PRODUCT_CONSULT"
    QUERY_ORDER = "QUERY_ORDER"
    COMPLAINT = "COMPLAINT"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def parse(cls, value: str | None) -> "Intent":
        """把 LLM 返回的字符串解析成 Intent，解析失败归为 UNKNOWN。"""
        if value is None:
            return cls.UNKNOWN
        text = str(value).strip().upper()
        for intent in cls:
            if intent.value == text:
                return intent
        return cls.UNKNOWN

    def is_known(self) -> bool:
        """是否属于可识别的意图（排除 UNKNOWN）。对应旧版 isKnownIntent。"""
        return self in (Intent.PRODUCT_CONSULT, Intent.QUERY_ORDER, Intent.COMPLAINT)
