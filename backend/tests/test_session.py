import pytest

from app.db.models import Session as SessionModel
from app.db.session import SessionLocal
from app.service.session_service import session_service


@pytest.mark.asyncio(loop_scope="session")
async def test_rename_persists(client):
    """回归：rename 必须 commit（曾因漏 commit 导致"返回 ok 但没落库"）"""
    async with SessionLocal() as db:
        await session_service.ensure_session("s1", db, title="旧标题")

    resp = await client.patch("/api/session/s1", json={"title": "新标题"})
    assert resp.status_code == 200

    async with SessionLocal() as db:  # 换一个新 session 查库 = 验证真落盘
        row = await db.get(SessionModel, "s1")
        assert row.title == "新标题"


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_session_cascades(client):
    async with SessionLocal() as db:
        await session_service.ensure_session("s2", db, title="T")
        await session_service.append("s2", db, role="user", content="hi")

    resp = await client.delete("/api/session/s2")
    assert resp.status_code == 200

    async with SessionLocal() as db:
        assert await db.get(SessionModel, "s2") is None
        # messages 的级联由 FK 完成——顺便验证 PRAGMA 生效
        from app.db.models import Message
        from sqlalchemy import select
        rows = (await db.execute(select(Message).where(Message.session_id == "s2"))).scalars().all()
        assert rows == []
