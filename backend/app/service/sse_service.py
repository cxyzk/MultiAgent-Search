"""会话级 SSE 定向推送。

一个会话可能同时连着多个客户端（手机 + 电脑、多个标签页），但流式事件
只应该推给**发起任务的那个连接**——否则另一端会凭空冒出别人的回答。

所以连接按 (session_id, client_id) 注册：client_id 由前端生成，
SSE 连接和 /task 提交带上同一个值。
"""
import asyncio
import json
from collections import defaultdict


class SSEService:
    def __init__(self):
        # session_id -> {client_id: Queue}
        self.sse_queues: dict[str, dict[str, asyncio.Queue]] = defaultdict(dict)

    async def generate(self, queue: asyncio.Queue, session_id: str, client_id: str):
        try:
            yield ": connected\n\n"  # ★ 必须放在 try 里：客户端"连上就断开"时 aclose
            #   会把 GeneratorExit 抛在挂起点，写在 try 外的话 finally 不会执行，
            #   队列就永久残留在注册表里。
            while True:
                try:
                    # 15 秒没有事件就发一个注释行保活（SSE 的"心跳"）
                    payload = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        finally:
            # 断开时只清理自己：同一 client_id 重连过的话，这里的队列已被新连接替换
            clients = self.sse_queues.get(session_id)
            if clients is not None:
                if clients.get(client_id) is queue:
                    clients.pop(client_id, None)
                if not clients:
                    self.sse_queues.pop(session_id, None)

    async def register(self, session_id: str, client_id: str, queue: asyncio.Queue) -> None:
        # 同一 client_id 重连（旧连接还没断透）→ 用新队列替换旧的
        self.sse_queues[session_id][client_id] = queue

    async def push(self, session_id: str, payload: dict, client_id: str | None = None) -> None:
        """只推给发起任务的连接。没有对应连接就丢弃——由前端重连后拉历史补上。

        用 put_nowait：队列满了说明客户端跟不上，丢这一条，别阻塞事件生成。
        """
        queue = self.sse_queues.get(session_id, {}).get(client_id or "")
        if queue is None:
            return
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            pass


sse_service = SSEService()
