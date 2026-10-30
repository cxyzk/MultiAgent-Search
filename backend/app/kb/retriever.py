"""检索器：可插拔接口 + BM25 实现（纯 Python，中文分词用 jieba）。

v2 可加 EmbeddingRetriever（接入第三方 embedding 服务）——接口不变。
"""
from typing import Protocol, runtime_checkable
import re,math
import jieba
from app.db.models import Chunk, Document
from app.db.session import SessionLocal
from sqlalchemy import select
from collections import Counter


@runtime_checkable
class Retriever(Protocol):
    async def search(self, query: str,top_k: int = 5) -> list[dict]:...



_STOPWORDS = frozenset("""
的 了 是 在 和 与 或 也 就 都 而 及 等 被 把 对 让 给 从 到 为 以 于 之 其 这 那 有 没有
我们 你们 他们 它们 怎么 如何 什么 为什么 可以 需要 应该 一个 一些 这个 那个 这些 那些
""".split())


def tokenize(text: str) -> list[str]:
    """中英混合分词：
    - 英文 / 数字：按单词
    - 中文：jieba 精确模式，只过滤停用词，**不过滤单字**——"锁""桶"这类单字是关键词，
      滤掉就召回不到；也不用 cut_for_search，它会额外产出"布式"这类二元碎片。
    """
    tokens: list[str] = []

    for m in re.finditer(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+", text.lower()):
        seg = m.group()
        if seg[0].isascii():
            tokens.append(seg)
        else:
            tokens.extend(w for w in jieba.lcut(seg) if w not in _STOPWORDS)
    return tokens

class BM25Retriever:
    """索引常驻内存；文档变更后 mark_dirty，下次检索时懒重建。"""

    K1 = 1.5
    B = 0.75
    TITLE_WEIGHT = 3      # 标题 token 重复计入的份数：标题命中的片段更可能正是要的

    def __init__(self) -> None:
        self._chunks: list[dict] = []
        self._df: Counter[str] = Counter()
        self._avg_len = 0.0
        self._dirty = True

    def mark_dirty(self) -> None:
        """入库 / 删除文档后调用"""
        self._dirty = True

    async def _rebuild(self) -> None:
        async with SessionLocal() as db:
            rows = (await db.execute(
                select(Chunk.id, Chunk.document_id, Chunk.content, Document.title)
                .join(Document, Document.id == Chunk.document_id)
            )).all()
        self._chunks = []
        self._df = Counter()
        total_len = 0
        for cid, doc_id, content, title in rows:
            # ★ 标题必须参与索引：正文常是代码/英文（如 C++ 示例），
            #   中文信息只存在于标题里；只索引 content 会导致"搜标题搜不到"。
            #   标题重复计入（TITLE_WEIGHT 份），提升标题命中相对正文的权重。
            tokens = tokenize(title) * self.TITLE_WEIGHT + tokenize(content)
            tf = Counter(tokens)
            total_len += len(tokens)
            for term in tf:
                self._df[term] += 1
            self._chunks.append({
                "id": cid, "document_id": doc_id, "title": title,
                "content": content, "tf": tf, "length": len(tokens),
            })
        self._avg_len = total_len / len(self._chunks) if self._chunks else 0.0
        self._dirty = False

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        if self._dirty:
            await self._rebuild()
        if not self._chunks:
            return []
        q_terms = tokenize(query)
        n = len(self._chunks)
        scored: list[tuple[float, dict]] = []
        for ch in self._chunks:
            score = 0.0
            for term in q_terms:
                tf = ch["tf"].get(term)
                if not tf:
                    continue
                df = self._df.get(term, 0)
                idf = math.log((n - df + 0.5) / (df + 0.5) + 1)      # BM25+ 形式，恒非负
                denom = tf + self.K1 * (1 - self.B + self.B * ch["length"] / self._avg_len)
                score += idf * tf * (self.K1 + 1) / denom
            if score > 0:
                scored.append((score, ch))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"chunk_id": ch["id"], "document_id": ch["document_id"], "title": ch["title"],
             "content": ch["content"], "score": round(s, 4)}
            for s, ch in scored[:top_k]
        ]


bm25_retriever = BM25Retriever()




