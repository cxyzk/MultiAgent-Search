"""知识库检索工具：主 agent 的 RAG 入口。"""
import asyncio

from app.core.config import settings
from app.kb.factory import get_retriever
from app.kb.query_rewrite import rewrite_query


KB_SEARCH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "kb_search",
        "description": "检索本地知识库（用户上传的文档）。"
                       "问内部资料、已有文档里的内容时优先调用；"
                       "知识库没命中或问题涉及实时信息，再考虑联网搜索。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "检索用的关键词或短句，只写主体，不要带“帮我查一下”这类话",
                },
                "top_k": {"type": "integer", "description": "返回片段数，默认 5"},
            },
            "required": ["query"],
        },
    },
}

async def kb_search(query: str, top_k: int = 5) -> dict:
    retriever = get_retriever()

    # ① 查询改写（可选）：口语化问题 → 1~3 条检索式
    queries = [query]
    if settings.query_rewrite_enabled:
        queries = await rewrite_query(query)

    # ② 多路并发检索，按 chunk_id 去重（同一个片段保留最高分）
    batches = await asyncio.gather(*(retriever.search(q, top_k) for q in queries))
    merged: dict[int, dict] = {}
    for batch in batches:
        for hit in batch:
            existing = merged.get(hit["chunk_id"])
            if existing is None or hit["score"] > existing["score"]:
                merged[hit["chunk_id"]] = hit

    hits = sorted(merged.values(), key=lambda item: item["score"], reverse=True)[:top_k]

    if not hits:
        # ★ 关键：明确告诉模型“没查到”，它才会去调 search_agent 或如实说不知道
        #   返回空列表而不给 note，模型很容易自己编
        return {"results": [], "note": "知识库没有命中相关片段，可以改用 search_agent 联网搜索"}

    return {
        "results": [
            {"title": h["title"], "content": h["content"], "score": h["score"]}
            for h in hits
        ],
        # ★ 结构化来源，前端要展示引用的就靠它
        "citations": [
            {"title": h["title"], "chunk_id": h["chunk_id"], "score": h["score"]}
            for h in hits
        ],
    }
