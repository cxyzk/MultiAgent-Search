from datetime import datetime
from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class Session(Base):
    """会话：title 取首条用户消息，供侧边栏展示"""
    __tablename__ = "sessions"
    #uuid生成的会话id
    id:Mapped[str]=mapped_column(String(64),primary_key=True)
    title:Mapped[str]=mapped_column(String(64),default='')
    created_at:Mapped[datetime]=mapped_column(default=datetime.now)
    updated_at:Mapped[datetime]=mapped_column(default=datetime.now)


class Message(Base):
    __tablename__ = "messages"
    id:Mapped[int]=mapped_column(primary_key=True,autoincrement=True)
    session_id:Mapped[str]=mapped_column(String(64),ForeignKey("sessions.id",ondelete="CASCADE"))
    role:Mapped[str]=mapped_column(String(16))
    content:Mapped[str]=mapped_column(Text)
    tool_calls: Mapped[str | None] = mapped_column(Text)
    tool_call_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

    # 最热的查询是"取某会话最近 N 条"，这个联合索引刚好覆盖
    __table_args__ = (Index("idx_msg_session", "session_id", "id"),)


class Task(Base):
    """任务：一次提问的执行记录，status = running / done / error / interrupted"""
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sessions.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16))
    query: Mapped[str] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    finished_at: Mapped[datetime | None] = mapped_column()

    __table_args__ = (Index("idx_task_session", "session_id", "created_at"),)
