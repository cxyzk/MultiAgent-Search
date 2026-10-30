"""混合检索：BM25 + 向量两路召回，RRF（倒数排名融合）。"""
import asyncio

RRF_K = 60   # 行业惯例值


class HybridRetriever:
    """两路召回 + RRF 融合，再做文档级去重。

    只按 chunk 融合时，长文档的多个片段会把 top_k 名额占满（实测 5 条里
    只有 3 篇文档的内容）。同一篇文档最多保留 max_per_doc 个 chunk，
    腾出的位置留给其它文档；去重后不足 top_k 时再按原顺序回填。
    """

    def __init__(self, bm25, emb, max_per_doc: int = 1) -> None:
        self._bm25 = bm25
        self._emb = emb
        self._max_per_doc = max_per_doc

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

        # 多留候选：去重会丢一些名次，需要足够的后备
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[: top_k * 3]

        results: list[dict] = []
        overflow: list[dict] = []
        per_doc: dict[str, int] = {}

        for chunk_id, score in ranked:
            item = dict(info[chunk_id])          # 复制元数据
            item["score"] = round(score, 6)
            title = item.get("title", "")
            if per_doc.get(title, 0) >= self._max_per_doc:
                overflow.append(item)            # 超额的先存着，不足时回填
                continue
            per_doc[title] = per_doc.get(title, 0) + 1
            results.append(item)
            if len(results) >= top_k:
                return results

        # 去重后不足 top_k（文档总数少）：用被压下的片段按原顺序补齐
        results.extend(overflow[: max(0, top_k - len(results))])
        return results