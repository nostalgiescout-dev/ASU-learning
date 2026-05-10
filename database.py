"""
database.py — Academic Kechafa LMS
Thin SQLite wrapper using Python's built-in sqlite3 module.
No ORM required — pure SQL with a dict-row factory.
"""

import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.environ.get("KECHAFA_DB", "kechafa.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row          # rows accessible as dicts
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def db():
    """Context manager: auto-commit on success, rollback on error."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetchone(sql: str, params: tuple = ()):
    with db() as conn:
        row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def fetchall(sql: str, params: tuple = ()):
    with db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def execute(sql: str, params: tuple = ()):
    with db() as conn:
        cur = conn.execute(sql, params)
        return cur.lastrowid


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row["name"] == column for row in rows)


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    if not _column_exists(conn, table, column):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _table_has_rows(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
    return row is not None


def init_db():
    """Create all tables and seed demo data."""
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            username        TEXT UNIQUE NOT NULL,
            email           TEXT UNIQUE NOT NULL,
            password_hash   TEXT NOT NULL,
            full_name       TEXT,
            bio             TEXT,
            avatar_url      TEXT DEFAULT 'https://api.dicebear.com/7.x/thumbs/svg?seed=kechafa',
            country         TEXT,
            scout_unit      TEXT,
            role            TEXT NOT NULL DEFAULT 'scout',
            is_active       INTEGER NOT NULL DEFAULT 1,
            level_points    INTEGER NOT NULL DEFAULT 0,
            level_rank      INTEGER NOT NULL DEFAULT 1,
            streak_days     INTEGER NOT NULL DEFAULT 0,
            total_reels_watched INTEGER NOT NULL DEFAULT 0,
            preferred_lang  TEXT NOT NULL DEFAULT 'en',
            created_at      TEXT DEFAULT (datetime('now')),
            last_seen       TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS courses (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            title           TEXT NOT NULL,
            title_ar        TEXT,
            description     TEXT,
            thumbnail_url   TEXT,
            language        TEXT NOT NULL DEFAULT 'en',
            category        TEXT NOT NULL DEFAULT 'general',
            difficulty      TEXT NOT NULL DEFAULT 'beginner',
            xp_reward       INTEGER NOT NULL DEFAULT 500,
            duration_mins   INTEGER,
            is_published    INTEGER NOT NULL DEFAULT 0,
            is_featured     INTEGER NOT NULL DEFAULT 0,
            instructor_id   INTEGER NOT NULL REFERENCES users(id),
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS course_categories (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE,
            slug        TEXT NOT NULL UNIQUE,
            description TEXT,
            emoji       TEXT NOT NULL DEFAULT '📚',
            created_by  INTEGER REFERENCES users(id),
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS books (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            description TEXT,
            file_path   TEXT NOT NULL,
            cover_image_path TEXT,
            language    TEXT NOT NULL CHECK(language IN ('en','fr','ar','es')) DEFAULT 'en',
            uploaded_by INTEGER NOT NULL REFERENCES users(id),
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS book_access (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            book_id     INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            granted_by  INTEGER REFERENCES users(id),
            created_at  TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, book_id)
        );

        CREATE TABLE IF NOT EXISTS book_categories (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE,
            slug        TEXT NOT NULL UNIQUE,
            description TEXT,
            created_by  INTEGER REFERENCES users(id),
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS enrollments (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL REFERENCES users(id),
            course_id       INTEGER NOT NULL REFERENCES courses(id),
            progress_pct    REAL NOT NULL DEFAULT 0.0,
            is_completed    INTEGER NOT NULL DEFAULT 0,
            enrolled_at     TEXT DEFAULT (datetime('now')),
            completed_at    TEXT,
            UNIQUE(user_id, course_id)
        );

        CREATE TABLE IF NOT EXISTS course_access_requests (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            requester_id    INTEGER NOT NULL REFERENCES users(id),
            course_id       INTEGER NOT NULL REFERENCES courses(id),
            status          TEXT NOT NULL DEFAULT 'pending',
            note            TEXT,
            responded_by    INTEGER REFERENCES users(id),
            responded_at    TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS videos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            title           TEXT NOT NULL,
            title_ar        TEXT,
            description     TEXT,
            video_url       TEXT NOT NULL,
            thumbnail_url   TEXT,
            video_type      TEXT NOT NULL DEFAULT 'reel',
            category        TEXT NOT NULL DEFAULT 'general',
            duration_secs   INTEGER,
            order_index     INTEGER NOT NULL DEFAULT 0,
            view_count      INTEGER NOT NULL DEFAULT 0,
            xp_reward       INTEGER NOT NULL DEFAULT 50,
            is_published    INTEGER NOT NULL DEFAULT 1,
            uploader_id     INTEGER NOT NULL REFERENCES users(id),
            course_id       INTEGER REFERENCES courses(id),
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS lesson_completions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL REFERENCES users(id),
            course_id       INTEGER NOT NULL REFERENCES courses(id),
            video_id        INTEGER NOT NULL REFERENCES videos(id),
            quiz_answer     TEXT,
            quiz_score      REAL NOT NULL DEFAULT 0,
            completed_at    TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, video_id)
        );

        CREATE TABLE IF NOT EXISTS lesson_quiz_questions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id       INTEGER NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
            question_text   TEXT NOT NULL,
            option_a        TEXT NOT NULL,
            option_b        TEXT NOT NULL,
            option_c        TEXT,
            option_d        TEXT,
            correct_option  TEXT NOT NULL,
            explanation     TEXT,
            order_index     INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_lesson_quiz_questions_lesson
        ON lesson_quiz_questions (lesson_id, order_index, id);

        CREATE TABLE IF NOT EXISTS comments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            body        TEXT NOT NULL,
            author_id   INTEGER NOT NULL REFERENCES users(id),
            video_id    INTEGER NOT NULL REFERENCES videos(id),
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS likes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            video_id    INTEGER NOT NULL REFERENCES videos(id),
            UNIQUE(user_id, video_id)
        );

        CREATE TABLE IF NOT EXISTS feed_posts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            author_id       INTEGER NOT NULL REFERENCES users(id),
            post_type       TEXT NOT NULL,
            title           TEXT NOT NULL,
            body            TEXT,
            media_url       TEXT,
            thumbnail_url   TEXT,
            category        TEXT,
            course_id       INTEGER REFERENCES courses(id),
            book_id         INTEGER REFERENCES books(id),
            is_pinned       INTEGER NOT NULL DEFAULT 0,
            is_published    INTEGER NOT NULL DEFAULT 1,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS post_likes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            post_id     INTEGER NOT NULL REFERENCES feed_posts(id) ON DELETE CASCADE,
            created_at  TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, post_id)
        );

        CREATE TABLE IF NOT EXISTS post_comments (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id     INTEGER NOT NULL REFERENCES feed_posts(id) ON DELETE CASCADE,
            author_id   INTEGER NOT NULL REFERENCES users(id),
            body        TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS post_shares (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id     INTEGER NOT NULL REFERENCES feed_posts(id) ON DELETE CASCADE,
            user_id     INTEGER REFERENCES users(id),
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS friend_requests (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id       INTEGER NOT NULL REFERENCES users(id),
            receiver_id     INTEGER NOT NULL REFERENCES users(id),
            status          TEXT NOT NULL DEFAULT 'pending',
            created_at      TEXT DEFAULT (datetime('now')),
            responded_at    TEXT,
            UNIQUE(sender_id, receiver_id)
        );

        CREATE TABLE IF NOT EXISTS badges (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT UNIQUE NOT NULL,
            icon            TEXT DEFAULT '🏅',
            color           TEXT DEFAULT '#f59e0b',
            description     TEXT,
            xp_value        INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS user_badges (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            badge_id    INTEGER NOT NULL REFERENCES badges(id),
            awarded_at  TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, badge_id)
        );

        CREATE TABLE IF NOT EXISTS messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            body            TEXT NOT NULL,
            sender_id       INTEGER NOT NULL REFERENCES users(id),
            receiver_id     INTEGER REFERENCES users(id),
            thread_id       INTEGER REFERENCES threads(id),
            is_ai_message   INTEGER NOT NULL DEFAULT 0,
            is_read         INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS threads (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            participant_a   INTEGER NOT NULL REFERENCES users(id),
            participant_b   INTEGER REFERENCES users(id),
            is_ai_thread    INTEGER NOT NULL DEFAULT 0,
            updated_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS ai_conversations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL REFERENCES users(id),
            title           TEXT,
            history_json    TEXT NOT NULL DEFAULT '[]',
            updated_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS app_settings (
            key         TEXT PRIMARY KEY,
            value       TEXT NOT NULL DEFAULT '',
            updated_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            kind        TEXT NOT NULL DEFAULT 'info',
            title       TEXT NOT NULL,
            body        TEXT,
            target_url  TEXT,
            entity_type TEXT,
            entity_id   INTEGER,
            actor_id    INTEGER REFERENCES users(id),
            icon        TEXT DEFAULT '🔔',
            is_read     INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS community_groups (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT UNIQUE NOT NULL,
            description TEXT,
            region      TEXT,
            owner_id    INTEGER NOT NULL REFERENCES users(id),
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS group_members (
            group_id    INTEGER NOT NULL REFERENCES community_groups(id),
            user_id     INTEGER NOT NULL REFERENCES users(id),
            PRIMARY KEY(group_id, user_id)
        );
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS contact_submissions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            email       TEXT NOT NULL,
            message     TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'pending',
            is_verified INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now')),
            verified_at TEXT
        )""")
        _ensure_column(conn, "contact_submissions", "status", "TEXT NOT NULL DEFAULT 'pending'")
        conn.execute(
            "UPDATE contact_submissions SET status='verified' WHERE is_verified=1 AND status='pending'"
        )
        _ensure_column(conn, "users", "is_verified", "INTEGER NOT NULL DEFAULT 1")
        _ensure_column(conn, "videos", "quiz_question", "TEXT")
        _ensure_column(conn, "videos", "quiz_option_a", "TEXT")
        _ensure_column(conn, "videos", "quiz_option_b", "TEXT")
        _ensure_column(conn, "videos", "quiz_option_c", "TEXT")
        _ensure_column(conn, "videos", "quiz_option_d", "TEXT")
        _ensure_column(conn, "videos", "quiz_correct_option", "TEXT")
        _ensure_column(conn, "videos", "quiz_explanation", "TEXT")
        _ensure_column(conn, "books", "category_id", "INTEGER REFERENCES book_categories(id)")
        _ensure_column(conn, "books", "cover_image_path", "TEXT")
        _ensure_column(conn, "course_categories", "emoji", "TEXT NOT NULL DEFAULT '📚'")
        _ensure_column(conn, "ai_conversations", "title", "TEXT")
        _ensure_column(conn, "enrollments", "granted_by", "INTEGER REFERENCES users(id)")
        _ensure_column(conn, "feed_posts", "thumbnail_url", "TEXT")
        _ensure_column(conn, "feed_posts", "category", "TEXT")
        _ensure_column(conn, "feed_posts", "course_id", "INTEGER REFERENCES courses(id)")
        _ensure_column(conn, "feed_posts", "book_id", "INTEGER REFERENCES books(id)")
        _ensure_column(conn, "feed_posts", "is_pinned", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "feed_posts", "is_published", "INTEGER NOT NULL DEFAULT 1")
        _ensure_column(conn, "notifications", "target_url", "TEXT")
        _ensure_column(conn, "notifications", "entity_type", "TEXT")
        _ensure_column(conn, "notifications", "entity_id", "INTEGER")
        _ensure_column(conn, "notifications", "actor_id", "INTEGER REFERENCES users(id)")
        _ensure_column(conn, "course_access_requests", "note", "TEXT")
        _ensure_column(conn, "course_access_requests", "responded_by", "INTEGER REFERENCES users(id)")
        _ensure_column(conn, "course_access_requests", "responded_at", "TEXT")
        _ensure_column(conn, "courses", "language", "TEXT NOT NULL DEFAULT 'en'")
        conn.execute(
            """
            INSERT INTO lesson_quiz_questions
                (lesson_id, question_text, option_a, option_b, option_c, option_d, correct_option, explanation, order_index)
            SELECT
                v.id,
                v.quiz_question,
                COALESCE(v.quiz_option_a, ''),
                COALESCE(v.quiz_option_b, ''),
                v.quiz_option_c,
                v.quiz_option_d,
                v.quiz_correct_option,
                v.quiz_explanation,
                1
            FROM videos v
            WHERE COALESCE(TRIM(v.quiz_question), '') <> ''
              AND COALESCE(TRIM(v.quiz_correct_option), '') <> ''
              AND NOT EXISTS (
                  SELECT 1
                  FROM lesson_quiz_questions q
                  WHERE q.lesson_id = v.id
              )
            """
        )

        if not _table_has_rows(conn, "course_categories"):
            admin_user = conn.execute(
                "SELECT id FROM users WHERE role='admin' ORDER BY id LIMIT 1"
            ).fetchone()
            created_by = admin_user["id"] if admin_user else None
            default_course_categories = [
                ("Knots", "knot-tying", "Scout knot techniques and rope skills", "🪢"),
                ("First Aid", "first-aid", "Emergency response and field safety", "🩺"),
                ("Navigation", "navigation", "Maps, compass work, and orientation", "🧭"),
                ("Camping", "camping", "Outdoor living and campsite readiness", "🏕️"),
                ("Leadership", "leadership", "Teamwork, responsibility, and leading others", "🌟"),
                ("General", "general", "General scout learning tracks", "📚"),
            ]
            conn.executemany(
                "INSERT INTO course_categories (name, slug, description, emoji, created_by) VALUES (?, ?, ?, ?, ?)",
                [(name, slug, description, emoji, created_by) for name, slug, description, emoji in default_course_categories],
            )

        existing_course_slugs = {
            row["slug"] for row in conn.execute("SELECT slug FROM course_categories").fetchall()
        }
        discovered_slugs = {
            row["category"] for row in conn.execute(
                "SELECT DISTINCT category FROM courses WHERE category IS NOT NULL AND TRIM(category) <> ''"
            ).fetchall()
        }
        for slug in sorted(discovered_slugs):
            if slug in existing_course_slugs:
                continue
            conn.execute(
                "INSERT INTO course_categories (name, slug, description, emoji, created_by) VALUES (?, ?, ?, ?, ?)",
                (slug.replace("-", " ").title(), slug, "Imported from existing course data", "📚", None),
            )

        if not _table_has_rows(conn, "book_categories"):
            admin_user = conn.execute(
                "SELECT id FROM users WHERE role='admin' ORDER BY id LIMIT 1"
            ).fetchone()
            created_by = admin_user["id"] if admin_user else None
            conn.execute(
                "INSERT INTO book_categories (name, slug, description, created_by) VALUES (?, ?, ?, ?)",
                ("General", "general", "Default library category", created_by),
            )

        default_category = conn.execute(
            "SELECT id FROM book_categories ORDER BY CASE WHEN slug='general' THEN 0 ELSE 1 END, id LIMIT 1"
        ).fetchone()
        if default_category:
            conn.execute(
                "UPDATE books SET category_id=? WHERE category_id IS NULL",
                (default_category["id"],),
            )

        if not _table_has_rows(conn, "feed_posts"):
            admin_user = conn.execute(
                "SELECT id FROM users WHERE role IN ('admin', 'instructor') ORDER BY CASE WHEN role='admin' THEN 0 ELSE 1 END, id LIMIT 1"
            ).fetchone()
            author_id = admin_user["id"] if admin_user else None

            if author_id:
                conn.execute(
                    """
                    INSERT INTO feed_posts (author_id, post_type, title, body, is_pinned)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        author_id,
                        "text",
                        "Welcome to the Community Feed",
                        "Share text updates, publish new training clips, announce courses, and highlight useful library books here.",
                        1,
                    ),
                )

            existing_videos = conn.execute(
                """
                SELECT uploader_id, title, description, video_url, thumbnail_url, category, video_type, created_at
                FROM videos
                WHERE is_published=1 AND video_type IN ('video', 'reel')
                ORDER BY created_at DESC
                LIMIT 6
                """
            ).fetchall()
            for video in existing_videos:
                conn.execute(
                    """
                    INSERT INTO feed_posts (
                        author_id, post_type, title, body, media_url, thumbnail_url, category, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        video["uploader_id"],
                        video["video_type"],
                        video["title"],
                        video["description"],
                        video["video_url"],
                        video["thumbnail_url"],
                        video["category"],
                        video["created_at"],
                    ),
                )

            featured_course = conn.execute(
                "SELECT id, instructor_id, title, description, category FROM courses WHERE is_published=1 ORDER BY is_featured DESC, created_at DESC LIMIT 1"
            ).fetchone()
            if featured_course:
                conn.execute(
                    """
                    INSERT INTO feed_posts (author_id, post_type, title, body, category, course_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        featured_course["instructor_id"],
                        "course_announcement",
                        f"Course Spotlight: {featured_course['title']}",
                        featured_course["description"],
                        featured_course["category"],
                        featured_course["id"],
                    ),
                )

            latest_book = conn.execute(
                "SELECT id, uploaded_by, title, description FROM books ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            if latest_book:
                conn.execute(
                    """
                    INSERT INTO feed_posts (author_id, post_type, title, body, book_id)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        latest_book["uploaded_by"],
                        "book_announcement",
                        f"Library Update: {latest_book['title']}",
                        latest_book["description"],
                        latest_book["id"],
                    ),
                )

    _seed()
    _seed_feed_posts()


