from tavily import AsyncTavilyClient

from app.core.config import settings

TAVILY_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "tavily_search",
        "description": "联网搜索。查新闻、时事、最近动态时 topic 必须用 news，"
                       "否则返回的多是常年不过期的聚合页。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "topic": {
                    "type": "string",
                    "enum": ["general", "news"],
                    "description": "general=全网综合搜索；news=新闻索引（带时效性）。"
                                   "用户问最近/最新/今天的资讯时用 news。",
                },
                "days": {
                    "type": "integer",
                    "description": "topic=news 时生效：只返回最近 N 天的新闻，默认 7",
                },
            },
            "required": ["query"],
        },
    },
}

# 惰性单例：复用底层连接池（每次请求新建 client 会反复重建连接）
_client: AsyncTavilyClient | None = None


def _get_client() -> AsyncTavilyClient:
    global _client
    if _client is None:
        _client = AsyncTavilyClient(api_key=settings.tavily_api_key)
    return _client


async def tavily_search(
    query: str, topic: str = "general", days: int = 7, max_results: int = 3
) -> dict:
    # news 主题才有时效性过滤和 published_date 字段，general 传了也没用
    kwargs: dict = {"query": query, "max_results": max_results}
    if topic == "news":
        kwargs["topic"] = "news"
        kwargs["days"] = days

    try:
        response = await _get_client().search(**kwargs)   # 官方 SDK 返回 dict
    except Exception as e:
        return {"error": f"搜索服务请求失败：{type(e).__name__}: {e}"}

    results = response.get("results", [])
    formatted: list[dict] = []
    for result in results:
        formatted.append({
            "title": result.get("title", ""),
            "url": result.get("url", ""),
            "content": result.get("content", ""),
            "published_date": result.get("published_date", ""),
        })
    return {"results": formatted}
