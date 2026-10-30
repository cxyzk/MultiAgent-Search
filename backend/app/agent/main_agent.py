from datetime import datetime

from app.agent.loop import run_tool_loop
from app.prompt.main import MAIN_AGENT_PROMPT_TEMPLATE
from app.agent.weather_agent import run_weather_agent
from app.agent.search_agent import run_search_agent
from app.tools.kb_search import kb_search, KB_SEARCH_TOOL_SCHEMA

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

async def run_main_agent(query: str, on_progress=None, history: list[dict] | None = None,
                         on_token=None, on_message=None, deep_think: bool = False,
                         on_reasoning=None, allow_search: bool = True) -> str:
    now = datetime.now()
    today = f"{now:%Y-%m-%d} " + "周" + "一二三四五六日"[now.weekday()]

    system_prompt = MAIN_AGENT_PROMPT_TEMPLATE.format(today=today)
    tools = [KB_SEARCH_TOOL_SCHEMA, WEATHER_AGENT_SCHEMA]
    tool_map = {"kb_search": kb_search, "weather_agent": run_weather_agent}

    if allow_search:
        tools.append(SEARCH_AGENT_SCHEMA)
        tool_map["search_agent"] = run_search_agent
    else:
        # 关掉「智能搜索」= 真正禁止联网：工具直接不给，避免模型自己决定去搜
        system_prompt += (
            "\n\n【系统限制】用户已关闭联网搜索：search_agent 工具不可用。"
            "不要尝试联网、也不要承诺稍后重试；基于已有知识回答，"
            "对可能过时的信息如实说明。"
        )

    return await run_tool_loop(
        system_prompt=system_prompt,
        tools=tools,
        tool_map=tool_map,
        query=query,
        on_progress=on_progress,
        agent_name="main_agent",
        history=history,
        on_token=on_token,
        on_message=on_message,
        deep_think=deep_think,
        on_reasoning=on_reasoning,
    )


