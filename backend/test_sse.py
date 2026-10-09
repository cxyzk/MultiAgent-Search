import asyncio
import httpx

BASE = "http://127.0.0.1:8001"

async def main():
    # 先建立 SSE 订阅，再提交任务
    async with httpx.AsyncClient(base_url=BASE, timeout=120) as client:
        async with client.stream("GET", "/api/events/test-session") as resp:
            r = await client.post("/api/task", json={
                "query": "北京现在的天气如何",
                "session_id": "test-session",
            })
            print("提交:", r.json())
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    msg = line[len("data: "):]
                    print("<<", msg)
                    if '"type": "result"' in msg or '"type": "error"' in msg:
                        break

asyncio.run(main())
