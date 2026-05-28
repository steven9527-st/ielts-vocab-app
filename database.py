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
            type        TEXT NOT NULL DEFAULT 'standard',
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
    # word_lists 新增 type：标识词库语义性质（standard / synonym），驱动测验出题方式
    try:
        c.execute("ALTER TABLE word_lists ADD COLUMN type TEXT NOT NULL DEFAULT 'standard'")
    except Exception:
        pass  # 列已存在则忽略（幂等）
    conn.commit()
    # 自动迁移既有词库：按 synonyms 字段填充率分类（仅对默认/未明确设置 type 的词库）
    _migrate_word_list_types(conn)
    conn.close()


def _migrate_word_list_types(conn) -> None:
    """将既有 word_lists 按 synonyms 填充率自动分类。

    仅对 type 为默认值 'standard'（含从 NULL 升级而来）的词库执行：
      • 词库内 synonyms 字段填充率 ≥ 80% → 标记为 'synonym'
      • 否则保持 'standard'

    已被显式标 'synonym' 的词库不被覆盖；首次启动后已迁移则后续启动无副作用。
    阈值取 0.8 是经验值：同义词词库应接近 100%，标准词库接近 0%。
    """
    SYNONYM_THRESHOLD = 0.8
    rows = conn.execute(
        "SELECT id FROM word_lists WHERE type IS NULL OR type = 'standard'"
    ).fetchall()
    for row in rows:
        list_id = row[0]
        total = conn.execute(
            "SELECT COUNT(*) FROM words WHERE list_id=?", (list_id,)
        ).fetchone()[0]
        if total == 0:
            continue
        with_syn = conn.execute(
            "SELECT COUNT(*) FROM words WHERE list_id=? AND synonyms IS NOT NULL AND synonyms != ''",
            (list_id,)
        ).fetchone()[0]
        if (with_syn / total) >= SYNONYM_THRESHOLD:
            conn.execute("UPDATE word_lists SET type='synonym' WHERE id=?", (list_id,))
    conn.commit()