# ──────────────────────────────────────────────
#  SEED
# ──────────────────────────────────────────────

def _seed_feed_posts():
    if fetchone("SELECT id FROM feed_posts LIMIT 1"):
        return

    admin_user = fetchone(
        "SELECT id FROM users WHERE role IN ('admin', 'instructor') ORDER BY CASE WHEN role='admin' THEN 0 ELSE 1 END, id LIMIT 1"
    )
    author_id = admin_user["id"] if admin_user else None

    if author_id:
        execute(
            "INSERT INTO feed_posts (author_id, post_type, title, body, is_pinned) VALUES (?, ?, ?, ?, ?)",
            (
                author_id,
                "text",
                "Welcome to the Community Feed",
                "Share text updates, publish new training clips, announce courses, and highlight useful library books here.",
                1,
            ),
        )

    existing_videos = fetchall(
        """
        SELECT uploader_id, title, description, video_url, thumbnail_url, category, video_type, created_at
        FROM videos
        WHERE is_published=1 AND video_type IN ('video', 'reel')
        ORDER BY created_at DESC
        LIMIT 6
        """
    )
    for video in existing_videos:
        execute(
            """
            INSERT INTO feed_posts (
                author_id, post_type, title, body, media_url, thumbnail_url, category, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                video["uploader_id"],
                video["video_type"],
                video["title"],
                video["description"],
                video["video_url"],
                video["thumbnail_url"],
                video["category"],
                video["created_at"],
            ),
        )

    featured_course = fetchone(
        "SELECT id, instructor_id, title, description, category FROM courses WHERE is_published=1 ORDER BY is_featured DESC, created_at DESC LIMIT 1"
    )
    if featured_course:
        execute(
            "INSERT INTO feed_posts (author_id, post_type, title, body, category, course_id) VALUES (?, ?, ?, ?, ?, ?)",
            (
                featured_course["instructor_id"],
                "course_announcement",
                f"Course Spotlight: {featured_course['title']}",
                featured_course["description"],
                featured_course["category"],
                featured_course["id"],
            ),
        )

    latest_book = fetchone(
        "SELECT id, uploaded_by, title, description FROM books ORDER BY created_at DESC LIMIT 1"
    )
    if latest_book:
        execute(
            "INSERT INTO feed_posts (author_id, post_type, title, body, book_id) VALUES (?, ?, ?, ?, ?)",
            (
                latest_book["uploaded_by"],
                "book_announcement",
                f"Library Update: {latest_book['title']}",
                latest_book["description"],
                latest_book["id"],
            ),
        )


def _seed():
    from werkzeug.security import generate_password_hash

    if fetchone("SELECT id FROM users LIMIT 1"):
        return  # already seeded

    users = [
        ("kechafa_admin",    "admin@kechafa.ma",       "Admin@1234",       "Kechafa Admin",      "admin",      15000, 15, "ar"),
        ("lead_instructor",  "instructor@kechafa.ma",  "Instructor@1234",  "Youssef El Fassi",   "instructor", 10500, 10, "fr"),
        ("scout_sara",       "sara@kechafa.ma",        "Scout@1234",       "Sara Benali",        "scout",      2340,  2,  "ar"),
    ]
    user_ids = {}
    for uname, email, pwd, fname, role, xp, rank, lang in users:
        uid = execute(
            "INSERT INTO users (username,email,password_hash,full_name,role,level_points,level_rank,preferred_lang,scout_unit,bio) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (uname, email, generate_password_hash(pwd), fname, role, xp, rank, lang,
             "National HQ" if role=="admin" else "Rabat Group 3" if role=="instructor" else "Casablanca Group 7",
             "Lead administrator." if role=="admin" else "Certified trainer." if role=="instructor" else "Enthusiastic scout.")
        )
        user_ids[uname] = uid

    inst_id  = user_ids["lead_instructor"]
    admin_id = user_ids["kechafa_admin"]

    badges = [
        ("First Steps",     "🥾", "#10b981", "Welcome to the platform",            0),
        ("Knot Master",     "🪢", "#2563eb", "Complete the Knot Tying course",    200),
        ("First Aid Hero",  "🩺", "#ef4444", "Complete the First Aid course",     300),
        ("7-Day Streak",    "🔥", "#f59e0b", "Login 7 days in a row",             100),
        ("Navigator",       "🧭", "#8b5cf6", "Complete the Navigation course",    250),
        ("Community Leader","🌟", "#f97316", "Awarded by admin",                  500),
    ]
    badge_ids = {}
    for name, icon, color, desc, xp in badges:
        bid = execute("INSERT INTO badges (name,icon,color,description,xp_value) VALUES (?,?,?,?,?)",
                      (name, icon, color, desc, xp))
        badge_ids[name] = bid

    # Give admin & instructor the First Steps badge
    execute("INSERT INTO user_badges (user_id,badge_id) VALUES (?,?)", (admin_id, badge_ids["First Steps"]))
    execute("INSERT INTO user_badges (user_id,badge_id) VALUES (?,?)", (inst_id,  badge_ids["First Steps"]))
    execute("INSERT INTO user_badges (user_id,badge_id) VALUES (?,?)", (inst_id,  badge_ids["Knot Master"]))

    courses_data = [
        ("Knot Tying Fundamentals",    "أساسيات ربط العقد",    "knot-tying",  "beginner",     500, 45,  1, 1,
         "Master 12 essential knots every scout needs to know.",
         "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=600&q=80"),
        ("First Aid in the Field",     "الإسعافات الأولية",     "first-aid",   "intermediate", 800, 90,  1, 1,
         "Emergency response techniques for outdoor environments.",
         "https://images.unsplash.com/photo-1544991936-9464fa4b0c46?w=600&q=80"),
        ("Map & Compass Navigation",   "التنقل بالخريطة",      "navigation",  "intermediate", 600, 60,  1, 0,
         "Traditional orienteering skills for backcountry adventure.",
         "https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1?w=600&q=80"),
        ("Leadership & Team Dynamics", "القيادة وديناميكيات الفريق","leadership","advanced", 1000,120, 1, 0,
         "Build the skills to inspire and guide your scout troop.",
         "https://images.unsplash.com/photo-1521737604893-d14cc237f11d?w=600&q=80"),
    ]
    course_ids = []
    for title, title_ar, cat, diff, xp, dur, pub, feat, desc, thumb in courses_data:
        cid = execute(
            "INSERT INTO courses (title,title_ar,description,thumbnail_url,category,difficulty,xp_reward,duration_mins,is_published,is_featured,instructor_id) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (title, title_ar, desc, thumb, cat, diff, xp, dur, pub, feat, inst_id)
        )
        course_ids.append(cid)

    demo_video = "https://www.w3schools.com/html/mov_bbb.mp4"
    videos_data = [
        ("Bowline Knot in 60 Seconds",   "عقدة القوس في 60 ثانية",  "knot-tying", 62,  50, "lesson", course_ids[0], 1,
         "https://images.unsplash.com/photo-1578985545062-69928b1d9587?w=400&q=80"),
        ("Figure-Eight Knot Tutorial",   "عقدة الرقم ثمانية",      "knot-tying", 55,  50, "lesson", course_ids[0], 2,
         "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=400&q=80"),
        ("CPR Step-by-Step",             "خطوات الإنعاش القلبي",   "first-aid",  88,  75, "lesson", course_ids[1], 1,
         "https://images.unsplash.com/photo-1544991936-9464fa4b0c46?w=400&q=80"),
        ("Reading a Topographic Map",    "قراءة الخريطة الطبوغرافية","navigation",75, 60, "lesson", course_ids[2], 1,
         "https://images.unsplash.com/photo-1476514525535-07fb3b4ae5f1?w=400&q=80"),
        ("Setting Up Base Camp",         "إعداد المخيم الرئيسي",   "camping",    90,  60, "reel",   None,          0,
         "https://images.unsplash.com/photo-1478131143081-80f7f84ca84d?w=400&q=80"),
        ("Wild Plant Identification",    "تحديد النباتات البرية",   "camping",    70,  55, "reel",   None,          0,
         "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=400&q=80"),
    ]
    for title, title_ar, cat, dur, xp, vtype, cid, order_i, thumb in videos_data:
        execute(
            "INSERT INTO videos (title,title_ar,video_url,thumbnail_url,category,duration_secs,xp_reward,video_type,course_id,order_index,uploader_id) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (title, title_ar, demo_video, thumb, cat, dur, xp, vtype, cid, order_i, inst_id)
        )

    # Community group
    grp_id = execute(
        "INSERT INTO community_groups (name,description,region,owner_id) VALUES (?,?,?,?)",
        ("المغرب الكشفي – المجموعة الوطنية",
         "الفضاء الرسمي للكشافة المغربية على منصة Academic Kachafa Fakat.", "Morocco", admin_id)
    )
    for uid in user_ids.values():
        execute("INSERT INTO group_members (group_id,user_id) VALUES (?,?)", (grp_id, uid))

    # Welcome notifications
    for uid in user_ids.values():
        execute("INSERT INTO notifications (user_id,kind,title,body,icon) VALUES (?,?,?,?,?)",
                (uid, "welcome", "Welcome to Academic Kechafa! 🎉",
                 "Start your scouting journey today.", "🎉"))

    print("✅  Demo data seeded.")
