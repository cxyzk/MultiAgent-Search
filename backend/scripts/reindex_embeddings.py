"""给存量 chunks 补 embedding（首次启用向量检索时跑一次）。

用法：cd backend && python -m scripts.reindex_embeddings
"""
import asyncio

import numpy as np
from sqlalchemy import select

from app.db.models import Chunk, Document
from app.db.session import SessionLocal
from app.kb.embedding import embed, embedding_enabled

BATCH = 16


async def main() -> None:
    if not embedding_enabled():
        raise SystemExit("未配置 EMBEDDING_API_KEY，无法重建向量索引")

    async with SessionLocal() as db:
        rows = (await db.execute(
            select(Chunk.id, Chunk.content, Document.title)
            .join(Document, Document.id == Chunk.document_id)
            .where(Chunk.embedding.is_(None))
            .order_by(Chunk.id)
        )).all()

        if not rows:
            print("没有需要重建的 chunk")
            return
        print(f"待重建 {len(rows)} 个 chunk ...")

        for i in range(0, len(rows), BATCH):
            batch = rows[i:i + BATCH]
            texts = [f"{title}\n{content}" for _, content, title in batch]
            vecs = await embed(texts)
            for (cid, _, _), vec in zip(batch, vecs):
                blob = np.asarray(vec, dtype=np.float32).tobytes()
                await db.execute(
                    Chunk.__table__.update().where(Chunk.id == cid).values(embedding=blob)
                )
            await db.commit()
            print(f"  {min(i + BATCH, len(rows))}/{len(rows)}")

    print("完成")


asyncio.run(main())
