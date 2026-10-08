from fastapi import APIRouter
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from app.agent.main_agent import run_main_agent
import asyncio,json,uuid
from app.db.session import SessionLocal

from app.core.session_store import store


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
    '''
    这里不能用依赖注入的方式
    '''
    task_id = uuid.uuid4().hex

    # session_id 和 task_id 通过闭包"带进"agent 深处，不用改 run_agent 的签名
    async def on_progress(payload: dict) -> None:
        #这里的payload通过解包再加入这个task_id
        await push(req.session_id, {**payload, "task_id": task_id})

    async def on_token(delta: str) -> None:
        # 直播：文本增量立刻推送，不等汇总
        await push(req.session_id, {"type": "token", "task_id": task_id, "delta": delta})

    # ★ 全量轨迹落库钩子：loop 每产生一条消息就调一次
    async def on_message(msg: dict) -> None:
        tool_calls = msg.get("tool_calls")
        async with SessionLocal() as db:
            await store.append(
                req.session_id,
                db=db,
                role=msg["role"],
                content=msg.get("content") or "",
                tool_calls=json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None,
                tool_call_id=msg.get("tool_call_id"),
            )

    async def job() -> None:
        try:
            async with SessionLocal() as db:
                # ① 读【旧】历史（此时本次提问还没落库）
                history = await store.get_history(req.session_id, db=db)
                # ② 建会话 + 落 user（两个都不能省，顺序也不能反）
                await store.ensure_session(req.session_id, db, title=req.query[:60])
                await store.append(req.session_id, db, role="user", content=req.query)
            result = await run_main_agent(req.query,
                                          on_progress=on_progress,
                                          history=history,
                                          on_token=on_token,
                                          on_message=on_message)
            # ④ 只推送，不再落库（原来的 append(assistant) 删掉）
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


