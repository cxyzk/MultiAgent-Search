from fastapi import APIRouter
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import uuid
from app.agent.main_agent import run_main_agent
import asyncio

router = APIRouter()

# session_id -> WebSocket，简化设计：一个会话一条连接
connections: dict[str, WebSocket] = {}

#ws推送函数 通过session_id推送数据给前端
async def push(session_id: str, payload: dict) -> None:
    ws = connections.get(session_id)
    if ws is not None:
        await ws.send_json(payload)

class TaskRequest(BaseModel):
    query: str
    session_id: str   # 前端先连 WS 用的身份，提交任务时带上


@router.post("/task")
async def create_task(req: TaskRequest):
    task_id = uuid.uuid4().hex

    # session_id 和 task_id 通过闭包"带进"agent 深处，不用改 run_agent 的签名
    async def on_progress(payload: dict) -> None:
        #这里的payload通过解包再加入这个task_id
        await push(req.session_id, {**payload, "task_id": task_id})

    async def job() -> None:
        try:
            #这里采用这个回调传入 避免这个循环依赖
            result = await run_main_agent(req.query, on_progress=on_progress)
            await push(req.session_id, {"type": "result", "task_id": task_id, "content": result})
        except Exception as e:
            # 后台任务的异常没人接，必须自己兜住推给前端，否则前端永远干等
            await push(req.session_id, {"type": "error", "task_id": task_id, "error": str(e)})

    asyncio.create_task(job())  # 丢后台跑，HTTP 立刻返回
    return {"task_id": task_id, "session_id": req.session_id}


@router.websocket("/ws/{session_id}")
async def ws_endpoint(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    connections[session_id] = websocket
    try:
        while True:
            await websocket.receive_text()   # 收着消息维持连接，内容暂不处理
    except WebSocketDisconnect:
        connections.pop(session_id, None)


