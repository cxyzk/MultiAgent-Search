"""Rerank：两阶段检索的第二段——用 bge-reranker 对候选片段精排。

召回阶段追求"都找得到"（多召回），精排阶段追求"排得准"（少而准）。
任何异常都降级为"按召回顺序截断"，不阻塞检索。
"""
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# 连接池复用：懒创建单例，进程生命周期内只有一份，省掉每次 TCP + TLS 握手。
# 前提：pytest.ini 的 loop scope 是 session（全测试共用一个事件循环）；
# 若改成 function 级，这个 client 会在第二个测试里撞上 "Event loop is closed"。
_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    """同步懒创建：函数体内没有 await，协程不会在此被切走，所以免锁。"""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            # connect 单独调短：连不上就快速降级，别把 kb_search 拖满 15s
            timeout=httpx.Timeout(15.0, connect=5.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )
    return _client


async def close_client() -> None:
    """进程退出时收尾，由 lifespan 在 yield 之后调用。"""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def rerank(query: str, hits: list[dict], top_n: int = 5) -> list[dict]:
    """对候选片段精排并截断到 top_n；分数换成精排的 relevance_score。

    配置全部取自 RERANK_* 这组 env，不依赖 embedding 的任何字段。
    """
    if len(hits) <= 1:
        return hits[:top_n]

    # 调用时读 settings（不是模块级常量）：测试 monkeypatch 才能打中
    url, api_key = settings.rerank_base_url, settings.rerank_api_key
    if not url or not api_key:
        logger.warning("rerank 未配置 RERANK_BASE_URL / RERANK_API_KEY，跳过精排")
        return hits[:top_n]

    try:
        response = await get_client().post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": settings.rerank_model,
                "query": query,
                # 标题参与精排：正文常是代码/英文，中文语义只存在于标题里，
                # 与入库向量化（f"{title}\n{piece}"）和 BM25（TITLE_WEIGHT）保持一致
                "documents": [f"{hit.get('title', '')}\n{hit['content']}" for hit in hits],
                "top_n": top_n,
            },
        )
        response.raise_for_status()
        results = response.json().get("results", [])
    except httpx.HTTPStatusError as e:
        # 鉴权失败是配置问题，不该混进"网络抖动"的 warning 里
        if e.response.status_code in (401, 403):
            logger.error("rerank 鉴权失败（%s）：检查 RERANK_API_KEY 是否有效",
                         e.response.status_code)
        else:
            logger.warning("rerank 失败，降级为召回顺序：%s", e)
        return hits[:top_n]
    except Exception as e:                      # 网络 / 超时 / 响应格式异常
        logger.warning("rerank 失败，降级为召回顺序：%s", e)
        return hits[:top_n]

    reranked: list[dict] = []
    for item in results:                        # 服务端已按 relevance 降序返回
        hit = dict(hits[item["index"]])
        hit["score"] = round(float(item["relevance_score"]), 4)
        reranked.append(hit)
    return reranked or hits[:top_n]
