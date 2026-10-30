"""把 pydantic 参数模型转成 OpenAI function calling 的 tools schema。"""
import copy
from typing import Type

from pydantic import BaseModel


def _simplify(schema: dict) -> dict:
    """去掉 title / $defs：部分 provider 对这两个字段不兼容，对模型也没有意义。"""
    schema = copy.deepcopy(schema)
    schema.pop("title", None)
    defs = schema.pop("$defs", {})
    for prop in schema.get("properties", {}).values():
        ref = prop.pop("$ref", None)
        if ref and ref.startswith("#/$defs/"):
            name = ref.rsplit("/", 1)[-1]
            prop.update(copy.deepcopy(defs.get(name, {})))
            prop.pop("title", None)
    return schema


def tool_schema(name: str, description: str, args: Type[BaseModel]) -> dict:
    """生成 tools 列表里的单项；参数定义以 args 模型为唯一来源。"""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": _simplify(args.model_json_schema()),
        },
    }
