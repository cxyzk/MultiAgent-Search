import httpx
from app.core.config import settings

TAVILY_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "tavily_search",
        "description": "联网搜索最新信息。当需要查询实时、时效性信息时调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"}
            },
            "required": ["query"],
        },
    },
}

async def tavily_search(query: str, max_results: int = 3) -> dict:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                headers={"Authorization": f"Bearer {settings.tavily_api_key}"},
                json={"query": query, "max_results": max_results},
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            new_results = []
            for result in results:
                new_results.append(
                    {
                        "title": result.get("title", ""),
                        "url": result.get("url", ""),
                        "content": result.get("content ", ""),
                    }
                )
            return {"results": new_results}
    except httpx.HTTPError as e:
        return {"error": f"搜索服务请求失败：{e}"}
