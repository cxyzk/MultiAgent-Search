from openai import AsyncOpenAI
from app.core.config import settings
from app.tools.weather import get_weather,WEATHER_TOOL_SCHEMA
import json
from typing import Awaitable, Callable, Optional

# 工具名 -> 函数 的映射
TOOL_MAP = {"get_weather": get_weather}
MAX_ROUNDS = 8


#初始化客户端
client = AsyncOpenAI(
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
)
SYSTEM_PROMPT = "你是一个助手，需要外部信息时调用提供的工具，然后基于工具结果回答用户。当用户查询的数据量过大时，可以抽样选择工具的调用次数。"
# 进度回调的类型：一个收 dict 的 async 函数。agent 层只管"喊"，不知道 WS 的存在
#运行注解
ProgressCallback = Callable[[dict], Awaitable[None]]

async def execute_tool(tool_call) -> str:
    """执行单个工具调用，返回回填给模型的结果字符串。以后超时/重试也加在这里"""
    func_name = tool_call.function.name
    args = json.loads(tool_call.function.arguments)
    func = TOOL_MAP.get(func_name)
    #这里的**把这个字典拆成关键字参数传给函数了 类似于func(city="上海")
    result = await func(**args) if func else {"error": f"未知工具：{func_name}"}
    return json.dumps(result, ensure_ascii=False)


async def run_agent(message, on_progress: Optional[ProgressCallback] = None):
    async def report(payload: dict) -> None:
        if on_progress:
            await on_progress(payload)
    messages = [
        {"role": "user", "content": message},
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    for round_i in range(MAX_ROUNDS):
        resp=await client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            tools=[WEATHER_TOOL_SCHEMA],
            tool_choice="auto",  # 让模型自己决定调不调
        )
        msg = resp.choices[0].message
        messages.append(msg)  # 必须把 assistant 的 tool_calls 消息加进去
        # 模型没调工具，直接返回文本
        if not msg.tool_calls:
            return msg.content
            # 执行每个工具调用
        await report({"tool_calls": [c.id for c in msg.tool_calls]})


        for tool_call in msg.tool_calls:
            # 调用工具 把结果添加到messages给大模型
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": await execute_tool(tool_call),
            })
            await report({"type": "tool_result", "tool": tool_call.function.name})
    # 超过最大轮数：不带 tools 再调一次，强制模型基于已有信息收尾
    resp = await client.chat.completions.create(model=settings.llm_model, messages=messages)
    return resp.choices[0].message.content

if __name__ == "__main__":
    ...
