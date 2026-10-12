from fastapi import APIRouter
from pydantic import BaseModel
import asyncio,json,uuid
from app.db.session import SessionLocal
from fastapi.responses import StreamingResponse

from app.service.session_service import session_service
from app.service.task_service import task_service
from app.service.sse_service import sse_service


router = APIRouter()

class TaskRequest(BaseModel):
    query: str
    session_id: str   # 前端先连 WS 用的身份，提交任务时带上


@router.post("/task")
async def create_task(req: TaskRequest):
    '''
    这里不能用依赖注入的方式
    '''
    task_id = uuid.uuid4().hex

    # session_id 和 task_id 通过闭包"带进"agent 深处，不用改 run_agent 的签名
    async def on_progress(payload: dict) -> None:
        #这里的payload通过解包再加入这个task_id
        await sse_service.push(req.session_id, {**payload, "task_id": task_id})

    async def on_token(delta: str) -> None:
        # 直播：文本增量立刻推送，不等汇总
        await sse_service.push(req.session_id, {"type": "token", "task_id": task_id, "delta": delta})

    # ★ 全量轨迹落库钩子：loop 每产生一条消息就调一次
    async def on_message(msg: dict) -> None:
        tool_calls = msg.get("tool_calls")
        async with SessionLocal() as db:
            await session_service.append(
                req.session_id,
                db=db,
                role=msg["role"],
                content=msg.get("content") or "",
                tool_calls=json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None,
                tool_call_id=msg.get("tool_call_id"),
            )
    asyncio.create_task(task_service.job(req,task_id,on_progress,on_token,on_message))  # 丢后台跑，HTTP 立刻返回
    return {"task_id": task_id, "session_id": req.session_id}


@router.get("/events/{session_id}")
async def sse_endpoint(session_id: str):
    queue: asyncio.Queue = asyncio.Queue()
    await sse_service.register(session_id, queue)
    return StreamingResponse(
        sse_service.generate(queue, session_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # 将来 nginx 部署时禁缓冲，事件才实时到达
        },
    )


