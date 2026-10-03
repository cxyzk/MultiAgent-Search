from openai import AsyncOpenAI
from app.core.config import settings
import json
from typing import Awaitable, Callable, Optional

MAX_ROUNDS = 8


#初始化客户端
client = AsyncOpenAI(
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
)


#运行注解
ProgressCallback = Callable[[dict], Awaitable[None]]


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


async def run_tool_loop(
        system_prompt: str,
        tools: list[dict],
        tool_map: dict,
        query:str,
        on_progress: Optional[ProgressCallback] = None,
        agent_name: str = "agent"
)->str:
    async def report(payload: dict) -> None:
        if on_progress:
            await on_progress({**payload, "agent": agent_name})
    messages = [
        {"role": "system", "content":  system_prompt},
        {"role": "user", "content": query}
    ]
    for round_i in range(MAX_ROUNDS):
        resp=await client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            tools=tools,
            tool_choice="auto",  # 让模型自己决定调不调
        )
        msg = resp.choices[0].message
        messages.append(msg)  # 必须把 assistant 的 tool_calls 消息加进去

        # 模型没调工具，直接返回文本
        if not msg.tool_calls:
            return msg.content

        #将工具调用结果通过ws传给前端
        await report({
                "type":"progress",
                "round": round_i + 1,
                "tools": [c.function.name for c in msg.tool_calls]})

        # 执行每个工具调用
        for tool_call in msg.tool_calls:
            # 调用工具 把结果添加到messages给大模型
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": await execute_tool(tool_call, tool_map),
            })
            await report({"type": "tool_result", "tool": tool_call.function.name})

    # 超过最大轮数：不带 tools 再调一次，强制模型基于已有信息收尾
    resp = await client.chat.completions.create(model=settings.llm_model, messages=messages)
    return resp.choices[0].message.content

if __name__ == "__main__":
    ...
