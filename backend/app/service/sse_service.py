import asyncio
import json

class SSEService:
    def __init__(self):
        # session_id -> 事件队列：一个会话一条 SSE 连接
        self.sse_queues: dict[str, asyncio.Queue] = {}

    async def generate(self,queue: asyncio.Queue,session_id: str):
        yield ": connected\n\n"  # ★ 立即吐一行：让代理立刻转发响应头
        try:
            while True:
                try:
                    # 15 秒没有事件就发一个注释行保活（SSE 的"心跳"）
                    payload = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        finally:
            # 客户端断开 → 生成器被取消 → 清理注册。
            # is queue 守卫：防止"旧连接的清理"误删"新连接刚注册的队列"
            if self.sse_queues.get(session_id) is queue:
                self.sse_queues.pop(session_id, None)
    # 注册函数 将会话和队列关联起来
    async def register(self,session_id:str,queue: asyncio.Queue)->None:
        self.sse_queues[session_id] = queue

    # sse推送函数 通过session_id推送数据给前端
    async def push(self,session_id: str, payload: dict) -> None:
        queue = self.sse_queues.get(session_id)
        if queue is not None:
            await queue.put(payload)

sse_service = SSEService()