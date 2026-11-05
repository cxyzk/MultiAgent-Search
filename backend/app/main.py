from fastapi import  FastAPI
from app.api import api_router
from contextlib import asynccontextmanager
from app.db.session import SessionLocal
from sqlalchemy import update
from app.db.models import Task
from app.kb.rerank import close_client
from app.core.llm import close_llm_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动善后：上次进程退出时还在 running 的任务，标记为 interrupted
    async with SessionLocal() as db:
        await db.execute(
            update(Task).where(Task.status == "running").values(status="interrupted")
        )
        await db.commit()
    yield
    # 进程退出：优雅关闭共享连接池，避免对端等超时 + ResourceWarning
    await close_client()
    await close_llm_client()

app=FastAPI(title="MultiAgent-Search",lifespan=lifespan)

@app.get("/health")
async def health():
    return {"status": "ok"}
app.include_router(api_router,prefix="/api")




