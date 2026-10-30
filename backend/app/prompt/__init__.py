"""各智能体的 system prompt。

集中放在这里的原因：
- 改调度规则/输出格式时只看一个文件，不用在 agent 实现里翻；
- 便于配合 eval/ 做"改一处 prompt、跑一次评测"的回归对比；
- 将来做 A/B 或多语言时，只需多一个常量。
"""
from app.prompt.main import MAIN_AGENT_PROMPT_TEMPLATE
from app.prompt.search import SEARCH_AGENT_PROMPT_TEMPLATE
from app.prompt.weather import WEATHER_AGENT_PROMPT

__all__ = [
    "MAIN_AGENT_PROMPT_TEMPLATE",
    "SEARCH_AGENT_PROMPT_TEMPLATE",
    "WEATHER_AGENT_PROMPT",
]
