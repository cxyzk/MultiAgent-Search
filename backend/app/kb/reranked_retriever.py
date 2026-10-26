"""两阶段检索：把任一检索器包成"先多召回、再精排"。

实现 Retriever Protocol（只需 search），所以对 kb_search 工具、
/kb/search 调试接口完全透明——切换只需要动配置。
"""
from app.kb.rerank import rerank


class RerankedRetriever:
    """召回阶段多要一些候选，交给 rerank 精排后只留 top_k。"""

    def __init__(self, base, candidate_k: int = 20) -> None:
        self._base = base
        self._candidate_k = candidate_k

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        candidate_count = max(top_k, self._candidate_k)
        candidates = await self._base.search(query, candidate_count)
        return await rerank(query, candidates, top_n=top_k)
