from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Message
from app.db.models import Session
from app.db.models import Task


class SessionStore:
    """持久化版会话历史：写侧全量轨迹，读侧只挑文本轮"""

    MAX_MESSAGES = 20  # 回填上限，超出丢最老的（现在丢在 SQL 的 LIMIT 里）

    @staticmethod
    async def ensure_session(session_id: str, db: AsyncSession, title: str = "") -> None:
        """会话不存在就创建；已存在就跳过"""
        if await db.get(Session, session_id) is None:
            db.add(Session(id=session_id, title=title[:60]))
            await db.commit()

    @staticmethod
    async def append(session_id: str,  db: AsyncSession,role: str, content: str = "",
                     tool_calls: str | None = None,
                     tool_call_id: str | None = None
                     ) -> None:
        db.add(Message(
            session_id=session_id,role=role,content=content,
            tool_calls=tool_calls,tool_call_id=tool_call_id
        ))
        await db.execute(
            update(Session).where(Session.id == session_id)
            .values(updated_at=datetime.now())
        )
        await db.commit()

    @staticmethod
    async def get_history(session_id: str, db: AsyncSession, limit: int = MAX_MESSAGES) -> list[dict]:
        """回填给 LLM：只取文本轮，倒序切最近 N 条再反转成正序"""
        stmt=(select(Message.role,Message.content).where(
            Message.session_id == session_id,
            Message.role.in_(("user", "assistant")),
            Message.content != "",  # ← 妙在这：assistant 中间轮 content 为空，天然被滤掉
        )
        .order_by(Message.id.desc())
        .limit(limit)
        )
        rows=(await db.execute(stmt)).all()
        return [{"role": r, "content": c} for r, c in reversed(rows)]

    @staticmethod
    async def list_sessions(db: AsyncSession) -> list[dict]:
        """侧边栏：最近聊的排前面"""
        stmt = (
            select(Session.id, Session.title, Session.updated_at)
            .order_by(Session.updated_at.desc())
        )
        rows = (await db.execute(stmt)).all()
        return [{"id": i, "title": t, "updated_at": str(u)} for i, t, u in rows]

    @staticmethod
    async def list_messages(session_id: str,db:AsyncSession) -> list[dict]:
        """给前端恢复聊天记录：正序、同样只展示文本轮"""
        stmt = (
            select(Message.role, Message.content, Message.created_at)
            .where(
                Message.session_id == session_id,
                Message.role.in_(("user", "assistant")),
                Message.content != "",
            )
            .order_by(Message.id.asc())
        )
        rows = (await db.execute(stmt)).all()
        return [{"role": r, "content": c, "created_at": str(t)} for r, c, t in rows]

    @staticmethod
    async def delete_session(session_id: str,db:AsyncSession) -> None:
        """删会话；messages 靠外键 CASCADE 一并清掉"""
        row = await db.get(Session, session_id)
        if row is not None:
            await db.delete(row)
            await db.commit()

    @staticmethod
    async def create_task(task_id: str, db: AsyncSession, session_id: str, query: str) -> None:
        """任务开始：落一条 running 记录"""
        db.add(Task(id=task_id, session_id=session_id, status="running", query=query))
        await db.commit()

    @staticmethod
    async def finish_task(task_id: str, db: AsyncSession, status: str, error: str | None = None) -> None:
        """任务收尾：done / error，记录结束时间"""
        await db.execute(
            update(Task).where(Task.id == task_id)
            .values(status=status, error=error, finished_at=datetime.now())
        )
        await db.commit()

    @staticmethod
    async def list_tasks(session_id: str, db: AsyncSession, limit: int = 20) -> list[dict]:
        """会话的任务记录，最近的在前"""
        stmt = (
            select(Task.id, Task.status, Task.query, Task.error, Task.created_at, Task.finished_at)
            .where(Task.session_id == session_id)
            .order_by(Task.created_at.desc())
            .limit(limit)
        )
        rows = (await db.execute(stmt)).all()
        return [
            {"id": i, "status": s, "query": q, "error": e,
             "created_at": str(c), "finished_at": str(f) if f else None}
            for i, s, q, e, c, f in rows
        ]

store=SessionStore()