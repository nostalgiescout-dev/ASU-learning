PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name       TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE,
    username        TEXT UNIQUE,
    password_hash   TEXT,
    role            TEXT NOT NULL CHECK (role IN ('admin', 'user')) DEFAULT 'user',
    is_active       INTEGER NOT NULL DEFAULT 1,
    avatar_url      TEXT,
    bio             TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS oauth_accounts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL,
    provider            TEXT NOT NULL,
    provider_user_id    TEXT NOT NULL,
    provider_email      TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (provider, provider_user_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS courses (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    title               TEXT NOT NULL,
    description         TEXT,
    thumbnail_url       TEXT,
    created_by          INTEGER NOT NULL,
    is_published        INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS videos (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id           INTEGER,
    title               TEXT NOT NULL,
    description         TEXT,
    video_url           TEXT NOT NULL,
    thumbnail_url       TEXT,
    created_by          INTEGER NOT NULL,
    is_published        INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS enrollments (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL,
    course_id           INTEGER NOT NULL,
    enrolled_by         INTEGER,
    enrolled_at         TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (user_id, course_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    FOREIGN KEY (enrolled_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS video_views (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL,
    video_id            INTEGER NOT NULL,
    course_id           INTEGER,
    viewed_at           TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_video_views_video_id ON video_views(video_id);
CREATE INDEX IF NOT EXISTS idx_video_views_course_id ON video_views(course_id);
CREATE INDEX IF NOT EXISTS idx_video_views_user_id ON video_views(user_id);

CREATE TABLE IF NOT EXISTS likes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL,
    video_id            INTEGER NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (user_id, video_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS comments (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL,
    video_id            INTEGER NOT NULL,
    body                TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_comments_video_id ON comments(video_id);

CREATE TABLE IF NOT EXISTS messages (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    body                TEXT NOT NULL,
    sender_id           INTEGER NOT NULL,
    receiver_id         INTEGER REFERENCES users(id),
    thread_id           INTEGER REFERENCES threads(id),
    is_ai_message       INTEGER NOT NULL DEFAULT 0,
    is_read             INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (thread_id) REFERENCES threads(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS threads (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    participant_a       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    participant_b       INTEGER REFERENCES users(id) ON DELETE CASCADE,
    is_ai_thread        INTEGER NOT NULL DEFAULT 0,
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ai_conversations (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title               TEXT,
    history_json        TEXT NOT NULL DEFAULT '[]',
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_thread_id ON messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_messages_sender_id ON messages(sender_id);
CREATE INDEX IF NOT EXISTS idx_messages_receiver_id ON messages(receiver_id);
CREATE INDEX IF NOT EXISTS idx_threads_participant_a ON threads(participant_a);
CREATE INDEX IF NOT EXISTS idx_threads_participant_b ON threads(participant_b);
CREATE INDEX IF NOT EXISTS idx_ai_conversations_user_id ON ai_conversations(user_id);

-- Analytics helper view
CREATE VIEW IF NOT EXISTS course_analytics AS
SELECT
    c.id AS course_id,
    c.title AS course_title,
    COUNT(DISTINCT e.user_id) AS enrolled_users,
    COUNT(DISTINCT vv.user_id) AS viewers,
    COUNT(DISTINCT l.id) AS total_likes,
    COUNT(DISTINCT cm.id) AS total_comments
FROM courses c
LEFT JOIN enrollments e ON e.course_id = c.id
LEFT JOIN videos v ON v.course_id = c.id
LEFT JOIN video_views vv ON vv.video_id = v.id
LEFT JOIN likes l ON l.video_id = v.id
LEFT JOIN comments cm ON cm.video_id = v.id
GROUP BY c.id, c.title;
