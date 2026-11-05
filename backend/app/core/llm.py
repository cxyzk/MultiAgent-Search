"""LLM 客户端：全进程共用一个 AsyncOpenAI 实例，复用底层连接池。

- 懒创建：没配 key 时不会在 import 阶段炸（CI / 测试）
- 正式对话（loop）和查询改写（query_rewrite）共用这一份连接池；
  两者超时需求不同，由调用方用 `with_options(...)` 派生——它复用同一个
  httpx client，只覆盖 timeout / max_retries，不会新建连接池

放 core 而不是 agent：消费方跨两个包（agent/loop.py 与 kb/query_rewrite.py），
而 agent 本身经 tools/kb_search 依赖 kb。若放在 agent 下，kb 会反向依赖 agent
形成包级环——实测只要 app/agent/__init__.py 加一行聚合 import 就会
ImportError（partially initialized module）。core 是叶子层（只依赖 config），
两个包都单向指向它，不存在这个问题。
"""
from openai import AsyncOpenAI

from app.core.config import settings

_client: AsyncOpenAI | None = None


def get_llm_client() -> AsyncOpenAI:
    """同步懒创建：函数体内没有 await，协程不会在此被切走，所以免锁。"""
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
        )
    return _client


async def close_llm_client() -> None:
    """进程退出时收尾，由 lifespan 在 yield 之后调用。"""
    global _client
    if _client is not None:
        await _client.close()
        _client = None
