from datetime import datetime

from app.agent.loop import run_tool_loop
from app.agent.weather_agent import run_weather_agent
from app.agent.search_agent import run_search_agent


MAIN_AGENT_PROMPT_TEMPLATE = """你是任务编排主智能体，负责理解用户请求、调度子智能体、汇总最终回答。
今天是 {today}，回答涉及时效性内容时以此为基准。

## 可用子智能体
- search_agent：联网搜索。适合实时信息、新闻、你不确定或可能已过时的知识。
- weather_agent：天气查询。适合任意城市的当前天气。

## 调度规则（必须遵守）
1. 动手前先判断：这个问题凭你已有的知识能不能回答好？能，就不调度任何子智能体。
2. 简单问题（单一事实、单一查询）最多调度 1 次子智能体。
3. 对比类问题（A 对比 B）最多调度 2 次。
4. 禁止在同一轮调度两个相同的子智能体。
5. 子智能体返回的结果只要足以回答用户，立即汇总作答——绝不为了"更全面"追加调度。
6. 用户请求宽泛时（如"最近的热门消息"），自行选一个合理的具体方向处理，
   不要替用户穷举多个角度。

## 汇总要求
- 基于子智能体返回的内容作答，标注信息来源；
- 子智能体给出的来源 URL 必须在回答末尾以"参考来源"一节列出，汇总时不要丢弃；
- 子智能体没覆盖到的部分如实说明，不要编造；
- 用 Markdown 输出，条理清晰。
"""

SEARCH_AGENT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_agent",
        "description": "联网搜索子智能体。需要实时信息、新闻、或你知识库之外的资料时调用。",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "要搜索的问题"}},
            "required": ["query"],
        },
    },
}

WEATHER_AGENT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "weather_agent",
        "description": "天气查询子智能体。用户询问某城市天气时调用。",
        "parameters": {
            "type": "object",
            "properties": {
                # 所有子智能体入参统一叫 query：schema 的参数名必须和
                # run_weather_agent(query=...) 的形参一字不差
                "query": {"type": "string", "description": "要查询的天气问题，例如：北京今天的天气"}
            },
            "required": ["query"],
        },
    },
}

async def run_main_agent(query: str, on_progress=None, history: list[dict] | None = None,on_token=None) -> str:
    now = datetime.now()
    today = f"{now:%Y-%m-%d} " + "周" + "一二三四五六日"[now.weekday()]
    return await run_tool_loop(
        system_prompt=MAIN_AGENT_PROMPT_TEMPLATE.format(today=today),
        tools=[SEARCH_AGENT_SCHEMA, WEATHER_AGENT_SCHEMA],
        tool_map={
            "search_agent": run_search_agent,     # ← 工具就是子智能体函数
            "weather_agent": run_weather_agent,
        },
        query=query,
        on_progress=on_progress,
        agent_name="main_agent",
        history=history,
        on_token=on_token,
    )


