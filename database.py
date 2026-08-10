import json
import re
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
    # 历史数据回补：同义词学习通关的词补标 mastered
    # （修复 add-synonym-learn-quiz 未 UPDATE words.status 的历史 bug）
    _migrate_synonym_mastered(conn)
    # 存量数据清洗：words 文本字段中的换行符折叠为空格
    # （修复浏览器 CRLF 规范化导致测验误判的 bug）
    _migrate_strip_newlines(conn)
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


def _migrate_synonym_mastered(conn) -> None:
    """把同义词学习通关的历史词补标 mastered（幂等）。

    背景：`add-synonym-learn-quiz` change 引入同义词学习流后，
    通关时故意跳过了 `UPDATE words SET status='mastered'`，
    导致这些词永远显示 unmastered，影响首页统计。
    本迁移扫 study_log 里所有 `learn_synonym+accuracy=1.0` 记录，
    把词标 mastered。

    幂等保证：`WHERE status='unmastered'` 语义确保重复执行结果一致；
    同时保护用户手动降级为 unmastered 的词……不：实际上这两个语义冲突，
    最终选择"仅升级 unmastered → mastered"，接受"手动降级会被回补"的边缘代价
    （代价可接受：用户可以再次手动降级；且此场景极少）。
    """
    try:
        rows = conn.execute(
            "SELECT word_ids FROM study_log "
            "WHERE mode='learn_synonym' AND accuracy=1.0"
        ).fetchall()
    except Exception:
        return  # 表可能还没创建（首次全新初始化场景）

    all_wids = set()
    for row in rows:
        try:
            wids = json.loads(row[0] or '[]')
            for wid in wids:
                all_wids.add(int(wid))
        except Exception:
            continue

    if not all_wids:
        return

    for wid in all_wids:
        conn.execute(
            "UPDATE words SET status='mastered' WHERE id=? AND status='unmastered'",
            (wid,)
        )
    conn.commit()


_WHITESPACE_RE = re.compile(r'\s+')


def collapse_whitespace(s: str) -> str:
    """把所有连续空白（含 \\n \\r \\t）折叠为单个空格并 strip 首尾。"""
    if not s:
        return s or ''
    return _WHITESPACE_RE.sub(' ', s).strip()


def _migrate_strip_newlines(conn) -> None:
    """清洗 words 表文本字段中的换行/制表等空白（幂等）。

    背景：Excel 单元格内换行（Alt+Enter）会把 \\n 带进 english/synonyms 字段。
    浏览器表单提交时按 HTML 标准把裸 LF 规范化为 CRLF，
    导致 quiz_submit 的字符串精确比较误判：
    用户在结果页看到"你的选择"与"正确答案"显示完全一样（\\r\\n 与 \\n 渲染相同），
    实际差一个 \\r 字符被判错。

    处理：english/chinese/phonetic/pos/synonyms 五字段统一折叠空白。
    冲突：清洗后 english 若与同 list_id 下另一行相同（UNIQUE(list_id, english)），
    删除当前行（保留无换行的干净版本）；清洗后 english 为空的行直接删除。
    """
    fields = ('english', 'chinese', 'phonetic', 'pos', 'synonyms')
    try:
        rows = conn.execute(
            "SELECT id, list_id, english, chinese, phonetic, pos, synonyms FROM words "
            "WHERE english LIKE '%' || char(10) || '%' OR english LIKE '%' || char(13) || '%' "
            "   OR chinese LIKE '%' || char(10) || '%' OR chinese LIKE '%' || char(13) || '%' "
            "   OR phonetic LIKE '%' || char(10) || '%' OR phonetic LIKE '%' || char(13) || '%' "
            "   OR pos LIKE '%' || char(10) || '%' OR pos LIKE '%' || char(13) || '%' "
            "   OR synonyms LIKE '%' || char(10) || '%' OR synonyms LIKE '%' || char(13) || '%'"
        ).fetchall()
    except Exception:
        return  # 表不存在等场景直接跳过

    for row in rows:
        cleaned = {f: collapse_whitespace(row[f]) for f in fields}
        if cleaned['chinese'] == '':
            cleaned['chinese'] = (row['chinese'] or '').strip() or cleaned['english']

        new_eng = cleaned['english']
        if not new_eng:
            # 清洗后 english 为空 → 词条无意义，删除
            conn.execute("DELETE FROM words WHERE id=?", (row['id'],))
            continue

        dup = conn.execute(
            "SELECT id FROM words WHERE list_id=? AND english=? AND id != ?",
            (row['list_id'], new_eng, row['id'])
        ).fetchone()
        if dup:
            # 与现有干净版本唯一冲突 → 删除带换行的脏版本
            conn.execute("DELETE FROM words WHERE id=?", (row['id'],))
            continue

        conn.execute(
            "UPDATE words SET english=?, chinese=?, phonetic=?, pos=?, synonyms=? WHERE id=?",
            (cleaned['english'], cleaned['chinese'], cleaned['phonetic'],
             cleaned['pos'], cleaned['synonyms'], row['id'])
        )
    conn.commit()
