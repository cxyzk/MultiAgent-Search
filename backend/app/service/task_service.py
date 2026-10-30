from app.db.session import SessionLocal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.service.session_service import session_service
from app.service.kb_service import kb_service
from app.agent.main_agent import run_main_agent
from app.service.sse_service import sse_service
from app.core.context import current_task
from app.service.usage_service import summarize_task_usage
from datetime import datetime

from app.db.models import Task, Message
import json
import time

class TaskService:
    @staticmethod
    async def job(req, task_id, on_progress, on_token, on_message, on_reasoning=None) -> None:
        # 把 session/task 放进请求上下文：深层 LLM 调用据此记录归属（并行任务互不串）
        ctx_token = current_task.set({"session_id": req.session_id, "task_id": task_id})
        # 思考过程：透传给前端的同时留一份，任务结束时挂到最终回答上
        reasoning_parts: list[str] = []
        started_at = time.perf_counter()
        first_token_at: float | None = None

        async def forward_reasoning(delta: str) -> None:
            reasoning_parts.append(delta)
            if on_reasoning:
                await on_reasoning(delta)

        async def forward_token(delta: str) -> None:
            nonlocal first_token_at
            if first_token_at is None:
                first_token_at = time.perf_counter()   # 首个回答 token：思考阶段结束
            if on_token:
                await on_token(delta)
        try:
            async with SessionLocal() as db:
                # ① 读【旧】历史（此时本次提问还没落库）
                history = await session_service.get_history(req.session_id, db=db)
                # ② 建会话 + 落 user（两个都不能省，顺序也不能反）
                await session_service.ensure_session(req.session_id, db, title=req.query[:60])
                await session_service.append(req.session_id, db, role="user", content=req.query)
                await task_service.create_task(task_id, db, req.session_id, req.query)
                # ③ 知识库主题清单：让模型知道"哪些问题该先查库"
                kb_titles = await kb_service.list_titles(db)
            # 智能搜索：false = 禁止联网（工具会被移除）；true = 允许，是否调用由模型自行决定
            query = req.query
            web_search = getattr(req, "web_search", False)
            result = await run_main_agent(query,
                                          on_progress=on_progress,
                                          history=history,
                                          on_token=forward_token,
                                          on_message=on_message,
                                          deep_think=getattr(req, "deep_think", False),
                                          on_reasoning=forward_reasoning,
                                          allow_search=web_search,
                                          kb_titles=kb_titles)
            async with SessionLocal() as db:
                await task_service.finish_task(task_id, db, "done")

            # ④ 只推送，不再落库（原来的 append(assistant) 删掉）；附上本任务的用量汇总
            usage = await summarize_task_usage(task_id)
            # "已思考（用时 N 秒）"= 开始 → 首个回答 token；和 LLM 总耗时是两个口径
            if first_token_at is not None:
                usage["thinking_ms"] = int((first_token_at - started_at) * 1000)
            # 展示数据持久化：思考过程 + 用量挂到最后一条 assistant（= 最终回答）
            async with SessionLocal() as db:
                last_assistant_id = (
                    select(Message.id)
                    .where(Message.session_id == req.session_id, Message.role == "assistant")
                    .order_by(Message.id.desc())
                    .limit(1)
                ).scalar_subquery()
                await db.execute(
                    update(Message).where(Message.id == last_assistant_id).values(
                        reasoning="".join(reasoning_parts) or None,
                        usage_json=json.dumps(usage, ensure_ascii=False) if usage else None,
                    )
                )
                await db.commit()
            await sse_service.push(req.session_id, {"type": "result", "task_id": task_id, "content": result, "usage": usage})
        except Exception as e:
            async with SessionLocal() as db:
                await task_service.finish_task(task_id, db, "error", error=str(e))  # ★ 补上这两行
            # 后台任务的异常没人接，必须自己兜住推给前端，否则前端永远干等
            await sse_service.push(req.session_id, {"type": "error", "task_id": task_id, "error": str(e)})
        finally:
            current_task.reset(ctx_token)   # ★ 复位，避免上下文泄漏到后续任务

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

task_service = TaskService()


