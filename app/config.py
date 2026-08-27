"""集中管理所有配置项。

使用 pydantic-settings，配置来源优先级：
    环境变量 > .env 文件 > 代码里的默认值

字段名采用「大写蛇形」命名，例如 qianwen.api-key 对应环境变量 QIANWEN_API_KEY。
默认值与旧项目 application.properties 保持一致，便于对照。
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（config.py 位于 app/ 下，往上一级即项目根）
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resolve_path(path: str) -> str:
    """把配置里的相对路径解析为基于项目根目录的绝对路径（返回字符串）。

    例如 "resources/embedding/init.txt" -> "D:/gitwork/agent-py/resources/embedding/init.txt"。
    已经是绝对路径时原样返回。
    """
    p = Path(path)
    return str(p if p.is_absolute() else PROJECT_ROOT / p)


class Settings(BaseSettings):
    """应用配置。每个字段都有默认值，可在 .env 或环境变量中覆盖。"""

    # ---------- 千问（Qwen）大模型，OpenAI 兼容端点，作为主聊天模型 ----------
    qianwen_api_key: str = ""
    qianwen_model_name: str = "qwen3.7-plus"
    qianwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # ---------- DeepSeek（保留配置，默认不启用，仅作备用） ----------
    deepseek_api_key: str = ""
    deepseek_model_name: str = "deepseek-v4-flash"
    deepseek_base_url: str = "https://api.deepseek.com"

    # ---------- MongoDB（会话 / 消息持久化） ----------
    mongodb_uri: str = "mongodb://localhost:27017/ai"

    # ---------- Redis（chat memory 持久化） ----------
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_database: int = 0

    # ---------- Qdrant（向量库） ----------
    # 注意：这里走 HTTP REST 接口（默认 6333）。
    # Qdrant 的 gRPC 端口是 6334，但新版 qdrant-client 走 gRPC 与 Qdrant 1.16 存在兼容问题，
    # 故统一使用 HTTP，更稳定。
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_use_tls: bool = False
    qdrant_api_key: str = ""
    qdrant_collection_name: str = "bge_small_zh_512"
    # 检索阈值：旧项目写的是 0.8，但实测相关结果余弦分数约 0.80（刚好卡在边界），
    # 0.8 会把最相关的结果也过滤掉，这里默认放宽到 0.7 让检索可用。
    qdrant_min_score: float = 0.7
    qdrant_max_results: int = 5

    # ---------- 本地 ONNX 向量模型（bge-small-zh） ----------
    embedding_model_path: str = "resources/onnx/bge-small-zh/bge-small-zh-v1.5.onnx"
    embedding_tokenizer_path: str = "resources/onnx/bge-small-zh/bge-small-zh-v1.5-tokenizer.json"
    embedding_pooling_mode: str = "CLS"

    # 让 pydantic-settings 自动读取项目根目录下的 .env 文件（环境变量优先）
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """返回全局唯一的 Settings 实例（带缓存，避免重复解析 .env）。"""
    return Settings()
