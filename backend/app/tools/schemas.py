"""工具参数模型：schema 由 pydantic 生成，和函数签名同源，避免手写 JSON 漂移。

注意：这里的字段就是模型能看到的"参数契约"。加 ge/le/enum 既给模型提示范围，
也方便将来在工具入口做 model_validate 校验。
"""
from typing import Literal

from pydantic import BaseModel, Field


class KbSearchArgs(BaseModel):
    """kb_search 的参数。"""

    query: str = Field(description="检索用的关键词或短句，只写主体，不要带“帮我查一下”这类话")
    top_k: int = Field(5, ge=1, le=20, description="返回片段数，默认 5")


class TavilySearchArgs(BaseModel):
    """tavily_search 的参数。"""

    query: str = Field(description="搜索关键词")
    topic: Literal["general", "news"] = Field(
        "general",
        description="general=全网综合搜索；news=新闻索引（带时效性）。"
                    "用户问最近/最新/今天的资讯时用 news。",
    )
    days: int = Field(7, ge=1, le=30, description="topic=news 时生效：只返回最近 N 天的新闻，默认 7")


class WeatherArgs(BaseModel):
    """get_weather 的参数。"""

    city: str = Field(description="城市名称，例如：北京、上海、哈尔滨")
