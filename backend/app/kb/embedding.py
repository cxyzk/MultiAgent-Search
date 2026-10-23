"""Embedding：批量文本向量化（OpenAI 兼容接口，默认硅基流动 bge-m3）。

- 惰性创建 client：没配 key 时（CI / 测试）不会在 import 阶段炸
- 分批调用：单次 input 有上限，16 条一批
- 失败向上抛，由调用方决定是否降级
"""
from openai import AsyncOpenAI

from app.core.config import settings

BATCH_SIZE = 16

_client: AsyncOpenAI | None = None


def embedding_enabled() -> bool:
    return bool(settings.embedding_api_key)


def _client_instance() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            base_url=settings.embedding_base_url,
            api_key=settings.embedding_api_key,
        )
    return _client


async def embed(texts: list[str]) -> list[list[float]]:
    """批量向量化，返回与输入等长的向量列表。"""
    if not texts:
        return []
    out: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        resp = await _client_instance().embeddings.create(
            model=settings.embedding_model,
            input=texts[i:i + BATCH_SIZE],
        )
        out.extend(item.embedding for item in resp.data)
    return out
