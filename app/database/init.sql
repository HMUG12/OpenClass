-- ============================================================
-- OpenClass 数据库初始化脚本 (SQLite)
-- ============================================================

-- 班级表
CREATE TABLE IF NOT EXISTS classes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 学生表
CREATE TABLE IF NOT EXISTS students (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id     INTEGER NOT NULL,
    name         TEXT    NOT NULL,
    gender       TEXT    DEFAULT '未设置' CHECK (gender IN ('男', '女', '未设置')),
    points       INTEGER DEFAULT 0,
    called_count INTEGER DEFAULT 0,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_students_class ON students(class_id);

-- 点名记录表
CREATE TABLE IF NOT EXISTS call_records (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    class_id   INTEGER NOT NULL,
    called_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (class_id)   REFERENCES classes(id)   ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_call_records_student ON call_records(student_id);
CREATE INDEX IF NOT EXISTS idx_call_records_class   ON call_records(class_id);

-- 聊天会话表
CREATE TABLE IF NOT EXISTS chat_sessions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT    NOT NULL DEFAULT '新会话',
    created_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 聊天消息表
CREATE TABLE IF NOT EXISTS chat_messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL,
    role            TEXT    NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content         TEXT    NOT NULL DEFAULT '',
    tool_calls_json TEXT    DEFAULT NULL,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);

-- API 配置表 (密钥使用 AES 加密后存储)
CREATE TABLE IF NOT EXISTS api_configs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_name   TEXT    NOT NULL UNIQUE,
    api_key_encrypted TEXT  NOT NULL DEFAULT '',
    base_url        TEXT    NOT NULL DEFAULT '',
    default_model   TEXT    NOT NULL DEFAULT '',
    is_active       INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 默认插入预设供应商
INSERT OR IGNORE INTO api_configs (provider_name, api_key_encrypted, base_url, default_model, is_active)
VALUES
    ('OpenAI',    '', 'https://api.openai.com/v1',         'gpt-4',                1),
    ('Anthropic', '', 'https://api.anthropic.com/v1',      'claude-3-opus-20240229', 0),
    ('DeepSeek',  '', 'https://api.deepseek.com/v1',       'deepseek-chat',         0),
    ('Ollama',    '', 'http://localhost:11434/v1',          'llama3',                0);

-- 插入示例班级和学生数据（便于调试）
INSERT OR IGNORE INTO classes (id, name) VALUES (1, '一年级(1)班');

INSERT OR IGNORE INTO students (class_id, name, gender) VALUES
    (1, '张三', '男'),  (1, '李四', '女'),  (1, '王五', '男'),
    (1, '赵六', '女'),  (1, '陈七', '男'),  (1, '周八', '女'),
    (1, '吴九', '男'),  (1, '郑十', '女'),  (1, '钱十一', '男'),
    (1, '孙十二', '女'), (1, '刘十三', '男'), (1, '黄十四', '女');
