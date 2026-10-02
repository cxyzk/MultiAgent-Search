'''
子智能体 ≈ (system_prompt, tools, tool_map) + 同一个循环引擎
'''

from app.agent.loop import run_tool_loop
from app.tools.tavily_search import tavily_search, TAVILY_TOOL_SCHEMA

SEARCH_AGENT_PROMPT = """你是联网搜索助手，是团队里唯一的搜索执行者。

## 执行规则
1. 只调用一次 tavily_search，这是硬性要求。结果不理想时，如实报告
   "已搜索但结果有限"，禁止换关键词反复搜索。
2. 构造搜索词要具体：有明确主体和限定词，避免"消息""信息"这类空泛词；
   用户要"最近/最新"内容时，在搜索词里带上时间限定。
3. 只做搜索和整理，回答之外的评价、建议一律不写。

## 输出格式
- 3~5 条要点，每条一句话 + 来源 URL；
- 结果里若有发布时间，注明；
- 结果为空或全不相关时直接说明，禁止编造。
"""

async def run_search_agent(query: str, on_progress=None) -> str:
    return await run_tool_loop(
        system_prompt=SEARCH_AGENT_PROMPT,
        tools=[TAVILY_TOOL_SCHEMA],
        tool_map={"tavily_search": tavily_search},
        query=query,
        on_progress=on_progress,
        agent_name="search_agent",
    )