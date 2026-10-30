"""知识库业务：文档入库（切分 + 向量化 + 落库）、列表、删除。"""
import logging
import uuid

import numpy as np
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, Chunk
from app.kb.chunker import split_text
from app.kb.embedding import embed, embedding_enabled
from app.kb.embedding_retriever import embedding_retriever
from app.kb.retriever import bm25_retriever

logger = logging.getLogger(__name__)


class KBService:
    @staticmethod
    async def add_document(title: str, content: str, db: AsyncSession,
                           source: str | None = None) -> dict:
        """切分并入库，返回 {id, title, chunks}"""
        doc_id = uuid.uuid4().hex
        db.add(Document(id=doc_id, title=title, source=source))
        #确定插入顺序的正确性
        await db.flush()
        pieces = split_text(content)

        # 向量化：配了 embedding key 才做；失败降级为纯 BM25，不阻塞入库
        vectors: list[list[float]] = []
        if embedding_enabled():
            try:
                # 文本构造与重建脚本保持一致：标题 + 正文
                vectors = await embed([f"{title}\n{piece}" for piece in pieces])
            except Exception as e:
                logger.warning("embedding 失败，降级为纯 BM25: %s", e)

        for seq, piece in enumerate(pieces):
            blob = (np.asarray(vectors[seq], dtype=np.float32).tobytes()
                    if vectors else None)
            db.add(Chunk(document_id=doc_id, seq=seq, content=piece, embedding=blob))

        await db.commit()
        bm25_retriever.mark_dirty()          # ★ 通知检索器：索引该重建了
        embedding_retriever.mark_dirty()     # ★ 向量索引也一起重建
        return {"id": doc_id, "title": title, "chunks": len(pieces)}

    @staticmethod
    async def get_document(document_id: str, db: AsyncSession) -> dict | None:
        """文档详情 + 全部 chunk（用于查看切分效果）"""
        doc = await db.get(Document, document_id)
        if doc is None:
            return None
        rows = (await db.execute(
            select(Chunk.seq, Chunk.content)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.seq)
        )).all()
        return {
            "id": doc.id, "title": doc.title, "source": doc.source,
            "created_at": str(doc.created_at),
            "chunks": [{"seq": s, "content": c} for s, c in rows],
        }



    @staticmethod
    async def list_titles(db: AsyncSession, limit: int = 50) -> list[str]:
        """文档标题清单：喂给主 agent 判断"这个问题属不属于知识库的主题"。"""
        rows = (await db.execute(
            select(Document.title).order_by(Document.created_at.desc()).limit(limit)
        )).scalars().all()
        return list(rows)

    @staticmethod
    async def list_documents(db: AsyncSession) -> list[dict]:
        chunk_count = (
            select(func.count(Chunk.id))
            .where(Chunk.document_id == Document.id)
            .correlate(Document)
            .scalar_subquery()
        )
        stmt = (select(Document.id, Document.title, Document.source,
                       Document.created_at, chunk_count)
                .order_by(Document.created_at.desc()))
        rows = (await db.execute(stmt)).all()
        return [{"id": i, "title": t, "source": s, "created_at": str(c), "chunk_count": n}
                for i, t, s, c, n in rows]

    @staticmethod
    async def delete_document(document_id: str, db: AsyncSession) -> None:
        row = await db.get(Document, document_id)
        if row is not None:
            await db.delete(row)             # chunks 靠 CASCADE 一并清掉
            await db.commit()
            bm25_retriever.mark_dirty()


kb_service = KBService()
