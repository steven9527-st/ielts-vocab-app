import sqlite3

from paths import db_path

DB_PATH = db_path()


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS word_lists (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            source_file TEXT,
            word_count  INTEGER DEFAULT 0,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS words (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            list_id     INTEGER NOT NULL REFERENCES word_lists(id) ON DELETE CASCADE,
            english     TEXT NOT NULL,
            chinese     TEXT NOT NULL,
            phonetic    TEXT DEFAULT '',
            pos         TEXT DEFAULT '',
            synonyms    TEXT DEFAULT '',
            status      TEXT NOT NULL DEFAULT 'unmastered',
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(list_id, english)
        );

        CREATE TABLE IF NOT EXISTS study_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            list_id     INTEGER REFERENCES word_lists(id) ON DELETE SET NULL,
            date        DATE NOT NULL,
            mode        TEXT NOT NULL,
            word_ids    TEXT NOT NULL,
            accuracy    REAL,
            duration_s  INTEGER,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS learn_session (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            list_id         INTEGER REFERENCES word_lists(id) ON DELETE CASCADE,
            date            DATE NOT NULL,
            word_ids        TEXT NOT NULL,
            remaining_ids   TEXT,
            current_index   INTEGER,
            quiz_word_ids   TEXT,
            quiz_answers    TEXT,
            status          TEXT NOT NULL DEFAULT 'in_progress',
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    # 迁移：为已存在的 words 表添加 phonetic/pos/synonyms 列
    try:
        c.execute("ALTER TABLE words ADD COLUMN phonetic TEXT DEFAULT ''")
    except Exception:
        pass  # 列已存在则忽略
    try:
        c.execute("ALTER TABLE words ADD COLUMN pos TEXT DEFAULT ''")
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE words ADD COLUMN synonyms TEXT DEFAULT ''")
    except Exception:
        pass
    # learn_session 新增 current_index：支持「全集 + 游标」模型以实现翻卡前进/后退
    try:
        c.execute("ALTER TABLE learn_session ADD COLUMN current_index INTEGER")
    except Exception:
        pass  # 列已存在则忽略（幂等）
    conn.commit()
    conn.close()
