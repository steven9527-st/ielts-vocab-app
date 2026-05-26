import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'vocab.db')


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
            quiz_word_ids   TEXT,
            quiz_answers    TEXT,
            status          TEXT NOT NULL DEFAULT 'in_progress',
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    conn.close()
