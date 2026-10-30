from app.agent.loop import run_tool_loop
from app.prompt.weather import WEATHER_AGENT_PROMPT
from app.tools.weather import get_weather, WEATHER_TOOL_SCHEMA

async def run_weather_agent(query: str, on_progress=None) -> str:
    return await run_tool_loop(
        system_prompt=WEATHER_AGENT_PROMPT,
        tools=[WEATHER_TOOL_SCHEMA],
        tool_map={"get_weather": get_weather},
        query=query,
        on_progress=on_progress,
        agent_name="weather_agent",
    )