'''
子智能体 ≈ (system_prompt, tools, tool_map) + 同一个循环引擎
'''

from datetime import datetime

from app.agent.loop import run_tool_loop
from app.prompt.search import SEARCH_AGENT_PROMPT_TEMPLATE
from app.tools.tavily_search import tavily_search, TAVILY_TOOL_SCHEMA

async def run_search_agent(query: str, on_progress=None) -> str:
    now = datetime.now()
    today = f"{now:%Y-%m-%d} " + "周" + "一二三四五六日"[now.weekday()]
    return await run_tool_loop(
        system_prompt=SEARCH_AGENT_PROMPT_TEMPLATE.format(today=today),
        tools=[TAVILY_TOOL_SCHEMA],
        tool_map={"tavily_search": tavily_search},
        query=query,
        on_progress=on_progress,
        agent_name="search_agent",
    )