import os

# ★★★ 必须在 import app 之前执行 ★★★
# 1) DB_URL：强制指向测试库（覆盖 .env）
os.environ["DB_URL"] = "sqlite+aiosqlite:///./test_app.db"

# 2) Settings 的其余必填字段：CI 环境没有 .env，缺了会 ValidationError（import app 就炸）。
#    测试全程不真调 LLM（mock 掉了），占位值即可。
os.environ.setdefault("LLM_BASE_URL", "http://localhost:9/v1")
os.environ.setdefault("LLM_API_KEY", "test-key")
os.environ.setdefault("LLM_MODEL", "test-model")

# 3) Rerank：测试不真调 rerank API（慢且消耗额度），固定关掉
os.environ["RERANK_ENABLED"] = "false"

# 4) Embedding：测试同样不调外部 API（入库会降级为纯 BM25）
os.environ["EMBEDDING_API_KEY"] = ""

# 5) 查询改写：测试不调 LLM
os.environ["QUERY_REWRITE_ENABLED"] = "false"

import pytest
import pytest_asyncio
from sqlalchemy import text
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.db.session import engine, SessionLocal
from app.db.models import Base
from app.kb.retriever import bm25_retriever

TEST_DB = "test_app.db"


@pytest_asyncio.fixture(scope="session")
async def _schema():
    """整个测试会话建一次表；结束后删库文件"""
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


@pytest_asyncio.fixture(autouse=True)
async def _clean(_schema):
    """每个测试前清空数据（子表 → 父表）+ 重置 BM25 内存索引"""
    async with SessionLocal() as db:
        for table in ("chunks", "documents", "tasks", "messages", "sessions"):
            await db.execute(text(f"DELETE FROM {table}"))
        await db.commit()
    bm25_retriever.mark_dirty()  # ★ 全局单例，不重置会带着上个测试的索引
    yield


@pytest_asyncio.fixture
async def db_session():
    async with SessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    """不真的起 uvicorn：ASGITransport 直接在进程内调 app"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
def mock_agent(monkeypatch):
    """把 LLM 调用换成假 agent：不花钱、不联网，但照样触发回调（落库/推送都靠它）"""
    import app.service.task_service as task_service_module

    async def fake_run(query, on_progress=None, history=None,
                       on_token=None, on_message=None, **kwargs):
        if on_message:
            await on_message({"role": "assistant", "content": "固定回答"})
        return "固定回答"

    monkeypatch.setattr(task_service_module, "run_main_agent", fake_run)
    return fake_run
