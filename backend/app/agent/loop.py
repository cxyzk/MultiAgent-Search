from openai import AsyncOpenAI
from app.core.config import settings
import json,asyncio
import logging
import time
from typing import Awaitable, Callable, Any
from types import SimpleNamespace

from app.service.usage_service import record_llm_call

logger = logging.getLogger(__name__)

MAX_ROUNDS = 8




#初始化客户端
client = AsyncOpenAI(
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
)


#运行注解
ProgressCallback = Callable[[dict], Awaitable[None]]
TokenCallback = Callable[[str], Awaitable[None]]   # 每收到一小段文本调一次
MessageCallback = Callable[[dict], Awaitable[None]]


async def execute_tool(tool_call, tool_map: dict) -> str:
    """执行单个工具调用，返回回填给模型的结果字符串。以后超时/重试也加在这里"""
    func_name = tool_call.function.name
    try:
        args = json.loads(tool_call.function.arguments)
        func = tool_map.get(func_name)
        #这里的**把这个字典拆成关键字参数传给函数了 类似于func(city="上海")
        result = await func(**args) if func else {"error": f"未知工具：{func_name}"}
    except Exception as e:
        # 工具崩了要把错误回填给模型让它自己决定下一步，而不是炸掉整个请求
        # 同时记日志：错误回填给模型后前端只看到"工具失败"，终端也不再可见
        logger.warning("工具 %s 执行失败: %s: %s", func_name, type(e).__name__, e)
        result = {"error": f"工具 {func_name} 执行失败：{type(e).__name__}: {e}"}
    return json.dumps(result, ensure_ascii=False)

# 对执行单工具的封装 同时返回tool_call和result
async def run_tool(tool_call,tool_map,tool_semaphore)->tuple[Any, str]:
    async with tool_semaphore:#限制工具执行的并发数
     return tool_call, await execute_tool(tool_call, tool_map)


async def _call_model(messages, tools, on_token, agent_name: str = "agent",
                      deep_think: bool = False, on_reasoning=None):
    """调一次 LLM，返回 (content, tool_calls, 放回 messages 用的 assistant 消息)。

    on_token 非空时走流式：content 增量实时转发给调用方，
    tool_calls 的增量碎片按 index 分桶拼装。
    deep_think=True 时 reasoning_effort="high"（思考 token ~77→180），
    False 时 reasoning_effort="none"（不产出 reasoning_content，省 token 也更快）。
    on_reasoning 非空时把 reasoning_content（思考过程）单独转发，不和正文混在一起。
    每次调用都会把 token 用量/耗时记到 llm_calls 表（观测失败不影响主流程）。
    """
    started_at = time.perf_counter()
    # 思考强度：关闭时不产出 reasoning_content（reasoning_effort=none，实测 completion 16→9），
    # 开启时用 high（实测思考 token ~77→180）。两者是同一个参数的不同档位，切换成本为零。
    extra_body = {"reasoning_effort": "high" if deep_think else "none"}

    if on_token is None:
        resp=await client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            extra_body=extra_body,
            **({"tools": tools, "tool_choice": "auto"} if tools else {}),
        )
        msg = resp.choices[0].message
        if on_reasoning and getattr(msg, "reasoning_content", None):
            await on_reasoning(msg.reasoning_content)
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        await record_llm_call(agent_name=agent_name, usage=resp.usage, latency_ms=latency_ms)
        return msg.content, msg.tool_calls, msg
    content_parts: list[str] = []
    #工具拼装
    tc_buf: dict[int, dict] = {}  # index -> {"id", "name", "arguments"}

    stream = await client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        extra_body=extra_body,
        **({"tools": tools, "tool_choice": "auto"} if tools else {}),
        stream=True,
        stream_options={"include_usage": True},   # ★ 让最后一个 chunk 带 usage
    )
    last_usage = None
    async for chunk in stream:
        if getattr(chunk, "usage", None):          # ★ 先捕获（这个 chunk 的 choices 是空的）
            last_usage = chunk.usage
        if not chunk.choices:
            continue  # 某些服务商最后一个 chunk 的 choices 是空的
        delta = chunk.choices[0].delta
        # 思考过程单独转发（DeepSeek 的 reasoning_content 字段，和正文分开发）
        if on_reasoning and getattr(delta, "reasoning_content", None):
            await on_reasoning(delta.reasoning_content)
        if delta.content:
            content_parts.append(delta.content)
            await on_token(delta.content)  # ← 直播：收到就转发
        for tc in delta.tool_calls or []:
            slot = tc_buf.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
            if tc.id:
                slot["id"] = tc.id
            if tc.function and tc.function.name:
                slot["name"] = tc.function.name
            if tc.function and tc.function.arguments:
                slot["arguments"] += tc.function.arguments  # 累加，不是覆盖！

    content = "".join(content_parts)
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    await record_llm_call(agent_name=agent_name, usage=last_usage, latency_ms=latency_ms)

    tool_calls = [
        SimpleNamespace(id=s["id"],
                        function=SimpleNamespace(name=s["name"], arguments=s["arguments"]))
        for s in tc_buf.values()
    ]
    # 放回 messages 的必须是纯 dict：SimpleNamespace 下次请求序列化会出问题
    assistant_msg: dict = {"role": "assistant", "content": content}
    if tool_calls:
        assistant_msg["tool_calls"] = [
            {"id": s["id"], "type": "function",
             "function": {"name": s["name"], "arguments": s["arguments"]}}
            for s in tc_buf.values()
        ]
    return content, tool_calls, assistant_msg


