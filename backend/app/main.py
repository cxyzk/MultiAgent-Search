from fastapi import  FastAPI
from app.api import api_router
from contextlib import asynccontextmanager
from app.db.session import SessionLocal
from sqlalchemy import update
from app.db.models import Task


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动善后：上次进程退出时还在 running 的任务，标记为 interrupted
    async with SessionLocal() as db:
        await db.execute(
            update(Task).where(Task.status == "running").values(status="interrupted")
        )
        await db.commit()
    yield

app=FastAPI(title="MultiAgent-Search",lifespan=lifespan)

@app.get("/health")
async def health():
    return {"status": "ok"}
app.include_router(api_router,prefix="/api")




