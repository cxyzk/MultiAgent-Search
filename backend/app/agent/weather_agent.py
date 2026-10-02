from app.agent.loop import run_tool_loop
from app.tools.weather import get_weather, WEATHER_TOOL_SCHEMA

WEATHER_AGENT_PROMPT = "你是天气查询助手。只负责查询天气，回答简洁，直接给出关键数据。"

async def run_weather_agent(query: str, on_progress=None) -> str:
    return await run_tool_loop(
        system_prompt=WEATHER_AGENT_PROMPT,
        tools=[WEATHER_TOOL_SCHEMA],
        tool_map={"get_weather": get_weather},
        query=query,
        on_progress=on_progress,
        agent_name="weather_agent",
    )