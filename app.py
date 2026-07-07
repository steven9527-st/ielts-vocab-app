import json
import os
import random
import tempfile
import threading
import time
import uuid
from datetime import date, datetime, timedelta

from flask import (Flask, jsonify, redirect, render_template, request,
                   send_file, session, url_for)

from database import get_db, init_db
from excel_parser import (apply_mapping, guess_columns, parse_table_raw)
from paths import is_frozen, resource_dir, tmp_parse_dir
from pdf_parser import parse_pdf, has_text_layer, extract_pdf_tables

# 扫描图 PDF 错误提示文案（用户预处理引导）
SCANNED_PDF_HINT = (
    '这个 PDF 看起来是扫描图，无法直接读取文字。'
    '请先用 WPS / Adobe Acrobat 等工具将其转换为可选中文字的 PDF（或直接导出为 Excel），再上传。'
)

# ── 心跳机制（仅 is_frozen() 时启用） ───────────────
# 浏览器每 10 秒发一次心跳；30 秒未收到心跳则进程自杀。
# 解决用户关浏览器后进程残留导致下次启动冲突的问题。
_HEARTBEAT_TIMEOUT_S = 30
_HEARTBEAT_CHECK_INTERVAL_S = 5
_last_heartbeat = time.time()
_heartbeat_lock = threading.Lock()


def _touch_heartbeat():
    """刷新最后活跃时间戳——任何 HTTP 请求都会触发"""
    global _last_heartbeat
    with _heartbeat_lock:
        _last_heartbeat = time.time()


def _start_heartbeat_watchdog():
    """启动后台守护线程，超过 _HEARTBEAT_TIMEOUT_S 无心跳则自杀。

    仅在打包模式（is_frozen=True）下被调用。
    使用 os._exit(0) 而非 sys.exit() 以确保从守护线程也能立即终止主进程。
    """
    def _watch():
        while True:
            time.sleep(_HEARTBEAT_CHECK_INTERVAL_S)
            with _heartbeat_lock:
                idle = time.time() - _last_heartbeat
            if idle > _HEARTBEAT_TIMEOUT_S:
                print(f'[IELTSVocab] No heartbeat for {idle:.0f}s, exiting.')
                os._exit(0)

    t = threading.Thread(target=_watch, daemon=True, name='heartbeat-watchdog')
    t.start()

# 打包环境下，Flask 需要明确指定 templates / static 资源路径（PyInstaller 解压目录）
if is_frozen():
    app = Flask(
        __name__,
        template_folder=os.path.join(resource_dir(), 'templates'),
        static_folder=os.path.join(resource_dir(), 'static'),
    )
else:
    app = Flask(__name__)
app.secret_key = os.urandom(24)


def has_cjk(s) -> bool:
    """判断字符串是否包含中日韩统一表意文字（CJK Unified Ideographs U+4E00–U+9FFF）。

    用作 Jinja test：模板内可写 `{% if value is has_cjk %}` 进行中文检测。
    对非字符串输入安全返回 False，避免模板渲染抛错。
    """
    if not isinstance(s, str):
        return False
    return any('\u4e00' <= ch <= '\u9fff' for ch in s)


app.jinja_env.tests['has_cjk'] = has_cjk

# 服务器端临时存储目录（解析结果太大不能放 cookie）
_TMP_DIR = tmp_parse_dir()


