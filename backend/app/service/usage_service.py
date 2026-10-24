"""LLM 调用用量：记录 + 汇总。原则：记录失败绝不能拖垮主流程。"""
import logging

from sqlalchemy import func, select

from app.core.config import settings
from app.core.context import current_task
from app.db.models import LlmCall
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


async def record_llm_call(*, agent_name: str, usage, latency_ms: int) -> None:
    """记录一次调用。usage 可能为 None（部分服务商流式不返回），记 0 即可。"""
    try:
        ctx = current_task.get() or {}
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0) if usage else 0
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0) if usage else 0
        cache_hit_tokens = int(getattr(usage, "prompt_cache_hit_tokens", 0) or 0) if usage else 0

        reasoning_tokens = 0
        details = getattr(usage, "completion_tokens_details", None) if usage else None
        if details is not None:
            reasoning_tokens = int(getattr(details, "reasoning_tokens", 0) or 0)

        async with SessionLocal() as db:
            db.add(LlmCall(
                session_id=ctx.get("session_id"),
                task_id=ctx.get("task_id"),
                agent_name=agent_name,
                model=settings.llm_model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cache_hit_tokens=cache_hit_tokens,
                reasoning_tokens=reasoning_tokens,
                latency_ms=latency_ms,
            ))
            await db.commit()

        logger.info(
            "[llm] agent=%s prompt=%d completion=%d cache_hit=%d reasoning=%d latency=%dms",
            agent_name, prompt_tokens, completion_tokens,
            cache_hit_tokens, reasoning_tokens, latency_ms,
        )
    except Exception as e:          # 观测失败不影响业务
        logger.warning("记录 LLM 用量失败: %s", e)


async def summarize_task_usage(task_id: str) -> dict:
    """按任务汇总（给 result 事件用）"""
    async with SessionLocal() as db:
        row = (await db.execute(
            select(
                func.count(LlmCall.id),
                func.coalesce(func.sum(LlmCall.prompt_tokens), 0),
                func.coalesce(func.sum(LlmCall.completion_tokens), 0),
                func.coalesce(func.sum(LlmCall.cache_hit_tokens), 0),
                func.coalesce(func.sum(LlmCall.latency_ms), 0),
            ).where(LlmCall.task_id == task_id)
        )).one()

    calls, prompt_tokens, completion_tokens, cache_hit_tokens, latency_ms = row
    return {
        "calls": calls,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "cache_hit_tokens": cache_hit_tokens,
        "llm_latency_ms": latency_ms,
    }
