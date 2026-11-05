"""查询改写：把口语化问题改写成检索友好的短查询，提升召回。

设计：
- 只在 kb_search 工具入口做一次（不是每次检索都调），成本可控
- 任何失败都降级为 [原问题]，绝不阻塞检索
"""
import json
import logging
import re

import httpx

from app.core.config import settings
from app.core.llm import get_llm_client

logger = logging.getLogger(__name__)

# 改写是"锦上添花"，失败就该立刻降级。而 SDK 默认 read 超时 600s + 重试 2 次，
# 最坏能把 kb_search 卡半小时——所以派生一个短超时、不重试的实例。
# with_options 复用同一个 httpx client，不会新建连接池。
_REWRITE_TIMEOUT = httpx.Timeout(10.0, connect=3.0)

REWRITE_PROMPT = """你是检索查询改写器。把用户的问题改写成 1~3 条适合检索的短查询。
规则：
- 保留专有名词、技术术语、数字；补全"它 / 那个 / 这个"的指代对象
- 每条不超过 15 字，只输出 JSON 数组，例如：["LRU 缓存 实现", "双链表 结构"]
- 不要解释，不要 markdown 代码块"""


async def rewrite_query(query: str) -> list[str]:
    """返回 1~3 条改写后的查询；任何失败都返回 [原问题]。"""
    try:
        client = get_llm_client().with_options(
            timeout=_REWRITE_TIMEOUT, max_retries=0)
        response = await client.chat.completions.create(
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
