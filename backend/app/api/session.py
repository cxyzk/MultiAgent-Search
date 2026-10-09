from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.session_store import store
from fastapi import Depends
from app.db.session import get_db



router = APIRouter()

# 列出所有的会话
@router.get("/session")
async def list_sessions(db: AsyncSession = Depends(get_db)):
    return await store.list_sessions(db=db)

# 列出指定会话的所有消息
@router.get("/session/{session_id}/messages")
async def list_messages(session_id: str,db: AsyncSession = Depends(get_db)):
    return await store.list_messages(session_id=session_id,db=db)


#删除指定的会话
@router.delete("/session/{session_id}")
async def delete_session(session_id: str,db:AsyncSession= Depends(get_db)):
    await store.delete_session(session_id=session_id, db=db)
    return {"ok": True}

@router.get("/session/{session_id}/tasks")
async def list_tasks(session_id: str, db: AsyncSession = Depends(get_db)):
    return await store.list_tasks(session_id, db)



