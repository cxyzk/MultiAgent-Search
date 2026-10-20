"""知识库检索工具：主 agent 的 RAG 入口。"""
from app.kb.retriever import bm25_retriever


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
    hits = await bm25_retriever.search(query, top_k)

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
