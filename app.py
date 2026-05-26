import json
import os
import random
import tempfile
import uuid
from datetime import date, datetime, timedelta

from flask import (Flask, jsonify, redirect, render_template, request,
                   send_file, session, url_for)

from database import get_db, init_db
from excel_parser import (apply_mapping, guess_columns, parse_table_raw)
from paths import is_frozen, resource_dir, tmp_parse_dir
from pdf_parser import parse_pdf

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
    mastered = db.execute("SELECT COUNT(*) FROM words WHERE list_id=? AND status='mastered'", (list_id,)).fetchone()[0]
    db.close()
    return {'total': total, 'mastered': mastered, 'unmastered': total - mastered}


def calc_streak():
    """计算全局连续打卡天数（任意词库完成学习100%通关）"""
    db = get_db()
    rows = db.execute(
        "SELECT DISTINCT date FROM study_log WHERE mode='learn' AND accuracy=1.0 ORDER BY date DESC"
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
    """今日是否已通关（accuracy=1.0 的学习记录）"""
    db = get_db()
    row = db.execute(
        "SELECT id FROM study_log WHERE list_id=? AND mode='learn' AND accuracy=1.0 AND date=?",
        (list_id, str(date.today()))
    ).fetchone()
    db.close()
    return row is not None


def generate_quiz_questions(word_ids, list_id):
    """为 word_ids 列表生成 4 选 1 题目，返回题目列表"""
    db = get_db()
    questions = []
    all_words = db.execute('SELECT id, english, chinese FROM words WHERE list_id=?', (list_id,)).fetchall()
    all_words = [dict(w) for w in all_words]
    db.close()

    if len(all_words) < 4:
        return None  # 词库不足

    for wid in word_ids:
        correct = next((w for w in all_words if w['id'] == wid), None)
        if not correct:
            continue
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
    completed_today = today_completed(list_id)

    return render_template('index.html',
                           no_lists=False,
                           all_lists=all_lists,
                           current_list=current_list,
                           stats=stats,
                           streak=streak,
                           active_session=active_session,
                           completed_today=completed_today)


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
        if has_active_quiz:
            _delete_quiz_data(session.pop('quiz_token', None))
            session.pop('quiz_index', None)
            session.pop('quiz_answers', None)
            session.pop('quiz_mode', None)
            session.pop('quiz_test_type', None)
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
            # ── PDF 流程：直接解析为 entries，跳预览页 ──
            try:
                entries = parse_pdf(tmp_path)
            except Exception as e:
                return jsonify({'error': f'PDF 解析失败：{e}'}), 400

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
    skip_first_row = bool(data.get('skip_first_row', True))

    try:
        english_col = int(english_col)
        chinese_col = int(chinese_col)
        phonetic_col = int(phonetic_col)
        pos_col = int(pos_col)
    except (TypeError, ValueError):
        return jsonify({'error': '列参数格式错误'}), 400

    if english_col < 0 or chinese_col < 0:
        return jsonify({'error': '请指定英文列和中文列'}), 400
    if english_col == chinese_col:
        return jsonify({'error': '英文列和中文列不能相同'}), 400

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
            skip_first_row=skip_first_row,
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
    # 创建词库记录
    c = db.execute(
        'INSERT INTO word_lists (name, source_file, word_count) VALUES (?, ?, 0)',
        (list_name, session.get('import_filename', ''))
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
                'INSERT OR IGNORE INTO words (list_id, english, chinese, phonetic, pos) VALUES (?, ?, ?, ?, ?)',
                (new_list_id, english, chinese,
                 entry.get('phonetic', '').strip(),
                 entry.get('pos', '').strip())
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
        "INSERT INTO learn_session (list_id, date, word_ids, remaining_ids, status) VALUES (?, ?, ?, ?, 'in_progress')",
        (list_id, str(date.today()), json.dumps(word_ids), json.dumps(word_ids))
    )
    session['learn_session_id'] = c.lastrowid
    session['learn_total'] = len(word_ids)
    db.commit()
    db.close()

    return redirect(url_for('learn_card'))


@app.route('/learn/continue')
def learn_continue():
    list_id = get_current_list_id()
    active = get_active_session(list_id)
    if active:
        session['learn_session_id'] = active['id']
        session['learn_total'] = len(json.loads(active['word_ids']))
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

    remaining = json.loads(ls['remaining_ids'] or '[]')
    if not remaining:
        db.close()
        return redirect(url_for('learn_quiz'))

    current_id = remaining[0]
    word = db.execute('SELECT * FROM words WHERE id=?', (current_id,)).fetchone()
    db.close()

    total = session.get('learn_total', len(json.loads(ls['word_ids'])))
    done = total - len(remaining)

    return render_template('flashcard.html',
                           word=dict(word),
                           current=done + 1,
                           total=total)


@app.route('/learn/next', methods=['POST'])
def learn_next():
    sess_id = session.get('learn_session_id')
    if not sess_id:
        return redirect(url_for('index'))

    db = get_db()
    ls = db.execute('SELECT * FROM learn_session WHERE id=?', (sess_id,)).fetchone()
    remaining = json.loads(ls['remaining_ids'] or '[]')

    if remaining:
        remaining.pop(0)

    if remaining:
        db.execute('UPDATE learn_session SET remaining_ids=? WHERE id=?',
                   (json.dumps(remaining), sess_id))
        db.commit()
        db.close()
        return redirect(url_for('learn_card'))
    else:
        db.execute('UPDATE learn_session SET remaining_ids=? WHERE id=?',
                   (json.dumps([]), sess_id))
        db.commit()
        db.close()
        return redirect(url_for('learn_quiz'))


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
    return redirect(url_for('index'))


# ─────────────────────────────────────────
# 学习测验
# ─────────────────────────────────────────

@app.route('/learn/quiz')
def learn_quiz():
    sess_id = session.get('learn_session_id')
    if not sess_id:
        return redirect(url_for('index'))

    list_id = get_current_list_id()
    if not list_id:
        return redirect(url_for('index'))
    db = get_db()
    ls = db.execute('SELECT * FROM learn_session WHERE id=?', (sess_id,)).fetchone()

    if not ls or ls['status'] != 'in_progress':
        db.close()
        return redirect(url_for('index'))

    # 检查词库是否够生成干扰项
    total_words = db.execute('SELECT COUNT(*) FROM words WHERE list_id=?', (list_id,)).fetchone()[0]
    if total_words < 4:
        db.close()
        return render_template('quiz_error.html', message='词库单词数不足（至少需要 4 个词）')

    # 取本轮需要测验的词（quiz_word_ids 存错题，否则用 word_ids）
    quiz_ids_raw = ls['quiz_word_ids']
    word_ids = json.loads(quiz_ids_raw) if quiz_ids_raw else json.loads(ls['word_ids'])
    db.close()

    questions = generate_quiz_questions(word_ids, list_id)
    if questions is None:
        return render_template('quiz_error.html', message='词库单词数不足（至少需要 4 个词）')

    random.shuffle(questions)
    # 存到服务端文件，避免 cookie 超限
    token = _save_quiz_data({'questions': questions, 'word_ids': word_ids})
    session['quiz_token'] = token
    session['quiz_index'] = 0
    session['quiz_answers'] = {}
    session['quiz_mode'] = 'learn'

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

    return render_template('quiz.html',
                           question=q,
                           current=idx + 1,
                           total=len(questions),
                           mode=mode,
                           question_type=question_type)


@app.route('/quiz/answer', methods=['POST'])
def quiz_answer():
    idx = session.get('quiz_index', 0)
    quiz_data = _load_quiz_data(session.get('quiz_token', ''))
    total = len(quiz_data.get('questions', []))
    selected = request.form.get('answer', '')

    if idx < total:
        answers = session.get('quiz_answers', {})
        answers[str(idx)] = selected
        session['quiz_answers'] = answers
        session['quiz_index'] = idx + 1

    return redirect(url_for('quiz_question'))


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
        if accuracy == 1.0:
            # 通关处理
            list_id = get_current_list_id()
            sess_id = session.get('learn_session_id')
            start_time = None

            db = get_db()
            if sess_id:
                ls = db.execute('SELECT created_at FROM learn_session WHERE id=?', (sess_id,)).fetchone()
                if ls:
                    start_time = ls['created_at']
                db.execute("UPDATE learn_session SET status='done' WHERE id=?", (sess_id,))
                for wid in word_ids:
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
                (list_id, str(date.today()), 'learn', json.dumps(word_ids), 1.0, duration)
            )
            db.commit()
            db.close()

            session.pop('learn_session_id', None)
            session.pop('learn_total', None)
            session.pop('quiz_answers', None)

            return render_template('quiz_result.html',
                                   mode='learn',
                                   passed=True,
                                   correct=total,
                                   total=total,
                                   accuracy=100,
                                   wrong_items=[])
        else:
            return render_template('quiz_result.html',
                                   mode='learn',
                                   passed=False,
                                   correct=correct_count,
                                   total=total,
                                   accuracy=int(accuracy * 100),
                                   wrong_items=wrong_items)

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

        session.pop('quiz_answers', None)
        session.pop('quiz_test_type', None)

        return render_template('test_result.html',
                               correct=correct_count,
                               total=total,
                               accuracy=int(accuracy * 100),
                               score_label=score_label,
                               wrong_items=wrong_items,
                               test_count=test_count,
                               test_type=test_type)


