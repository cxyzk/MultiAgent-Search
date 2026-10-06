from openai import AsyncOpenAI
from app.core.config import settings
import json
from typing import Awaitable, Callable
from types import SimpleNamespace

MAX_ROUNDS = 8


#初始化客户端
client = AsyncOpenAI(
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
)


#运行注解
ProgressCallback = Callable[[dict], Awaitable[None]]
TokenCallback = Callable[[str], Awaitable[None]]   # 每收到一小段文本调一次


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
        result = {"error": f"工具 {func_name} 执行失败：{type(e).__name__}: {e}"}
    return json.dumps(result, ensure_ascii=False)



async def _call_model(messages, tools, on_token):
    """调一次 LLM，返回 (content, tool_calls, 放回 messages 用的 assistant 消息)。

    on_token 非空时走流式：content 增量实时转发给调用方，
    tool_calls 的增量碎片按 index 分桶拼装。
    """
    if on_token is None:
        resp=await client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            **({"tools": tools, "tool_choice": "auto"} if tools else {}),
        )
        msg = resp.choices[0].message
        return msg.content, msg.tool_calls, msg
    content_parts: list[str] = []
    #工具拼装
    tc_buf: dict[int, dict] = {}  # index -> {"id", "name", "arguments"}

    stream = await client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        **({"tools": tools, "tool_choice": "auto"} if tools else {}),
        stream=True,
    )
    async for chunk in stream:
        if not chunk.choices:
            continue  # 某些服务商最后一个 chunk 的 choices 是空的
        delta = chunk.choices[0].delta
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
        content, tool_calls, assistant_msg = await _call_model(messages, tools, on_token)
        messages.append(assistant_msg)  # 必须把 assistant 的 tool_calls 消息加进去

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

        # 执行每个工具调用
        for tool_call in tool_calls:
            # 调用工具 把结果添加到messages给大模型
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": await execute_tool(tool_call, tool_map),
            })
            await report({"type": "tool_result", "tool": tool_call.function.name})

    # 超过最大轮数：不带 tools 再调一次，强制模型基于已有信息收尾
    content, _, _ = await _call_model(messages, None, on_token)
    return content
if __name__ == "__main__":
    ...

