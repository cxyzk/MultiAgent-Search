"""请求级上下文：session_id / task_id 传给深层调用，避免层层传参。"""
from contextvars import ContextVar

current_task: ContextVar[dict | None] = ContextVar("current_task", default=None)