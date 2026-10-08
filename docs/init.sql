CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,              -- 前端生成的 session_id（uuid）
    title       TEXT NOT NULL DEFAULT '',      -- 首条用户消息截断，给侧边栏用
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,  -- 回填排序就靠它
    session_id   TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role         TEXT NOT NULL,                      -- user / assistant / tool
    content      TEXT NOT NULL DEFAULT '',
    tool_calls   TEXT,                               -- JSON，assistant 中间轮才有
    tool_call_id TEXT,                               -- tool 消息才有
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_msg_session ON messages(session_id, id);
