"""混合检索：BM25 + 向量两路召回，RRF（倒数排名融合）。"""
import asyncio

RRF_K = 60   # 行业惯例值


class HybridRetriever:
    def __init__(self, bm25, emb) -> None:
        self._bm25 = bm25
        self._emb = emb

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        bm25_hits, emb_hits = await asyncio.gather(
            self._bm25.search(query, top_k * 3),
            self._emb.search(query, top_k * 3),
        )

        scores: dict[int, float] = {}
        info: dict[int, dict] = {}
        for hits in (bm25_hits, emb_hits):
            for rank, h in enumerate(hits):
                cid = h["chunk_id"]
                scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank + 1)
                info.setdefault(cid, h)

        ranked  = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]

        results :list[dict] = []
        for chunk_id, score in ranked:
            item = dict(info[chunk_id])  # 复制元数据
            item["score"] = round(score, 6)  # 加分数
            results.append(item)
        return results