async def run_tool_loop(
        system_prompt: str,
        tools: list[dict],
        tool_map: dict,
        query:str,
        on_progress: ProgressCallback | None = None,
        agent_name: str = "agent",
        history: list[dict] | None = None,
        on_token: TokenCallback | None = None,
        on_message: MessageCallback | None = None,   # ★ 新增
        deep_think: bool = False,                    # 只有主 agent 会传，子 agent 走默认
        on_reasoning=None,                           # 思考过程（只主 agent 传）
)->str:
    async def report(payload: dict) -> None:
        if on_progress:
            await on_progress({**payload, "agent": agent_name})
    messages = (
        [{"role": "system", "content":  system_prompt}]
        + (history or [])
        + [{"role": "user", "content": query}]
    )
    for round_i in range(MAX_ROUNDS):
        content, tool_calls, assistant_msg = await _call_model(
            messages, tools, on_token, agent_name=agent_name,
            deep_think=deep_think, on_reasoning=on_reasoning,
        )
        messages.append(assistant_msg)  # 必须把 assistant 的 tool_calls 消息加进去
        if on_message:
            await on_message(assistant_msg)

        # 模型没调工具，直接返回文本
        if not tool_calls:
            return content

        #将工具调用结果通过ws传给前端
        await report({
                "type":"progress",
                "round": round_i + 1,
                "tools": [c.function.name for c in tool_calls],
                "args": [c.function.arguments for c in tool_calls]
        })

        #工具的并发执行 每一个agent的并发设置为3
        tool_semaphore = asyncio.Semaphore(3)
        results = await asyncio.gather(*(run_tool(tool_call,tool_map,tool_semaphore) for tool_call in tool_calls))
        # 执行每个工具调用
        for tool_call,result in results:
            # 调用工具 把结果添加到messages给大模型
            tool_msg = {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result
            }
            messages.append(tool_msg)
            if on_message:
                await on_message(tool_msg)  # ★ 补上这一行，tool 结果也落库
            await report({"type": "tool_result", "tool": tool_call.function.name})

            # ★ 工具结果里带了 citations 就顺带推给前端（kb_search 专用）
            try:
                parsed = json.loads(result)
            except (TypeError, ValueError):
                parsed = None
            if isinstance(parsed, dict) and parsed.get("citations"):
                await report({
                    "type": "citations",
                    "tool": tool_call.function.name,
                    "items": parsed["citations"],
                })

    # 超过最大轮数：不带 tools 再调一次，强制模型基于已有信息收尾
    content, _, _ = await _call_model(messages, None, on_token,
                                      deep_think=deep_think, on_reasoning=on_reasoning)
    if on_message:
        await on_message({"role": "assistant", "content": content})  # ★
    return content
if __name__ == "__main__":
    ...

