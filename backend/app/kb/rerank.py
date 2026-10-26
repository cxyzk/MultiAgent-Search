"""Rerank：两阶段检索的第二段——用 bge-reranker 对候选片段精排。

召回阶段追求"都找得到"（多召回），精排阶段追求"排得准"（少而准）。
任何异常都降级为"按召回顺序截断"，不阻塞检索。
"""
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

RERANK_URL = "https://api.siliconflow.cn/v1/rerank"


async def rerank(query: str, hits: list[dict], top_n: int = 5) -> list[dict]:
    """对候选片段精排并截断到 top_n；分数换成精排的 relevance_score。"""
    if len(hits) <= 1:
        return hits[:top_n]

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                RERANK_URL,
                headers={"Authorization": f"Bearer {settings.embedding_api_key}"},
                json={
                    "model": settings.rerank_model,
                    "query": query,
                    "documents": [hit["content"] for hit in hits],
                    "top_n": top_n,
                },
            )
            response.raise_for_status()
            results = response.json().get("results", [])
    except Exception as e:                      # 网络 / 429 / 服务异常
        logger.warning("rerank 失败，降级为召回顺序：%s", e)
        return hits[:top_n]

    reranked: list[dict] = []
    for item in results:                        # 服务端已按 relevance 降序返回
        hit = dict(hits[item["index"]])
        hit["score"] = round(float(item["relevance_score"]), 4)
        reranked.append(hit)
    return reranked or hits[:top_n]
