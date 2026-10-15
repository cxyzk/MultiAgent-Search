"""知识库核心自测：入库两篇文档 → 检索命中验证 → 清理。"""
import asyncio
import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.db.session import SessionLocal
from app.kb.retriever import bm25_retriever
from app.service.kb_service import KBService

DOC_A = """向量数据库的选型要看规模。十万条以内的向量，用 numpy 暴力检索就足够，
一次全量相似度计算只要几毫秒。百万级以上才需要考虑 HNSW 这类近似最近邻索引。
暴力搜索是精确的，ANN 是近似的，小规模下暴力反而更准。"""

DOC_B = """并发限流要用信号量。asyncio.Semaphore 可以限制同时执行的协程数量。
要注意作用域：定义在函数内是每个循环独立限流，定义在模块级是全局共享。
在嵌套的 agent 结构里用全局信号量会造成死锁：父任务占着名额等子任务，子任务等名额才能开始。"""


async def main() -> None:
    async with SessionLocal() as db:
        r1 = await KBService.add_document("向量检索笔记", DOC_A, db, source="a.md")
        r2 = await KBService.add_document("并发编程笔记", DOC_B, db, source="b.md")
        print("入库:", r1, r2)

    for q in ["向量数据库 什么时候需要", "信号量 死锁", "今天晚饭吃什么"]:
        hits = await bm25_retriever.search(q, top_k=2)
        print(f"\nQ: {q}")
        for h in hits:
            print(f"   [{h['score']:>6}] 《{h['title']}》#{h['chunk_id']}: {h['content'][:36]}...")
        if not hits:
            print("   （无命中 —— 不相关的查询就该这样）")

    async with SessionLocal() as db:
        for r in (r1, r2):
            await KBService.delete_document(r["id"], db)
    print("\n测试数据已清理")


asyncio.run(main())
