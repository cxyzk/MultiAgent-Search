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


CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT PRIMARY KEY,            -- = task_id
    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    status      TEXT NOT NULL,               -- running / done / error / interrupted
    query       TEXT NOT NULL,
    error       TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_task_session ON tasks(session_id, created_at);

CREATE TABLE IF NOT EXISTS documents (
    id         TEXT PRIMARY KEY,           -- uuid
    title      TEXT NOT NULL,              -- 展示名
    source     TEXT,                       -- 原始文件名
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chunks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    seq         INTEGER NOT NULL,          -- 文档内第几段
    content     TEXT NOT NULL,
    embedding   BLOB                       -- v2 启用：float32 向量（BLOB，非 JSON）
);
CREATE INDEX IF NOT EXISTS idx_chunk_doc ON chunks(document_id);


CREATE TABLE IF NOT EXISTS llm_calls (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        VARCHAR(64),
    task_id           VARCHAR(64),
    agent_name        VARCHAR(64)  NOT NULL,
    model             VARCHAR(128) NOT NULL,
    prompt_tokens     INTEGER      NOT NULL DEFAULT 0,
    completion_tokens INTEGER      NOT NULL DEFAULT 0,
    cache_hit_tokens  INTEGER      NOT NULL DEFAULT 0,
    reasoning_tokens  INTEGER      NOT NULL DEFAULT 0,
    latency_ms        INTEGER      NOT NULL DEFAULT 0,
    created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_llm_calls_session_id ON llm_calls (session_id);
CREATE INDEX IF NOT EXISTS ix_llm_calls_task_id    ON llm_calls (task_id);