def _save_parse_result(entries: list) -> str:
    """将解析结果保存到服务器临时文件，返回 token"""
    token = str(uuid.uuid4())
    path = os.path.join(_TMP_DIR, f'{token}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(entries, f, ensure_ascii=False)
    return token


def _load_parse_result(token: str) -> list:
    """根据 token 读取解析结果"""
    if not token:
        return []
    path = os.path.join(_TMP_DIR, f'{token}.json')
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _delete_parse_result(token: str):
    """清理临时文件"""
    if not token:
        return
    path = os.path.join(_TMP_DIR, f'{token}.json')
    if os.path.exists(path):
        os.unlink(path)


# ── Quiz 数据服务端存储（避免 session cookie 超限） ───────────────

def _save_quiz_data(data: dict) -> str:
    """将测验数据保存到服务器临时文件，返回 token"""
    token = str(uuid.uuid4())
    path = os.path.join(_TMP_DIR, f'quiz_{token}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    return token


def _load_quiz_data(token: str) -> dict:
    """根据 token 读取测验数据"""
    if not token:
        return {}
    path = os.path.join(_TMP_DIR, f'quiz_{token}.json')
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _delete_quiz_data(token: str):
    """清理 quiz 临时文件"""
    if not token:
        return
    path = os.path.join(_TMP_DIR, f'quiz_{token}.json')
    if os.path.exists(path):
        os.unlink(path)


# ── Excel/CSV 原始数据服务端存储 ───────────────────────────

def _save_excel_raw(data: dict) -> str:
    """将 Excel/CSV 解析的原始 rows 保存到服务端临时文件，返回 token"""
    token = str(uuid.uuid4())
    path = os.path.join(_TMP_DIR, f'excel_{token}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    return token


def _load_excel_raw(token: str) -> dict:
    if not token:
        return {}
    path = os.path.join(_TMP_DIR, f'excel_{token}.json')
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _delete_excel_raw(token: str):
    if not token:
        return
    path = os.path.join(_TMP_DIR, f'excel_{token}.json')
    if os.path.exists(path):
        os.unlink(path)


# ─────────────────────────────────────────
# 初始化
# ─────────────────────────────────────────

@app.before_request
def setup():
    init_db()
    # 任何请求都隐式刷新心跳（用户主动操作即"活着"）
    _touch_heartbeat()


# ─────────────────────────────────────────
# 心跳路由（仅打包模式下浏览器会主动发）
# ─────────────────────────────────────────

@app.route('/api/heartbeat', methods=['POST'])
def api_heartbeat():
    """浏览器持续心跳的目标。
    实际刷新动作在 before_request 已完成；本路由仅作为浏览器
    setInterval 的目标 endpoint。
    """
    return jsonify({'ok': True})


# ─────────────────────────────────────────
# 全局模板上下文（供顶部 nav 词库切换组件使用）
# ─────────────────────────────────────────

@app.context_processor
def inject_nav_data():
    """为 base.html 顶部 nav 注入词库列表与进行中状态"""
    try:
        db = get_db()
        all_lists = [dict(r) for r in db.execute(
            'SELECT id, name FROM word_lists ORDER BY created_at ASC'
        ).fetchall()]
        db.close()
    except Exception:
        all_lists = []

    current_id = session.get('list_id')
    in_progress_endpoints = {'learn_card', 'learn_quiz', 'quiz_question'}
    in_progress = request.endpoint in in_progress_endpoints
    return {
        'nav_all_lists': all_lists,
        'nav_current_list_id': current_id,
        'nav_in_progress': in_progress,
        'is_frozen': is_frozen(),
    }


# ─────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────

def get_current_list_id():
    """从 session 获取当前词库 ID，若无则取第一个"""
    db = get_db()
    if 'list_id' in session:
        row = db.execute('SELECT id FROM word_lists WHERE id=?', (session['list_id'],)).fetchone()
        if row:
            db.close()
            return session['list_id']
    row = db.execute('SELECT id FROM word_lists ORDER BY created_at ASC LIMIT 1').fetchone()
    db.close()
    if row:
        session['list_id'] = row['id']
        return row['id']
    return None


def get_list_stats(list_id):
    db = get_db()
    total = db.execute('SELECT COUNT(*) FROM words WHERE list_id=?', (list_id,)).fetchone()[0]
    # mastered 口径：仅 status='mastered'（不含 fully_mastered），与 fully_mastered 分开计数
    mastered = db.execute(
        "SELECT COUNT(*) FROM words WHERE list_id=? AND status='mastered'", (list_id,)
    ).fetchone()[0]
    fully_mastered = db.execute(
        "SELECT COUNT(*) FROM words WHERE list_id=? AND status='fully_mastered'", (list_id,)
    ).fetchone()[0]
    unmastered = db.execute(
        "SELECT COUNT(*) FROM words WHERE list_id=? AND status='unmastered'", (list_id,)
    ).fetchone()[0]
    with_syn = db.execute(
        "SELECT COUNT(*) FROM words WHERE list_id=? AND synonyms IS NOT NULL AND synonyms!=''",
        (list_id,)
    ).fetchone()[0]
    unmastered_with_syn = db.execute(
        "SELECT COUNT(*) FROM words WHERE list_id=? AND status='unmastered' "
        "AND synonyms IS NOT NULL AND synonyms!=''",
        (list_id,)
    ).fetchone()[0]
    db.close()
    return {
        'total': total,
        'mastered': mastered,
        'fully_mastered': fully_mastered,
        'unmastered': unmastered,
        'with_synonyms': with_syn,
        'unmastered_with_synonyms': unmastered_with_syn,
    }


def calc_streak():
    """计算全局连续打卡天数（任意词库 / 任意学习模式 100% 通关）

    包含的 mode：
      • 'learn'          普通翻卡学习通关
      • 'learn_synonym'  同义词学习完成（unify-learn-entry-by-list-type 新增）
    """
    db = get_db()
    rows = db.execute(
        "SELECT DISTINCT date FROM study_log WHERE mode IN ('learn', 'learn_synonym') AND accuracy=1.0 ORDER BY date DESC"
    ).fetchall()
    db.close()

    if not rows:
        return 0

    dates = [datetime.strptime(r['date'], '%Y-%m-%d').date() for r in rows]
    today = date.today()
    streak = 0
    current = today

    for d in dates:
        if d == current or d == current - timedelta(days=1):
            streak += 1
            current = d
        elif d < current - timedelta(days=1):
            break

    return streak


def get_active_session(list_id):
    """获取当前词库今日或昨日的进行中 learn_session"""
    db = get_db()
    row = db.execute(
        "SELECT * FROM learn_session WHERE list_id=? AND status='in_progress' ORDER BY created_at DESC LIMIT 1",
        (list_id,)
    ).fetchone()
    db.close()
    return dict(row) if row else None


def today_completed(list_id):
    """今日是否已通关（普通学习或同义词学习任一完成即视为通关）"""
    db = get_db()
    row = db.execute(
        "SELECT id FROM study_log WHERE list_id=? AND mode IN ('learn', 'learn_synonym') AND accuracy=1.0 AND date=?",
        (list_id, str(date.today()))
    ).fetchone()
    db.close()
    return row is not None


def _fetch_review_items(word_ids, list_id, list_type='standard'):
    """按 word_ids 顺序，从 DB 拉取词的展示信息，供结果页展示"完全掌握"勾选列表。

    返回：[{word_id, english, meaning}, ...]
    meaning：standard → chinese；synonym → synonyms（若 synonyms 空则 fallback chinese）
    """
    if not word_ids:
        return []
    db = get_db()
    placeholders = ','.join('?' * len(word_ids))
    rows = db.execute(
        f'SELECT id, english, chinese, synonyms FROM words WHERE id IN ({placeholders})',
        list(word_ids)
    ).fetchall()
    db.close()

    lookup = {r['id']: r for r in rows}
    items = []
    for wid in word_ids:
        r = lookup.get(wid)
        if not r:
            continue
        if list_type == 'synonym':
            meaning = (r['synonyms'] or '').strip() or (r['chinese'] or '').strip()
        else:
            meaning = (r['chinese'] or '').strip()
        items.append({
            'word_id': r['id'],
            'english': r['english'] or '',
            'meaning': meaning,
        })
    return items


def today_mastered_count(list_id):
    """统计当前词库今日新增掌握的单词数（多会话合并去重）。

    数据源：study_log 中当天 mode IN ('learn','learn_synonym') 且 accuracy=1.0 的记录，
    合并 word_ids 后去重取长度。
    """
    if not list_id:
        return 0
    db = get_db()
    rows = db.execute(
        "SELECT word_ids FROM study_log "
        "WHERE list_id=? AND date=? AND accuracy=1.0 AND mode IN ('learn','learn_synonym')",
        (list_id, str(date.today()))
    ).fetchall()
    db.close()

    unique = set()
    for r in rows:
        try:
            ids = json.loads(r['word_ids'] or '[]')
            for wid in ids:
                unique.add(wid)
        except Exception:
            continue
    return len(unique)


def _get_list_type(list_id) -> str:
    """读取词库 type（'standard' / 'synonym'）；找不到则返回 'standard' 兜底。"""
    if not list_id:
        return 'standard'
    db = get_db()
    row = db.execute('SELECT type FROM word_lists WHERE id=?', (list_id,)).fetchone()
    db.close()
    if not row:
        return 'standard'
    val = row['type'] if 'type' in row.keys() else None
    return val if val in ('standard', 'synonym') else 'standard'


def generate_quiz_questions(word_ids, list_id, list_type='standard'):
    """为 word_ids 列表生成 4 选 1 题目，返回题目列表

    list_type:
      'standard' — 选项均为中文释义（既有逻辑）
      'synonym'  — 选项均为英文同义词（同义词词库专用）
                   要求同词库内有同义词的词数 ≥ 4，否则自动降级到 standard
    """
    db = get_db()
    questions = []
    # 同义词模式需读 synonyms 字段
    if list_type == 'synonym':
        all_words = db.execute(
            'SELECT id, english, chinese, synonyms FROM words WHERE list_id=?',
            (list_id,)
        ).fetchall()
    else:
        all_words = db.execute(
            'SELECT id, english, chinese FROM words WHERE list_id=?',
            (list_id,)
        ).fetchall()
    all_words = [dict(w) for w in all_words]
    db.close()

    if len(all_words) < 4:
        return None  # 词库不足

    # 同义词模式需要 ≥ 4 个有 synonyms 的词；否则降级到 standard
    if list_type == 'synonym':
        words_with_syn = [w for w in all_words if (w.get('synonyms') or '').strip()]
        if len(words_with_syn) < 4:
            print(f'[quiz] list {list_id} type=synonym 但有同义词的词不足 4 个 ({len(words_with_syn)})，降级到 standard')
            list_type = 'standard'

    for wid in word_ids:
        correct = next((w for w in all_words if w['id'] == wid), None)
        if not correct:
            continue

        if list_type == 'synonym':
            # 英文同义词选项：正确答案 = 当前词 synonyms；干扰项 = 其他词的 synonyms
            correct_syn = (correct.get('synonyms') or '').strip()
            if not correct_syn:
                # 当前词没有同义词，跳过此题（学习路径会保证全有 synonyms，但 test 模式可能从全词库随机选到无 syn 的词）
                continue
            distractor_pool = [
                (w.get('synonyms') or '').strip()
                for w in all_words
                if w['id'] != wid and (w.get('synonyms') or '').strip() and (w.get('synonyms') or '').strip() != correct_syn
            ]
            # 去重（避免不同词有相同 synonyms 时干扰项重复）
            distractor_pool = list(dict.fromkeys(distractor_pool))
            if len(distractor_pool) < 3:
                # 干扰项不足，本题降级为中文选项
                others = [w for w in all_words if w['id'] != wid]
                distractors = random.sample(others, min(3, len(others)))
                options = [correct['chinese']] + [d['chinese'] for d in distractors]
                random.shuffle(options)
                questions.append({
                    'word_id': wid,
                    'english': correct['english'],
                    'correct': correct['chinese'],
                    'options': options,
                })
                continue
            distractors = random.sample(distractor_pool, 3)
            options = [correct_syn] + distractors
            random.shuffle(options)
            questions.append({
                'word_id': wid,
                'english': correct['english'],
                'correct': correct_syn,
                'options': options,
            })
            continue

        # 标准模式：原中文选项逻辑
        others = [w for w in all_words if w['id'] != wid]
        distractors = random.sample(others, min(3, len(others)))
        options = [correct['chinese']] + [d['chinese'] for d in distractors]
        random.shuffle(options)
        questions.append({
            'word_id': wid,
            'english': correct['english'],
            'correct': correct['chinese'],
            'options': options
        })

    return questions


# ─────────────────────────────────────────
# 首页 Dashboard
# ─────────────────────────────────────────

@app.route('/')
def index():
    db = get_db()
    all_lists = [dict(r) for r in db.execute('SELECT * FROM word_lists ORDER BY created_at ASC').fetchall()]
    db.close()

    if not all_lists:
        return render_template('index.html', no_lists=True)

    list_id = get_current_list_id()
    current_list = next((l for l in all_lists if l['id'] == list_id), all_lists[0])
    stats = get_list_stats(list_id)
    streak = calc_streak()
    active_session = get_active_session(list_id)
    # 同义词学习的进度存在 Flask session 的 syn_queue 中（非 DB），单独检测
    active_syn_session = bool(session.get('syn_queue'))
    completed_today = today_completed(list_id)
    today_mastered = today_mastered_count(list_id) if completed_today else 0

    return render_template('index.html',
                           no_lists=False,
                           all_lists=all_lists,
                           current_list=current_list,
                           stats=stats,
                           streak=streak,
                           active_session=active_session,
                           active_syn_session=active_syn_session,
                           completed_today=completed_today,
                           today_mastered=today_mastered)


@app.route('/switch_list', methods=['POST'])
def switch_list():
    list_id = request.form.get('list_id', type=int)
    if list_id:
        session['list_id'] = list_id
        session['list_picked'] = True
    return redirect(url_for('index'))


@app.route('/api/switch_list_safe', methods=['POST'])
def api_switch_list_safe():
    """全站顶部 nav 使用的安全切换接口。
    若当前有进行中的 learn_session 或 quiz_token，需前端传 abandon=true 才会清理并切换。
    """
    data = request.get_json(silent=True) or {}
    target_list_id = data.get('list_id')
    abandon = bool(data.get('abandon', False))

    if not target_list_id:
        return jsonify({'error': '缺少 list_id'}), 400

    # 校验词库存在
    db = get_db()
    row = db.execute('SELECT id FROM word_lists WHERE id=?', (target_list_id,)).fetchone()
    db.close()
    if not row:
        return jsonify({'error': '词库不存在'}), 404

    # 检测当前是否有进行中的状态
    list_id = get_current_list_id()
    has_active_learn = False
    if list_id:
        active = get_active_session(list_id)
        has_active_learn = active is not None
    has_active_quiz = bool(session.get('quiz_token'))
    has_progress = has_active_learn or has_active_quiz

    if has_progress and not abandon:
        return jsonify({'error': '存在进行中的学习或测试', 'has_progress': True}), 409

    # 需要 abandon：清理 learn_session 与 quiz
    if has_progress:
        if has_active_learn:
            sess_id = session.get('learn_session_id')
            if sess_id:
                db = get_db()
                db.execute("UPDATE learn_session SET status='abandoned' WHERE id=?", (sess_id,))
                db.commit()
                db.close()
            session.pop('learn_session_id', None)
            session.pop('learn_total', None)
            session.pop('learn_max_reached', None)
        if has_active_quiz:
            _delete_quiz_data(session.pop('quiz_token', None))
            session.pop('quiz_index', None)
            session.pop('quiz_answers', None)
            session.pop('quiz_mode', None)
            session.pop('quiz_test_type', None)
            session.pop('quiz_max_reached', None)
            session.pop('test_count', None)

    session['list_id'] = int(target_list_id)
    session['list_picked'] = True
    return jsonify({'ok': True, 'list_id': int(target_list_id)})


@app.route('/api/pick_list', methods=['POST'])
def api_pick_list():
    """词库选择浮层提交接口：仅设置 list_id 与 list_picked 标记"""
    data = request.get_json(silent=True) or {}
    list_id = data.get('list_id')
    if not list_id:
        return jsonify({'error': '缺少 list_id'}), 400

    db = get_db()
    row = db.execute('SELECT id FROM word_lists WHERE id=?', (list_id,)).fetchone()
    db.close()
    if not row:
        return jsonify({'error': '词库不存在'}), 404

    session['list_id'] = int(list_id)
    session['list_picked'] = True
    return jsonify({'ok': True})


# ─────────────────────────────────────────
# PDF 导入
# ─────────────────────────────────────────

@app.route('/import')
def import_page():
    return render_template('import.html')


@app.route('/import/parse', methods=['POST'])
def import_parse():
    if 'pdf' not in request.files:
        return jsonify({'error': '未上传文件'}), 400
    f = request.files['pdf']
    filename = f.filename or ''
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ('.pdf', '.xlsx', '.csv'):
        return jsonify({'error': '仅支持 .pdf / .xlsx / .csv 文件'}), 400

    # 保存到临时文件
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        f.save(tmp.name)
        tmp_path = tmp.name

    try:
        if ext == '.pdf':
            # ── 文字层探测：扫描图 PDF 直接拒绝 ──
            if not has_text_layer(tmp_path):
                return jsonify({'error': SCANNED_PDF_HINT}), 400

            # ── 双路径分发（修复版顺序）：先编号词表 _ENTRY_RE，后表格抽取 ──
            # 原因：_ENTRY_RE 输出结构化字段（english/phonetic/pos/chinese）
            # 质量天然优于表格抽取（仅按列粗糙切分）；带表格线的编号词表 PDF
            # 不应被表格路径"截胡"。
            try:
                entries = parse_pdf(tmp_path)
            except Exception as e:
                return jsonify({'error': f'PDF 解析失败：{e}'}), 400

            total = len(entries)
            hit = sum(1 for e in entries if not e.get('failed'))
            hit_rate = (hit / total) if total > 0 else 0.0

            # 命中率 ≥ 30% 且数量 ≥ 5 → 采用编号词表路径
            if total >= 5 and hit_rate >= 0.3:
                # 词库间隔离：新建词库导入，无需检查其他词库的重复词
                # 只在 entries 内部自查重（同一文件内的重复词标为 duplicate）
                seen_in_file = set()
                for entry in entries:
                    if entry['failed']:
                        entry['duplicate'] = False
                        continue
                    key = entry['english'].lower()
                    if key in seen_in_file:
                        entry['duplicate'] = True
                    else:
                        seen_in_file.add(key)
                        entry['duplicate'] = False

                token = _save_parse_result(entries)
                session['import_token'] = token
                session['import_filename'] = filename
                return jsonify({
                    'entries': entries,
                    'count': len(entries),
                    'next': '/import/preview',
                })

            # ── 命中率不足 → 尝试表格抽取 fallback ──
            table_rows = None
            try:
                table_rows = extract_pdf_tables(tmp_path)
            except Exception:
                # 表格抽取异常视为"未抽到表格"，静默降级
                table_rows = None

            if table_rows:
                # 表格 PDF：写入 excel raw token，跳列映射页（与 .xlsx 完全一致）
                token = _save_excel_raw({
                    'rows': table_rows,
                    'filename': filename,
                })
                session['excel_raw_token'] = token
                session['import_filename'] = filename
                return jsonify({
                    'count': len(table_rows),
                    'next': '/import/excel_mapping',
                })

            # ── 两条路径都未能高质量解析 → 返回 parse_pdf 的原始结果 ──
            # 让用户在预览页看到现状（可能很空），可手动决定
            seen_in_file = set()
            for entry in entries:
                if entry['failed']:
                    entry['duplicate'] = False
                    continue
                key = entry['english'].lower()
                if key in seen_in_file:
                    entry['duplicate'] = True
                else:
                    seen_in_file.add(key)
                    entry['duplicate'] = False

            token = _save_parse_result(entries)
            session['import_token'] = token
            session['import_filename'] = filename
            return jsonify({
                'entries': entries,
                'count': len(entries),
                'next': '/import/preview',
            })

        else:
            # ── Excel/CSV 流程：先读全部 rows，跳到列映射页 ──
            try:
                rows = parse_table_raw(tmp_path)
            except RuntimeError as e:
                return jsonify({'error': str(e)}), 400
            except Exception as e:
                return jsonify({'error': f'文件解析失败：{e}'}), 400

            token = _save_excel_raw({
                'rows': rows,
                'filename': filename,
            })
            session['excel_raw_token'] = token
            session['import_filename'] = filename
            return jsonify({
                'count': len(rows),
                'next': '/import/excel_mapping',
            })
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@app.route('/import/excel_mapping')
def import_excel_mapping():
    token = session.get('excel_raw_token', '')
    raw = _load_excel_raw(token)
    rows = raw.get('rows', [])
    filename = raw.get('filename', 'unknown')

    if not rows:
        return redirect(url_for('import_page'))

    guess = guess_columns(rows)
    preview_rows = rows[:6]  # 前 6 行用于预览（含可能的表头）
    n_cols = len(rows[0]) if rows else 0
    # 列标签 A/B/C/D... + 表头单元格（若有）
    first_row = rows[0] if rows else []
    col_letters = [chr(ord('A') + i) for i in range(n_cols)]
    col_labels = []
    for i, letter in enumerate(col_letters):
        header_text = first_row[i] if i < len(first_row) else ''
        if header_text and len(header_text) <= 20:
            col_labels.append(f'{letter}: {header_text}')
        else:
            col_labels.append(letter)

    return render_template('import_excel_mapping.html',
                           filename=filename,
                           total_rows=len(rows),
                           preview_rows=preview_rows,
                           n_cols=n_cols,
                           col_labels=col_labels,
                           guess=guess)


@app.route('/import/excel_apply', methods=['POST'])
def import_excel_apply():
    data = request.get_json(silent=True) or {}
    english_col = data.get('english_col', -1)
    chinese_col = data.get('chinese_col', -1)
    phonetic_col = data.get('phonetic_col', -1)
    pos_col = data.get('pos_col', -1)
    synonym_col = data.get('synonym_col', -1)
    english_col_2 = data.get('english_col_2', -1)
    skip_first_row = bool(data.get('skip_first_row', True))
    import_mode = data.get('import_mode', 'standard')
    if import_mode not in ('standard', 'synonym'):
        import_mode = 'standard'

    try:
        english_col = int(english_col)
        chinese_col = int(chinese_col)
        phonetic_col = int(phonetic_col)
        pos_col = int(pos_col)
        synonym_col = int(synonym_col)
        english_col_2 = int(english_col_2)
    except (TypeError, ValueError):
        return jsonify({'error': '列参数格式错误'}), 400

    if english_col < 0 or chinese_col < 0:
        return jsonify({'error': '请指定英文列和中文列'}), 400
    if english_col == chinese_col:
        return jsonify({'error': '英文列和中文列不能相同'}), 400
    # 双英文列校验：仅在指定 english_col_2 时（>=0）需校验冲突，
    # 且仅在同义词模式下生效——标准模式即便误传也忽略
    if import_mode == 'synonym' and english_col_2 >= 0:
        if english_col_2 == english_col or english_col_2 == chinese_col:
            return jsonify({'error': '英文列 2 不能与英文列 / 中文列相同'}), 400

    token = session.get('excel_raw_token', '')
    raw = _load_excel_raw(token)
    rows = raw.get('rows', [])
    if not rows:
        return jsonify({'error': '会话已过期，请重新上传'}), 400

    try:
        entries = apply_mapping(
            rows,
            english_col=english_col,
            chinese_col=chinese_col,
            phonetic_col=phonetic_col,
            pos_col=pos_col,
            synonym_col=synonym_col,
            english_col_2=english_col_2,
            skip_first_row=skip_first_row,
            import_mode=import_mode,
        )
    except Exception as e:
        return jsonify({'error': f'数据转换失败：{e}'}), 400

    if not entries:
        return jsonify({'error': '映射后无有效数据'}), 400

    # 词库间隔离：新建词库导入，无需检查其他词库的重复词
    # 只在 entries 内部自查重（同一文件内的重复词标为 duplicate）
    seen_in_file = set()
    for entry in entries:
        if entry['failed']:
            entry['duplicate'] = False
            continue
        key = entry['english'].lower()
        if key in seen_in_file:
            entry['duplicate'] = True
        else:
            seen_in_file.add(key)
            entry['duplicate'] = False

    preview_token = _save_parse_result(entries)
    session['import_token'] = preview_token
    # 持久化 import_mode 到 session，供 import_confirm 写词库 type 使用
    session['import_mode'] = import_mode
    # 清理 excel raw token
    _delete_excel_raw(session.pop('excel_raw_token', None))

    return jsonify({
        'ok': True,
        'count': len(entries),
        'next': '/import/preview',
    })


@app.route('/import/preview')
def import_preview():
    token = session.get('import_token', '')
    entries = _load_parse_result(token)
    filename = session.get('import_filename', 'unknown.pdf')
    return render_template('import_preview.html', entries=entries, filename=filename)


@app.route('/import/confirm', methods=['POST'])
def import_confirm():
    data = request.get_json()
    entries = data.get('entries', [])
    list_name = data.get('list_name', '').strip() or session.get('import_filename', '词库')

    if not entries:
        return jsonify({'error': '没有可导入的词条'}), 400

    db = get_db()
    # 读取导入模式（来自 excel_apply 路径），写入词库 type 字段以驱动测验出题逻辑
    import_mode = session.get('import_mode', 'standard')
    list_type = 'synonym' if import_mode == 'synonym' else 'standard'
    # 创建词库记录
    c = db.execute(
        'INSERT INTO word_lists (name, source_file, word_count, type) VALUES (?, ?, 0, ?)',
        (list_name, session.get('import_filename', ''), list_type)
    )
    new_list_id = c.lastrowid

    count = 0
    for entry in entries:
        english = entry.get('english', '').strip()
        chinese = entry.get('chinese', '').strip()
        if not english or not chinese:
            continue
        try:
            db.execute(
                'INSERT OR IGNORE INTO words (list_id, english, chinese, phonetic, pos, synonyms) VALUES (?, ?, ?, ?, ?, ?)',
                (new_list_id, english, chinese,
                 entry.get('phonetic', '').strip(),
                 entry.get('pos', '').strip(),
                 entry.get('synonyms', '').strip())
            )
            count += 1
        except Exception:
            pass

    db.execute('UPDATE word_lists SET word_count=? WHERE id=?', (count, new_list_id))
    db.commit()
    db.close()

    session['list_id'] = new_list_id
    session['list_picked'] = True
    _delete_parse_result(session.pop('import_token', None))
    session.pop('import_filename', None)
    session.pop('import_mode', None)

    return jsonify({'success': True, 'count': count, 'list_id': new_list_id})


# ─────────────────────────────────────────
# 学习模式
# ─────────────────────────────────────────

@app.route('/learn/setup')
def learn_setup():
    list_id = get_current_list_id()
    if not list_id:
        return redirect(url_for('index'))
    stats = get_list_stats(list_id)

    db = get_db()
    list_count = db.execute('SELECT COUNT(*) FROM word_lists').fetchone()[0]
    db.close()
    show_picker = (list_count >= 2) and (not session.get('list_picked'))

    return render_template('learn_setup.html', stats=stats, default_n=20,
                           show_picker=show_picker)


@app.route('/learn/start', methods=['POST'])
def learn_start():
    list_id = get_current_list_id()
    n = request.form.get('n', 20, type=int)

    db = get_db()
    unmastered = db.execute(
        "SELECT id FROM words WHERE list_id=? AND status='unmastered' ORDER BY RANDOM() LIMIT ?",
        (list_id, n)
    ).fetchall()
    db.close()

    word_ids = [r['id'] for r in unmastered]
    if not word_ids:
        return redirect(url_for('index'))

    db = get_db()
    # 放弃之前进行中的 session
    db.execute(
        "UPDATE learn_session SET status='abandoned' WHERE list_id=? AND status='in_progress'",
        (list_id,)
    )
    c = db.execute(
        "INSERT INTO learn_session (list_id, date, word_ids, remaining_ids, current_index, status) VALUES (?, ?, ?, ?, 0, 'in_progress')",
        (list_id, str(date.today()), json.dumps(word_ids), json.dumps(word_ids))
    )
    session['learn_session_id'] = c.lastrowid
    session['learn_total'] = len(word_ids)
    session['learn_max_reached'] = 1  # 进度峰值：从第 1 张开始
    db.commit()
    db.close()

    return redirect(url_for('learn_card'))


@app.route('/learn/continue')
def learn_continue():
    list_id = get_current_list_id()
    active = get_active_session(list_id)
    if active:
        session['learn_session_id'] = active['id']
        word_ids_all = json.loads(active['word_ids'])
        session['learn_total'] = len(word_ids_all)
        # Lazy 迁移：旧 session 无 current_index，按 remaining_ids 推算
        ci = active.get('current_index')
        if ci is None:
            remaining = json.loads(active.get('remaining_ids') or '[]')
            ci = max(0, len(word_ids_all) - len(remaining))
            db = get_db()
            db.execute('UPDATE learn_session SET current_index=? WHERE id=?', (ci, active['id']))
            db.commit()
            db.close()
        # 进度峰值：续传时按当前位置初始化（无法恢复历史峰值）
        session['learn_max_reached'] = max(session.get('learn_max_reached', 0), ci + 1)
    return redirect(url_for('learn_card'))


@app.route('/learn/card')
def learn_card():
    sess_id = session.get('learn_session_id')
    if not sess_id:
        return redirect(url_for('index'))

    db = get_db()
    ls = db.execute('SELECT * FROM learn_session WHERE id=?', (sess_id,)).fetchone()
    if not ls or ls['status'] != 'in_progress':
        db.close()
        return redirect(url_for('index'))

    word_ids_all = json.loads(ls['word_ids'])
    total = len(word_ids_all)
    if total == 0:
        db.close()
        return redirect(url_for('learn_quiz'))

    # 读取游标，lazy 迁移旧 session（无 current_index）
    ci = ls['current_index']
    if ci is None:
        remaining = json.loads(ls['remaining_ids'] or '[]')
        ci = max(0, total - len(remaining))
        db.execute('UPDATE learn_session SET current_index=? WHERE id=?', (ci, sess_id))
        db.commit()

    # 越界保护：clamp 到合法范围；若超过末尾则直接进入测验
    if ci >= total:
        db.close()
        return redirect(url_for('learn_quiz'))
    ci = max(0, ci)

    current_id = word_ids_all[ci]
    word = db.execute('SELECT * FROM words WHERE id=?', (current_id,)).fetchone()
    db.close()

    current_pos = ci + 1  # 1-based
    # 更新进度峰值
    max_reached = max(session.get('learn_max_reached', 0), current_pos)
    session['learn_max_reached'] = max_reached

    return render_template('flashcard.html',
                           word=dict(word),
                           current=current_pos,
                           total=total,
                           display_progress=max_reached,
                           prev_available=(ci > 0))


@app.route('/learn/next', methods=['POST'])
def learn_next():
    sess_id = session.get('learn_session_id')
    if not sess_id:
        return redirect(url_for('index'))

    db = get_db()
    ls = db.execute('SELECT * FROM learn_session WHERE id=?', (sess_id,)).fetchone()
    if not ls:
        db.close()
        return redirect(url_for('index'))

    word_ids_all = json.loads(ls['word_ids'])
    total = len(word_ids_all)
    ci = ls['current_index']
    if ci is None:
        # Lazy 迁移
        remaining = json.loads(ls['remaining_ids'] or '[]')
        ci = max(0, total - len(remaining))

    ci_next = ci + 1
    if ci_next >= total:
        # 学完，进入测验；游标保持在末位
        db.execute('UPDATE learn_session SET current_index=? WHERE id=?', (total - 1, sess_id))
        db.commit()
        db.close()
        return redirect(url_for('learn_quiz'))

    db.execute('UPDATE learn_session SET current_index=? WHERE id=?', (ci_next, sess_id))
    db.commit()
    db.close()
    return redirect(url_for('learn_card'))


@app.route('/learn/prev', methods=['POST'])
def learn_prev():
    sess_id = session.get('learn_session_id')
    if not sess_id:
        return redirect(url_for('index'))

    db = get_db()
    ls = db.execute('SELECT * FROM learn_session WHERE id=?', (sess_id,)).fetchone()
    if not ls:
        db.close()
        return redirect(url_for('index'))

    word_ids_all = json.loads(ls['word_ids'])
    total = len(word_ids_all)
    ci = ls['current_index']
    if ci is None:
        remaining = json.loads(ls['remaining_ids'] or '[]')
        ci = max(0, total - len(remaining))

    ci_prev = max(0, ci - 1)
    db.execute('UPDATE learn_session SET current_index=? WHERE id=?', (ci_prev, sess_id))
    db.commit()
    db.close()
    return redirect(url_for('learn_card'))


@app.route('/learn/abandon', methods=['POST'])
def learn_abandon():
    sess_id = session.get('learn_session_id')
    if sess_id:
        db = get_db()
        db.execute("UPDATE learn_session SET status='abandoned' WHERE id=?", (sess_id,))
        db.commit()
        db.close()
    session.pop('learn_session_id', None)
    session.pop('learn_total', None)
    session.pop('learn_max_reached', None)
    return redirect(url_for('index'))


# ─────────────────────────────────────────
# 学习测验
# ─────────────────────────────────────────

@app.route('/learn/quiz')
def learn_quiz():
    # 优先消费同义词学习流传入的测验范围
    pending_ids = session.get('pending_quiz_word_ids')
    pending_return = session.get('pending_quiz_return_to')
    is_synonym_flow = bool(pending_ids) and pending_return == 'synonym_done'

    list_id = get_current_list_id()
    if not list_id:
        # 清理可能的临时数据
        session.pop('pending_quiz_word_ids', None)
        session.pop('pending_quiz_return_to', None)
        return redirect(url_for('index'))

    db = get_db()

    if is_synonym_flow:
        # 同义词学习流入口：不依赖 learn_session
        word_ids = list(pending_ids)
    else:
        # 普通学习流入口：必须有 learn_session
        sess_id = session.get('learn_session_id')
        if not sess_id:
            db.close()
            return redirect(url_for('index'))

        ls = db.execute('SELECT * FROM learn_session WHERE id=?', (sess_id,)).fetchone()
        if not ls or ls['status'] != 'in_progress':
            db.close()
            return redirect(url_for('index'))

        # 取本轮需要测验的词（quiz_word_ids 存错题，否则用 word_ids）
        quiz_ids_raw = ls['quiz_word_ids']
        word_ids = json.loads(quiz_ids_raw) if quiz_ids_raw else json.loads(ls['word_ids'])

    # 检查词库是否够生成干扰项
    total_words = db.execute('SELECT COUNT(*) FROM words WHERE list_id=?', (list_id,)).fetchone()[0]
    db.close()
    if total_words < 4:
        # 同义词流：词库太小，直接进完成页
        if is_synonym_flow:
            session.pop('pending_quiz_word_ids', None)
            session.pop('pending_quiz_return_to', None)
            return redirect(url_for('synonym_done'))
        return render_template('quiz_error.html', message='词库单词数不足（至少需要 4 个词）')

    # 学习测验：按词库 type 决定出题方式（synonym 词库 → 英文同义词选项）
    list_type = _get_list_type(list_id)
    questions = generate_quiz_questions(word_ids, list_id, list_type=list_type)
    if questions is None:
        if is_synonym_flow:
            session.pop('pending_quiz_word_ids', None)
            session.pop('pending_quiz_return_to', None)
            return redirect(url_for('synonym_done'))
        return render_template('quiz_error.html', message='词库单词数不足（至少需要 4 个词）')

    random.shuffle(questions)
    # 存到服务端文件，避免 cookie 超限
    token = _save_quiz_data({'questions': questions, 'word_ids': word_ids})
    session['quiz_token'] = token
    session['quiz_index'] = 0
    session['quiz_answers'] = {}
    session['quiz_mode'] = 'learn'
    session['quiz_max_reached'] = 1  # 进度峰值：从第 1 题开始
    # 保存本次学习会话的原始 word_ids 全集，quiz_retry 不覆盖。
    # 通关时用它计算 total、UPDATE mastered、写 study_log，避免"重做只剩错题子集"的 bug
    session['quiz_original_word_ids'] = list(word_ids)

    # 消费一次性来源标记（保留 pending_quiz_return_to 让 submit 识别）
    session.pop('pending_quiz_word_ids', None)
    if is_synonym_flow:
        session['quiz_synonym_flow'] = True
    else:
        session.pop('quiz_synonym_flow', None)

    return redirect(url_for('quiz_question'))


@app.route('/quiz/question')
def quiz_question():
    quiz_data = _load_quiz_data(session.get('quiz_token', ''))
    questions = quiz_data.get('questions', [])
    idx = session.get('quiz_index', 0)

    if not questions:
        return redirect(url_for('index'))

    if idx >= len(questions):
        return redirect(url_for('quiz_submit'))

    q = questions[idx]
    mode = session.get('quiz_mode', 'learn')
    # 学习模式始终为文字；测试模式取 question_type
    if mode == 'learn':
        question_type = 'text'
    else:
        question_type = quiz_data.get('question_type', 'text')

    current_pos = idx + 1
    # 更新进度峰值
    max_reached = max(session.get('quiz_max_reached', 0), current_pos)
    session['quiz_max_reached'] = max_reached

    # 回退后预选回原答案；并通过查询参数 from_prev 通知前端"不要自动播放音频"
    answers = session.get('quiz_answers', {})
    preselected = answers.get(str(idx), '')
    from_prev = request.args.get('from_prev') == '1'

    return render_template('quiz.html',
                           question=q,
                           current=current_pos,
                           total=len(questions),
                           mode=mode,
                           question_type=question_type,
                           display_progress=max_reached,
                           prev_available=(idx > 0),
                           preselected=preselected,
                           from_prev=from_prev)


@app.route('/quiz/answer', methods=['POST'])
def quiz_answer():
    idx = session.get('quiz_index', 0)
    quiz_data = _load_quiz_data(session.get('quiz_token', ''))
    total = len(quiz_data.get('questions', []))
    selected = request.form.get('answer', '')

    if idx < total:
        answers = session.get('quiz_answers', {})
        answers[str(idx)] = selected  # 覆盖式写入，支持回退后改答案
        session['quiz_answers'] = answers
        session['quiz_index'] = idx + 1

    return redirect(url_for('quiz_question'))


@app.route('/quiz/prev', methods=['POST'])
def quiz_prev():
    idx = session.get('quiz_index', 0)
    session['quiz_index'] = max(0, idx - 1)
    # 标记为来自回退，前端听力题不自动播放
    return redirect(url_for('quiz_question', from_prev=1))


@app.route('/quiz/submit')
def quiz_submit():
    quiz_data = _load_quiz_data(session.get('quiz_token', ''))
    questions = quiz_data.get('questions', [])
    word_ids = quiz_data.get('word_ids', [])
    answers = session.get('quiz_answers', {})
    mode = session.get('quiz_mode', 'learn')

    if not questions:
        return redirect(url_for('index'))

    correct_count = 0
    wrong_items = []

    for i, q in enumerate(questions):
        user_ans = answers.get(str(i), '')
        is_correct = (user_ans == q['correct'])
        if is_correct:
            correct_count += 1
        else:
            wrong_items.append({
                'english': q['english'],
                'word_id': q['word_id'],
                'user_answer': user_ans,
                'correct_answer': q['correct']
            })

    total = len(questions)
    accuracy = correct_count / total if total > 0 else 0

    # 清理服务端临时文件
    _delete_quiz_data(session.pop('quiz_token', None))

    if mode == 'learn':
        is_synonym_flow = bool(session.get('quiz_synonym_flow'))

        if accuracy == 1.0:
            # 通关处理
            list_id = get_current_list_id()

            # 关键：原始学习会话的 word_ids 全集（不受 quiz_retry 覆盖影响）
            # 优先用 session['quiz_original_word_ids']（learn_quiz 入口保存）
            # 兜底用 quiz_data 的 word_ids（旧 session 兼容）
            original_word_ids = session.get('quiz_original_word_ids') or list(word_ids)
            original_total = len(original_word_ids)

            if is_synonym_flow:
                # 同义词学习流：不操作 learn_session（同义词流没这个）
                # 但要 UPDATE words.status='mastered' 对齐普通流，让首页统计正确
                try:
                    db = get_db()
                    for wid in original_word_ids:
                        db.execute("UPDATE words SET status='mastered' WHERE id=?", (wid,))
                    # learn_synonym 记录已在跳测验前写过，这里补一条 quiz 记录对齐普通流
                    db.execute(
                        'INSERT INTO study_log (list_id, date, mode, word_ids, accuracy, duration_s) VALUES (?,?,?,?,?,?)',
                        (list_id, str(date.today()), 'quiz', json.dumps(original_word_ids), 1.0, 0)
                    )
                    db.commit()
                    db.close()
                except Exception as e:
                    print(f'[quiz_submit synonym_flow] mastered/study_log 写入失败: {e}')

                # 组装本次单词列表供结果页"完全掌握"勾选区
                review_items = _fetch_review_items(original_word_ids, list_id, list_type='synonym')

                session.pop('quiz_answers', None)
                session.pop('quiz_max_reached', None)
                session.pop('quiz_synonym_flow', None)
                session.pop('pending_quiz_return_to', None)
                session.pop('quiz_original_word_ids', None)

                return render_template('quiz_result.html',
                                       mode='learn',
                                       passed=True,
                                       correct=original_total,
                                       total=original_total,
                                       accuracy=100,
                                       wrong_items=[],
                                       synonym_flow=True,
                                       review_items=review_items)

            # 普通学习流通关
            sess_id = session.get('learn_session_id')
            start_time = None

            db = get_db()
            if sess_id:
                ls = db.execute('SELECT * FROM learn_session WHERE id=?', (sess_id,)).fetchone()
                if ls:
                    start_time = ls['created_at']
                    # 更权威的原始全集：learn_session.word_ids（DB 写入后不变）
                    try:
                        db_original = json.loads(ls['word_ids'])
                        if db_original:
                            original_word_ids = db_original
                            original_total = len(original_word_ids)
                    except Exception:
                        pass
                db.execute("UPDATE learn_session SET status='done' WHERE id=?", (sess_id,))

            for wid in original_word_ids:
                db.execute("UPDATE words SET status='mastered' WHERE id=?", (wid,))

            # 计算用时
            duration = 0
            if start_time:
                try:
                    t0 = datetime.strptime(start_time[:19], '%Y-%m-%d %H:%M:%S')
                    duration = int((datetime.now() - t0).total_seconds())
                except Exception:
                    pass

            db.execute(
                'INSERT INTO study_log (list_id, date, mode, word_ids, accuracy, duration_s) VALUES (?,?,?,?,?,?)',
                (list_id, str(date.today()), 'learn', json.dumps(original_word_ids), 1.0, duration)
            )
            db.commit()
            db.close()

            # 组装本次单词列表供结果页"完全掌握"勾选区
            review_items = _fetch_review_items(
                original_word_ids, list_id,
                list_type=_get_list_type(list_id)
            )

            session.pop('learn_session_id', None)
            session.pop('learn_total', None)
            session.pop('learn_max_reached', None)
            session.pop('quiz_answers', None)
            session.pop('quiz_max_reached', None)
            session.pop('quiz_original_word_ids', None)

            return render_template('quiz_result.html',
                                   mode='learn',
                                   passed=True,
                                   correct=original_total,
                                   total=original_total,
                                   accuracy=100,
                                   wrong_items=[],
                                   review_items=review_items)
        else:
            return render_template('quiz_result.html',
                                   mode='learn',
                                   passed=False,
                                   correct=correct_count,
                                   total=total,
                                   accuracy=int(accuracy * 100),
                                   wrong_items=wrong_items,
                                   synonym_flow=is_synonym_flow)

    else:  # test mode
        list_id = get_current_list_id()
        # 区分文字测试 / 听力测试
        test_type = session.get('quiz_test_type', 'text')
        log_mode = 'test_audio' if test_type == 'audio' else 'test_text'

        db = get_db()
        db.execute(
            'INSERT INTO study_log (list_id, date, mode, word_ids, accuracy) VALUES (?,?,?,?,?)',
            (list_id, str(date.today()), log_mode, json.dumps(word_ids), accuracy)
        )
        db.commit()
        db.close()

        score_label = '优秀 🎉' if accuracy >= 0.9 else ('良好 👍' if accuracy >= 0.7 else '加油 💪')
        test_count = session.get('test_count', total)

        # 组装本次单词列表供结果页"完全掌握"勾选区
        # 只展示答对的词（作为完全掌握候选），listening 用 chinese，文字用词库 type 决定
        list_type = _get_list_type(list_id)
        display_type = 'standard' if test_type == 'audio' else list_type
        review_items = _fetch_review_items(word_ids, list_id, list_type=display_type)
        # 附加每个词的答题结果
        wrong_wids = {w['word_id'] for w in wrong_items}
        for item in review_items:
            item['is_correct'] = item['word_id'] not in wrong_wids

        session.pop('quiz_answers', None)
        session.pop('quiz_test_type', None)
        session.pop('quiz_max_reached', None)

        return render_template('test_result.html',
                               correct=correct_count,
                               total=total,
                               accuracy=int(accuracy * 100),
                               score_label=score_label,
                               wrong_items=wrong_items,
                               test_count=test_count,
                               test_type=test_type,
                               review_items=review_items)


@app.route('/quiz/retry', methods=['POST'])
def quiz_retry():
    """错题重做：对错题重新生成题目"""
    wrong_items = request.get_json().get('wrong_items', [])
    list_id = get_current_list_id()
    if not list_id:
        return jsonify({'error': '无词库'}), 400
    word_ids = [w['word_id'] for w in wrong_items]

    # 错题循环：与首轮测验保持一致的出题方式（按词库 type）
    list_type = _get_list_type(list_id)
    questions = generate_quiz_questions(word_ids, list_id, list_type=list_type)
    if not questions:
        return jsonify({'error': '无法生成题目'}), 400

    random.shuffle(questions)
    # 存到服务端文件
    token = _save_quiz_data({'questions': questions, 'word_ids': word_ids})
    session['quiz_token'] = token
    session['quiz_index'] = 0
    session['quiz_answers'] = {}
    session['quiz_mode'] = 'learn'
    session['quiz_max_reached'] = 1  # 进度峰值重置

    return jsonify({'ok': True})


# ─────────────────────────────────────────
# 测试模式
# ─────────────────────────────────────────

@app.route('/test/setup')
def test_setup():
    list_id = get_current_list_id()
    if not list_id:
        return redirect(url_for('index'))
    stats = get_list_stats(list_id)

    db = get_db()
    list_count = db.execute('SELECT COUNT(*) FROM word_lists').fetchone()[0]
    db.close()
    show_picker = (list_count >= 2) and (not session.get('list_picked'))

    # 已掌握词不足 4 个（干扰项池最低门槛）→ 引导页拦截
    not_enough_mastered = stats['mastered'] < 4
    default_m = min(10, stats['mastered']) if stats['mastered'] > 0 else 10

    return render_template('test_setup.html', stats=stats, default_m=default_m,
                           show_picker=show_picker,
                           not_enough_mastered=not_enough_mastered)


@app.route('/test/start', methods=['POST'])
def test_start():
    list_id = get_current_list_id()
    if not list_id:
        return redirect(url_for('index'))
    m = request.form.get('m', 10, type=int)
    test_type = request.form.get('test_type', 'text')
    if test_type not in ('text', 'audio'):
        test_type = 'text'

    db = get_db()
    mastered_count = db.execute(
        "SELECT COUNT(*) FROM words WHERE list_id=? AND status='mastered'",
        (list_id,)
    ).fetchone()[0]

    if mastered_count < 4:
        db.close()
        return render_template(
            'quiz_error.html',
            message='当前词库已掌握词不足 4 个，请先去学习一些单词再来测试'
        )

    m = min(m, mastered_count)
    words = db.execute(
        "SELECT id FROM words WHERE list_id=? AND status='mastered' "
        "ORDER BY RANDOM() LIMIT ?",
        (list_id, m)
    ).fetchall()
    db.close()

    word_ids = [w['id'] for w in words]
    # 正式测试：听力模式强制 standard（保持"听英文 → 选中文释义"语义）；
    # 文字模式按词库 type 决定（synonym 词库 → 英文同义词选项）
    if test_type == 'audio':
        list_type = 'standard'
    else:
        list_type = _get_list_type(list_id)
    questions = generate_quiz_questions(word_ids, list_id, list_type=list_type)
    if not questions:
        return render_template('quiz_error.html', message='词库单词数不足（至少需要 4 个词）')

    random.shuffle(questions)
    # 存到服务端文件，避免 cookie 超限
    token = _save_quiz_data({
        'questions': questions,
        'word_ids': word_ids,
        'question_type': test_type,
    })
    session['quiz_token'] = token
    session['quiz_index'] = 0
    session['quiz_answers'] = {}
    session['quiz_mode'] = 'test'
    session['quiz_test_type'] = test_type
    session['quiz_max_reached'] = 1  # 进度峰值重置
    session['test_count'] = m

    return redirect(url_for('quiz_question'))


# ─────────────────────────────────────────
# 同义词学习（独立翻卡模式：正面英文 / 背面同义词）
# 仅基于 session 维护一个临时队列，不写 learn_session / study_log
# ─────────────────────────────────────────

def _write_synonym_study_log():
    """把同义词学习记录写入 study_log（mode='learn_synonym'）。

    在"跳测验之前"调用，确保即使用户在测验中途退出，
    学习行为也已计入 streak / today_completed 统计。

    幂等：如果 session 中 syn_word_ids 已被消费（清空），则跳过写入。
    """
    word_ids = session.get('syn_word_ids') or []
    list_id = session.get('syn_list_id') or get_current_list_id()
    started_at = session.get('syn_started_at')

    if not word_ids or not list_id:
        return

    duration = 0
    if started_at:
        try:
            t0 = datetime.fromisoformat(started_at)
            duration = max(0, int((datetime.now() - t0).total_seconds()))
        except Exception:
            duration = 0

    try:
        db = get_db()
        db.execute(
            'INSERT INTO study_log (list_id, date, mode, word_ids, accuracy, duration_s) VALUES (?,?,?,?,?,?)',
            (list_id, str(date.today()), 'learn_synonym', json.dumps(word_ids), 1.0, duration)
        )
        db.commit()
        db.close()
        # 标记已写入，避免 synonym_done 重复写
        session['syn_logged'] = True
    except Exception as e:
        print(f'[_write_synonym_study_log] 写入失败: {e}')


def _synonym_enter_quiz_or_done():
    """同义词学完最后一张后的跳转决策：
    - 词库单词够 4 个 → 写 study_log + 跳测验
    - 不够 → 直接跳完成页（沿用旧行为，测验流程要求 ≥4 个干扰项词库）
    """
    word_ids = session.get('syn_word_ids') or []
    list_id = session.get('syn_list_id') or get_current_list_id()

    if not word_ids or not list_id:
        return redirect(url_for('synonym_done'))

    # 检查词库是否够生成干扰项（同义词测验也走 generate_quiz_questions）
    db = get_db()
    total_words = db.execute('SELECT COUNT(*) FROM words WHERE list_id=?', (list_id,)).fetchone()[0]
    db.close()

    if total_words < 4:
        # 词库太小，直接跳完成页（不测验）
        return redirect(url_for('synonym_done'))

    # 先记账，再跳测验（用户中途退出也已计入 streak）
    _write_synonym_study_log()

    # 标记本次测验来源 + 测验范围（learn_quiz 会优先消费）
    session['pending_quiz_word_ids'] = list(word_ids)
    session['pending_quiz_return_to'] = 'synonym_done'

    return redirect(url_for('learn_quiz'))


@app.route('/learn/synonym/setup')
def synonym_setup():
    list_id = get_current_list_id()
    if not list_id:
        return redirect(url_for('index'))
    stats = get_list_stats(list_id)

    db = get_db()
    list_count = db.execute('SELECT COUNT(*) FROM word_lists').fetchone()[0]
    db.close()
    show_picker = (list_count >= 2) and (not session.get('list_picked'))

    # 学习范围只算"未掌握 + 含同义词"
    available = stats['unmastered_with_synonyms']
    default_n = min(20, available) if available > 0 else 0
    return render_template('learn_synonym_setup.html',
                           stats=stats,
                           default_n=default_n,
                           show_picker=show_picker)


@app.route('/learn/synonym/start', methods=['POST'])
def synonym_start():
    list_id = get_current_list_id()
    if not list_id:
        return redirect(url_for('index'))
    n = request.form.get('n', 20, type=int)

    db = get_db()
    rows = db.execute(
        "SELECT id FROM words WHERE list_id=? AND status='unmastered' "
        "AND synonyms IS NOT NULL AND synonyms!='' "
        "ORDER BY RANDOM() LIMIT ?",
        (list_id, n)
    ).fetchall()
    db.close()

    word_ids = [r['id'] for r in rows]
    if not word_ids:
        return redirect(url_for('synonym_setup'))

    session['syn_queue'] = word_ids
    session['syn_total'] = len(word_ids)
    session['syn_index'] = 0  # 游标模型：当前在第几个（0-based）
    session['syn_word_ids'] = word_ids  # 原始全集，供 done 时写 study_log
    session['syn_started_at'] = datetime.now().isoformat()  # 开始时间，供 done 时计算 duration
    session['syn_list_id'] = list_id  # 锁定本次学习对应的词库 id（即使中途切库也写对日志）
    return redirect(url_for('synonym_card'))


@app.route('/learn/synonym/card')
def synonym_card():
    # 优先用游标模型（支持上一张）；旧 session 走 lazy 迁移
    word_ids = session.get('syn_word_ids') or []
    if not word_ids:
        # 旧路径兜底：从 queue 取
        queue = session.get('syn_queue') or []
        if not queue:
            return _synonym_enter_quiz_or_done()
        current_id = queue[0]
        total = session.get('syn_total', len(queue))
        done = total - len(queue)
        current_pos = done + 1
        prev_available = False
    else:
        total = session.get('syn_total', len(word_ids))
        # Lazy 迁移：旧 session 没有 syn_index，按 queue 残量推断
        if 'syn_index' not in session:
            queue = session.get('syn_queue') or word_ids
            session['syn_index'] = max(0, total - len(queue))
        idx = session['syn_index']
        if idx >= total:
            return _synonym_enter_quiz_or_done()
        current_id = word_ids[idx]
        current_pos = idx + 1
        prev_available = idx > 0

    db = get_db()
    word = db.execute('SELECT * FROM words WHERE id=?', (current_id,)).fetchone()
    db.close()

    if not word:
        # 词被删了：游标推进一位
        if 'syn_index' in session:
            session['syn_index'] = session['syn_index'] + 1
        else:
            # 旧路径
            queue = session.get('syn_queue') or []
            if queue:
                queue.pop(0)
                session['syn_queue'] = queue
        return redirect(url_for('synonym_card'))

    return render_template('flashcard_synonym.html',
                           word=dict(word),
                           current=current_pos,
                           total=total,
                           prev_available=prev_available)


@app.route('/learn/synonym/next', methods=['POST'])
def synonym_next():
    word_ids = session.get('syn_word_ids') or []
    total = session.get('syn_total', len(word_ids))

    if word_ids:
        # 游标模型
        if 'syn_index' not in session:
            queue = session.get('syn_queue') or word_ids
            session['syn_index'] = max(0, total - len(queue))
        idx = session['syn_index'] + 1
        if idx >= total:
            session['syn_index'] = total
            return _synonym_enter_quiz_or_done()
        session['syn_index'] = idx
        # 同步维护 syn_queue 以保持兼容（虽然不再读）
        session['syn_queue'] = word_ids[idx:]
        return redirect(url_for('synonym_card'))

    # 旧路径兜底
    queue = session.get('syn_queue') or []
    if queue:
        queue.pop(0)
        session['syn_queue'] = queue
    if not queue:
        return _synonym_enter_quiz_or_done()
    return redirect(url_for('synonym_card'))


@app.route('/learn/synonym/prev', methods=['POST'])
def synonym_prev():
    """同义词学习：回到上一张（首张时不动）"""
    word_ids = session.get('syn_word_ids') or []
    total = session.get('syn_total', len(word_ids))

    if not word_ids:
        return redirect(url_for('synonym_card'))

    if 'syn_index' not in session:
        queue = session.get('syn_queue') or word_ids
        session['syn_index'] = max(0, total - len(queue))

    session['syn_index'] = max(0, session['syn_index'] - 1)
    # 同步 queue
    session['syn_queue'] = word_ids[session['syn_index']:]
    return redirect(url_for('synonym_card'))


@app.route('/learn/synonym/abandon', methods=['POST'])
def synonym_abandon():
    session.pop('syn_queue', None)
    session.pop('syn_total', None)
    session.pop('syn_index', None)
    session.pop('syn_word_ids', None)
    session.pop('syn_started_at', None)
    session.pop('syn_list_id', None)
    session.pop('syn_logged', None)
    return redirect(url_for('index'))


@app.route('/learn/synonym/done')
def synonym_done():
    total = session.pop('syn_total', 0)
    word_ids = session.pop('syn_word_ids', None) or []
    started_at = session.pop('syn_started_at', None)
    list_id = session.pop('syn_list_id', None) or get_current_list_id()
    already_logged = session.pop('syn_logged', False)
    session.pop('syn_queue', None)
    session.pop('syn_index', None)

    # 写入 study_log（mode='learn_synonym'）：
    # - 若 _write_synonym_study_log() 已在跳测验前写过（syn_logged=True），跳过
    # - 若词库太小未走测验、或本路由被直接访问，则在这里兜底写入
    if not already_logged and word_ids and list_id:
        duration = 0
        if started_at:
            try:
                t0 = datetime.fromisoformat(started_at)
                duration = max(0, int((datetime.now() - t0).total_seconds()))
            except Exception:
                duration = 0
        try:
            db = get_db()
            db.execute(
                'INSERT INTO study_log (list_id, date, mode, word_ids, accuracy, duration_s) VALUES (?,?,?,?,?,?)',
                (list_id, str(date.today()), 'learn_synonym', json.dumps(word_ids), 1.0, duration)
            )
            db.commit()
            db.close()
        except Exception as e:
            # 写入失败仅 warn，不阻塞页面跳转
            print(f'[synonym_done] study_log 写入失败: {e}')

    return render_template('flashcard_synonym_done.html', total=total)


# ─────────────────────────────────────────
# 词库管理
# ─────────────────────────────────────────

@app.route('/library')
def library():
    list_id = get_current_list_id()
    if not list_id:
        return redirect(url_for('index'))

    db = get_db()
    current_list = db.execute('SELECT * FROM word_lists WHERE id=?', (list_id,)).fetchone()
    words = db.execute(
        'SELECT * FROM words WHERE list_id=? ORDER BY english ASC',
        (list_id,)
    ).fetchall()
    db.close()

    return render_template('library.html',
                           current_list=dict(current_list),
                           words=[dict(w) for w in words])


@app.route('/api/word/<int:word_id>', methods=['PUT'])
def update_word(word_id):
    data = request.get_json()
    fields = {}
    if 'english' in data:
        fields['english'] = data['english'].strip()
    if 'chinese' in data:
        fields['chinese'] = data['chinese'].strip()
    if 'phonetic' in data:
        fields['phonetic'] = data['phonetic'].strip()
    if 'pos' in data:
        fields['pos'] = data['pos'].strip()
    if 'synonyms' in data:
        fields['synonyms'] = data['synonyms'].strip()
    if 'status' in data and data['status'] in ('mastered', 'unmastered', 'fully_mastered'):
        fields['status'] = data['status']

    if not fields:
        return jsonify({'error': '无有效字段'}), 400

    set_clause = ', '.join(f'{k}=?' for k in fields)
    values = list(fields.values()) + [word_id]

    db = get_db()
    db.execute(f'UPDATE words SET {set_clause} WHERE id=?', values)
    db.commit()
    db.close()

    return jsonify({'ok': True})


@app.route('/api/word/<int:word_id>', methods=['DELETE'])
def delete_word(word_id):
    db = get_db()
    db.execute('DELETE FROM words WHERE id=?', (word_id,))
    db.commit()
    db.close()
    return jsonify({'ok': True})


@app.route('/mastery/promote', methods=['POST'])
def mastery_promote():
    """把一批词的 status 从 'mastered' 升级为 'fully_mastered'。

    请求体：{"word_ids": [1, 2, 3, ...]}
    仅当词当前 status='mastered' 时才升级；其它状态保持不变。
    """
    data = request.get_json(silent=True) or {}
    word_ids = data.get('word_ids') or []

    if not isinstance(word_ids, list):
        return jsonify({'error': 'word_ids 必须是数组'}), 400

    # 过滤出合法的整数 id
    valid_ids = []
    for wid in word_ids:
        try:
            valid_ids.append(int(wid))
        except (TypeError, ValueError):
            continue

    if not valid_ids:
        return jsonify({'ok': True, 'promoted': 0})

    db = get_db()
    promoted = 0
    for wid in valid_ids:
        cursor = db.execute(
            "UPDATE words SET status='fully_mastered' WHERE id=? AND status='mastered'",
            (wid,)
        )
        promoted += cursor.rowcount
    db.commit()
    db.close()

    return jsonify({'ok': True, 'promoted': promoted})


@app.route('/api/list/<int:list_id>', methods=['DELETE'])
def delete_list(list_id):
    """删除整个词库（外键 CASCADE 自动清理 words、learn_session）"""
    db = get_db()
    row = db.execute('SELECT id FROM word_lists WHERE id=?', (list_id,)).fetchone()
    if not row:
        db.close()
        return jsonify({'error': '词库不存在'}), 404
    db.execute('DELETE FROM word_lists WHERE id=?', (list_id,))
    db.commit()
    db.close()

    # 若删除的是当前选中词库，清除 session
    if session.get('list_id') == list_id:
        session.pop('list_id', None)

    return jsonify({'ok': True})


# ─────────────────────────────────────────
# 设置 / 备份
# ─────────────────────────────────────────

@app.route('/settings')
def settings():
    return render_template('settings.html')


@app.route('/api/export')
def export_data():
    db = get_db()
    word_lists = [dict(r) for r in db.execute('SELECT * FROM word_lists').fetchall()]
    words = [dict(r) for r in db.execute('SELECT * FROM words').fetchall()]
    study_log = [dict(r) for r in db.execute('SELECT * FROM study_log').fetchall()]
    db.close()

    payload = {
        'version': 1,
        'exported_at': datetime.now().isoformat(),
        'word_lists': word_lists,
        'words': words,
        'study_log': study_log
    }

    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
    json.dump(payload, tmp, ensure_ascii=False, indent=2)
    tmp.close()

    filename = f"vocab_backup_{date.today().strftime('%Y%m%d')}.json"
    return send_file(tmp.name, as_attachment=True, download_name=filename, mimetype='application/json')


@app.route('/api/import_data', methods=['POST'])
def import_data():
    if 'file' not in request.files:
        return jsonify({'error': '未上传文件'}), 400

    f = request.files['file']
    try:
        payload = json.load(f)
    except Exception:
        return jsonify({'error': '文件格式不正确，请选择由本应用导出的 .json 文件'}), 400

    if 'word_lists' not in payload or 'words' not in payload:
        return jsonify({'error': '文件格式不正确，请选择由本应用导出的 .json 文件'}), 400

    db = get_db()
    db.execute('DELETE FROM study_log')
    db.execute('DELETE FROM words')
    db.execute('DELETE FROM word_lists')
    db.execute('DELETE FROM learn_session')

    for wl in payload['word_lists']:
        db.execute(
            'INSERT INTO word_lists (id, name, source_file, word_count, created_at) VALUES (?,?,?,?,?)',
            (wl['id'], wl['name'], wl.get('source_file', ''), wl.get('word_count', 0), wl.get('created_at', ''))
        )
    for w in payload['words']:
        db.execute(
            'INSERT INTO words (id, list_id, english, chinese, phonetic, pos, synonyms, status, created_at) VALUES (?,?,?,?,?,?,?,?,?)',
            (w['id'], w['list_id'], w['english'], w['chinese'],
             w.get('phonetic', ''), w.get('pos', ''), w.get('synonyms', ''),
             w.get('status', 'unmastered'), w.get('created_at', ''))
        )
    for log in payload.get('study_log', []):
        db.execute(
            'INSERT INTO study_log (id, list_id, date, mode, word_ids, accuracy, duration_s, created_at) VALUES (?,?,?,?,?,?,?,?)',
            (log['id'], log.get('list_id'), log['date'], log['mode'], log['word_ids'],
             log.get('accuracy'), log.get('duration_s'), log.get('created_at', ''))
        )

    db.commit()
    db.close()
    session.clear()

    return jsonify({'ok': True})


# ─────────────────────────────────────────
# 启动
# ─────────────────────────────────────────

def _find_free_port(preferred: int = 5000, fallbacks: tuple = (5001, 5002, 5050, 5500, 8000, 8080)) -> int:
    """优先用 preferred 端口；被占用则尝试 fallback 列表；都不通则交给系统选"""
    import socket
    candidates = (preferred,) + fallbacks
    for port in candidates:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    # 兜底：让系统分配
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def _open_browser_when_ready(url: str, delay: float = 1.5):
    """延迟开浏览器，给 Flask 启动留时间"""
    import threading
    import time
    import webbrowser

    def _open():
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception:
            pass

    threading.Thread(target=_open, daemon=True).start()


if __name__ == '__main__':
    init_db()
    # 打包环境：找可用端口 + 自动开浏览器 + 启动心跳守护
    if is_frozen():
        port = _find_free_port(5000)
        url = f'http://127.0.0.1:{port}'
        print(f'[IELTSVocab] Starting on {url}')
        _start_heartbeat_watchdog()
        _open_browser_when_ready(url)
        app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)
    else:
        # 开发模式：固定 5000，不自动开浏览器（避免开发时打扰）
        # 开发模式不启用心跳——本地开发要保留 Ctrl+C 控制权
        app.run(host='127.0.0.1', port=5000, debug=False)