@app.route('/quiz/retry', methods=['POST'])
def quiz_retry():
    """错题重做：对错题重新生成题目"""
    wrong_items = request.get_json().get('wrong_items', [])
    list_id = get_current_list_id()
    if not list_id:
        return jsonify({'error': '无词库'}), 400
    word_ids = [w['word_id'] for w in wrong_items]

    questions = generate_quiz_questions(word_ids, list_id)
    if not questions:
        return jsonify({'error': '无法生成题目'}), 400

    random.shuffle(questions)
    # 存到服务端文件
    token = _save_quiz_data({'questions': questions, 'word_ids': word_ids})
    session['quiz_token'] = token
    session['quiz_index'] = 0
    session['quiz_answers'] = {}
    session['quiz_mode'] = 'learn'

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

    return render_template('test_setup.html', stats=stats, default_m=10,
                           show_picker=show_picker)


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
    total_count = db.execute('SELECT COUNT(*) FROM words WHERE list_id=?', (list_id,)).fetchone()[0]

    if total_count < 4:
        db.close()
        return render_template('quiz_error.html', message='词库单词数不足（至少需要 4 个词）')

    m = min(m, total_count)
    words = db.execute(
        'SELECT id FROM words WHERE list_id=? ORDER BY RANDOM() LIMIT ?',
        (list_id, m)
    ).fetchall()
    db.close()

    word_ids = [w['id'] for w in words]
    questions = generate_quiz_questions(word_ids, list_id)
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
    session['test_count'] = m

    return redirect(url_for('quiz_question'))


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
    if 'status' in data and data['status'] in ('mastered', 'unmastered'):
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
            'INSERT INTO words (id, list_id, english, chinese, status, created_at) VALUES (?,?,?,?,?,?)',
            (w['id'], w['list_id'], w['english'], w['chinese'], w.get('status', 'unmastered'), w.get('created_at', ''))
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
    # 打包环境：找可用端口 + 自动开浏览器
    if is_frozen():
        port = _find_free_port(5000)
        url = f'http://127.0.0.1:{port}'
        print(f'[IELTSVocab] Starting on {url}')
        _open_browser_when_ready(url)
        app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)
    else:
        # 开发模式：固定 5000，不自动开浏览器（避免开发时打扰）
        app.run(host='127.0.0.1', port=5000, debug=False)
