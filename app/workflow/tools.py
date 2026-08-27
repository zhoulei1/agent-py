"""客服工具，对应旧项目 tools/PhonePriceTool。"""

import zlib

from langchain_core.tools import tool


@tool
def query_last_year_min_price(phone_name: str) -> float | None:
    """查询手机去年的最低价格。

    Args:
        phone_name: 手机型号名称，例如「阿里云百炼X1」。
    """
    # 复刻旧版 PhonePriceTool 的演示逻辑：
    #   阿里云百炼X1 -> None；其余型号 -> 用型号名算一个确定性的演示价格
    if phone_name == "阿里云百炼X1":
        return None
    return float(zlib.crc32(phone_name.encode("utf-8")))
