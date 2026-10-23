"""向量检索器：内存矩阵 + 余弦相似度（暴力全量，小规模下比 ANN 更准且够快）。"""
import numpy as np
from sqlalchemy import select

from app.db.models import Chunk, Document
from app.db.session import SessionLocal
from app.kb.embedding import embed

MIN_SIM = 0.3   # 余弦低于该值视为不相关；bge-m3 的经验起点，可按语料调


class EmbeddingRetriever:
    def __init__(self) -> None:
        self._matrix: np.ndarray | None = None
        self._chunks: list[dict] = []
        self._dirty = True

    def mark_dirty(self) -> None:
        self._dirty = True

    async def _rebuild(self) -> None:
        async with SessionLocal() as db:
            rows = (await db.execute(
                select(Chunk.id, Chunk.document_id, Chunk.content,
                       Document.title, Chunk.embedding)
                .join(Document, Document.id == Chunk.document_id)
                .where(Chunk.embedding.is_not(None))
            )).all()

        vecs: list[np.ndarray] = []
        self._chunks = []
        for cid, doc_id, content, title, blob in rows:
            vecs.append(np.frombuffer(blob, dtype=np.float32))
            self._chunks.append({
                "chunk_id": cid, "document_id": doc_id,
                "title": title, "content": content,
            })

        if vecs:
            dims = {v.shape[0] for v in vecs}
            if len(dims) > 1:
                raise RuntimeError(
                    f"向量维度不一致 {dims}——切换过 embedding 模型？请重建索引"
                )
            mat = np.vstack(vecs).astype(np.float32)
            self._matrix = mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9)
        else:
            self._matrix = None
        self._dirty = False

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        if self._dirty:
            await self._rebuild()
        if self._matrix is None or not self._chunks:
            return []

        qv = np.asarray((await embed([query]))[0], dtype=np.float32)
        qv /= (np.linalg.norm(qv) + 1e-9)

        similarities  = self._matrix @ qv                                  # 一次矩阵乘法
        ranked_indices = np.argsort(similarities)[::-1][:top_k]

        results: list[dict] = []
        for index in ranked_indices:
            similarity = float(similarities[index])
            if similarity < MIN_SIM:
                continue  # 不相关的不返回（不硬凑）

            chunk = dict(self._chunks[index])  # 拷贝，避免污染缓存的 chunk 信息
            chunk["score"] = round(similarity, 4)
            results.append(chunk)
        return results


embedding_retriever = EmbeddingRetriever()
