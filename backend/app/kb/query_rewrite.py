"""查询改写：把口语化问题改写成检索友好的短查询，提升召回。

设计：
- 只在 kb_search 工具入口做一次（不是每次检索都调），成本可控
- 任何失败都降级为 [原问题]，绝不阻塞检索
"""
import json
import logging
import re

from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None

REWRITE_PROMPT = """你是检索查询改写器。把用户的问题改写成 1~3 条适合检索的短查询。
规则：
- 保留专有名词、技术术语、数字；补全"它 / 那个 / 这个"的指代对象
- 每条不超过 15 字，只输出 JSON 数组，例如：["LRU 缓存 实现", "双链表 结构"]
- 不要解释，不要 markdown 代码块"""


def _client_instance() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
        )
    return _client


async def rewrite_query(query: str) -> list[str]:
    """返回 1~3 条改写后的查询；任何失败都返回 [原问题]。"""
    try:
        response = await _client_instance().chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": REWRITE_PROMPT},
                {"role": "user", "content": query},
            ],
            temperature=0,
            max_tokens=256,          # 中文查询 token 多，给足余量，否则 JSON 会被截断
        )
        content = (response.choices[0].message.content or "").strip()
        # 模型偶尔会包一层 ```json 围栏，先剥掉
        content = content.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        queries = json.loads(content)
        if not isinstance(queries, list):
            raise ValueError("改写结果不是数组")
        cleaned = [str(item).strip() for item in queries if str(item).strip()]
        return cleaned[:3] or [query]
    except json.JSONDecodeError:
        # 输出被截断 / 格式跑偏：退化为提取引号内的片段
        found = re.findall(r'"([^"]{2,30})"', content)
        cleaned = [item.strip() for item in found if item.strip()]
        return cleaned[:3] or [query]
    except Exception as e:
        logger.warning("查询改写失败，使用原问题：%s", e)
        return [query]
