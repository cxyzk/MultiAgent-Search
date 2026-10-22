"""SSE 核心逻辑的单元测试。

注意：httpx 的 ASGITransport 无法流式读取"永不结束"的响应
（client.stream 会一直等 ASGI 应用完成），所以这里不测 HTTP 长连接，
而是直接测生成器和队列这两个核心组件。长连接本身交给浏览器/手动冒烟验证。
"""
import asyncio

import pytest

from app.service.sse_service import sse_service


@pytest.mark.asyncio(loop_scope="session")
async def test_generate_emits_connected_then_data():
    queue: asyncio.Queue = asyncio.Queue()
    await sse_service.register("s-unit", queue)

    gen = sse_service.generate(queue, "s-unit")
    # ① 连接建立后立刻吐一行（防代理攒包，见 README 的 vite 代理坑）
    first = await asyncio.wait_for(gen.__anext__(), 2)
    assert first == ": connected\n\n"

    # ② 队列里的推送被格式化成 data: 行
    await sse_service.push("s-unit", {"type": "result", "content": "ok"})
    second = await asyncio.wait_for(gen.__anext__(), 2)
    assert second.startswith("data: ")
    assert '"result"' in second

    await gen.aclose()


@pytest.mark.asyncio(loop_scope="session")
async def test_push_without_connection_is_dropped():
    """没有 SSE 连接时 push 不能抛异常（推送是尽力而为，任务只对落库负责）"""
    await sse_service.push("no-such-session", {"type": "token", "delta": "x"})
