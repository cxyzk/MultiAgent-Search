"""任务状态流转测试。

注意：这里**不经过 HTTP + asyncio.create_task**（在 pytest-asyncio 下后台任务的
调度不可靠，实测 job 可能根本不执行），而是直接 await job()。
这样测的是"状态机 + 落库"本身，稳定可重复；HTTP 提交链路交给手动冒烟。
"""
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.db.models import Message, Task
from app.db.session import SessionLocal
from app.service.session_service import session_service
import app.service.task_service as ts


def _req(session_id: str, query: str = "你好") -> SimpleNamespace:
    return SimpleNamespace(session_id=session_id, query=query)


@pytest.mark.asyncio(loop_scope="session")
async def test_task_done_and_messages_persisted(mock_agent):
    collected: list[dict] = []

    async def on_message(msg: dict) -> None:
        collected.append(msg)
        # 模拟 chat.py 里那个"落到 messages 表"的回调（真实链路靠它写 assistant）
        async with SessionLocal() as db:
            await session_service.append(
                "s-task", db, role=msg["role"], content=msg.get("content") or ""
            )

    await ts.task_service.job(_req("s-task"), "tid-done", None, None, on_message)

    async with SessionLocal() as db:
        task = await db.get(Task, "tid-done")
        assert task is not None
        assert task.status == "done"
        assert task.error is None

        roles = [m.role for m in (await db.execute(
            select(Message).where(Message.session_id == "s-task")
        )).scalars()]
    assert "user" in roles
    assert "assistant" in roles
    assert any(m.get("role") == "assistant" for m in collected)


@pytest.mark.asyncio(loop_scope="session")
async def test_task_failure_records_error(monkeypatch):
    async def boom(*args, **kwargs):
        raise RuntimeError("模型挂了")

    monkeypatch.setattr(ts, "run_main_agent", boom)

    await ts.task_service.job(_req("s-err", "x"), "tid-err", None, None, None)

    async with SessionLocal() as db:
        task = await db.get(Task, "tid-err")
        assert task is not None
        assert task.status == "error"
        assert "模型挂了" in (task.error or "")
