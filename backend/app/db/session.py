from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from app.core.config import settings



engine = create_async_engine(settings.db_url)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

@event.listens_for(engine.sync_engine, "connect")
def _sqlite_pragmas(dbapi_conn, _):
    """每条新连接建立时都要执行这两行 —— 外键开关是连接级的，默认是关的！"""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")   # 库级配置，重复设置无副作用
    cursor.execute("PRAGMA foreign_keys=ON")    # 不设这个，ON DELETE CASCADE 就是摆设
    cursor.close()


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
