import asyncio
import httpx
import websockets

BASE = "http://127.0.0.1:8001"

async def main():
    #先订阅ws 再提交任务
    async with websockets.connect("ws://127.0.0.1:8001/api/ws/test-session") as ws:
        async with httpx.AsyncClient(base_url=BASE) as client:
            r = await client.post("/api/task", json={
                "query": "北京现在的天气如何",
                "session_id": "test-session",
            })
            print("提交:", r.json())
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=60)
                print("<<", msg)
                if '"type":"result"' in msg or '"type":"error"' in msg:
                    break
asyncio.run(main())