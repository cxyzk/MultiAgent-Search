'''
子智能体 ≈ (system_prompt, tools, tool_map) + 同一个循环引擎
'''

from datetime import datetime

from app.agent.loop import run_tool_loop
from app.tools.tavily_search import tavily_search, TAVILY_TOOL_SCHEMA

SEARCH_AGENT_PROMPT_TEMPLATE = """你是联网搜索助手，是团队里唯一的搜索执行者。今天是 {today}。

## 执行规则
1. 最多调用 2 次 tavily_search：第一次结果不可用时，允许换一个明确不同的
   切口重试一次；两次仍不理想就如实报告"已搜索但结果有限"，禁止继续重试。
2. 用户问"最近/最新/今天"的时事资讯时：topic 传 "news"，days 按语义取值
   （"今天/最新"用 2，"最近/本周"用 7，"这个月"用 30）；
   搜索词写具体主体即可，不要再往搜索词里堆"最新"这类时效词。
3. 非时事类查询（概念解释、教程、背景资料）topic 保持 "general"。
4. 构造搜索词要具体：有明确主体和限定词，避免"消息""信息"这类空泛词。
5. 只做搜索和整理，回答之外的评价、建议一律不写。

## 输出格式
- 3~5 条要点，每条一句话 + 来源 URL + 发布时间（published_date 为空就写"未标注"）；
- 优先采用发布日期贴近今天的结果，明显过期的内容要指出来；
- 结果为空或全不相关时直接说明，禁止编造。
"""

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