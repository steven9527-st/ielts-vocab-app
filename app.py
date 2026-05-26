import json
import os
import random
import tempfile
import uuid
from datetime import date, datetime, timedelta

from flask import (Flask, jsonify, redirect, render_template, request,
                   send_file, session, url_for)

from database import get_db, init_db
from pdf_parser import parse_pdf

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Jinja2 enumerate 过滤器
app.jinja_env.globals['enumerate'] = enumerate

# 服务器端临时存储目录（解析结果太大不能放 cookie）
_TMP_DIR = os.path.join(os.path.dirname(__file__), '.tmp_parse')
os.makedirs(_TMP_DIR, exist_ok=True)


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


# ─────────────────────────────────────────
# 初始化
# ─────────────────────────────────────────

@app.before_request
def setup():
    init_db()


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
    return redirect(url_for('index'))


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
    if not f.filename.lower().endswith('.pdf'):
        return jsonify({'error': '仅支持 .pdf 文件'}), 400

    # 保存到临时文件解析
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        f.save(tmp.name)
        tmp_path = tmp.name

    try:
        entries = parse_pdf(tmp_path)
    finally:
        os.unlink(tmp_path)

    # 检查已有词库中的重复词
    list_id = get_current_list_id()
    existing = set()
    if list_id:
        db = get_db()
        rows = db.execute('SELECT english FROM words WHERE list_id=?', (list_id,)).fetchall()
        existing = {r['english'].lower() for r in rows}
        db.close()

    for entry in entries:
        entry['duplicate'] = (not entry['failed'] and entry['english'].lower() in existing)

    # 保存到服务器端临时文件（避免 cookie 超限）
    token = _save_parse_result(entries)
    session['import_token'] = token
    session['import_filename'] = f.filename

    return jsonify({'entries': entries, 'count': len(entries)})


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
                'INSERT OR IGNORE INTO words (list_id, english, chinese) VALUES (?, ?, ?)',
                (new_list_id, english, chinese)
            )
            count += 1
        except Exception:
            pass

    db.execute('UPDATE word_lists SET word_count=? WHERE id=?', (count, new_list_id))
    db.commit()
    db.close()

    session['list_id'] = new_list_id
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
    return render_template('learn_setup.html', stats=stats, default_n=20)


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
    db = get_db()
    ls = db.execute('SELECT * FROM learn_session WHERE id=?', (sess_id,)).fetchone()

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
    session['quiz_questions'] = questions
    session['quiz_index'] = 0
    session['quiz_answers'] = {}
    session['quiz_mode'] = 'learn'
    session['quiz_word_ids'] = word_ids

    return redirect(url_for('quiz_question'))


@app.route('/quiz/question')
def quiz_question():
    questions = session.get('quiz_questions', [])
    idx = session.get('quiz_index', 0)

    if idx >= len(questions):
        return redirect(url_for('quiz_submit'))

    q = questions[idx]
    return render_template('quiz.html',
                           question=q,
                           current=idx + 1,
                           total=len(questions),
                           mode=session.get('quiz_mode', 'learn'))


@app.route('/quiz/answer', methods=['POST'])
def quiz_answer():
    idx = session.get('quiz_index', 0)
    questions = session.get('quiz_questions', [])
    selected = request.form.get('answer', '')

    if idx < len(questions):
        answers = session.get('quiz_answers', {})
        answers[str(idx)] = selected
        session['quiz_answers'] = answers
        session['quiz_index'] = idx + 1

    return redirect(url_for('quiz_question'))


@app.route('/quiz/submit')
def quiz_submit():
    questions = session.get('quiz_questions', [])
    answers = session.get('quiz_answers', {})
    mode = session.get('quiz_mode', 'learn')

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

    if mode == 'learn':
        if accuracy == 1.0:
            # 通关处理
            list_id = get_current_list_id()
            sess_id = session.get('learn_session_id')
            word_ids = session.get('quiz_word_ids', [])
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
            session.pop('quiz_questions', None)
            session.pop('quiz_answers', None)
            session.pop('quiz_word_ids', None)

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
        word_ids = session.get('quiz_word_ids', [])
        db = get_db()
        db.execute(
            'INSERT INTO study_log (list_id, date, mode, word_ids, accuracy) VALUES (?,?,?,?,?)',
            (list_id, str(date.today()), 'test', json.dumps(word_ids), accuracy)
        )
        db.commit()
        db.close()

        score_label = '优秀 🎉' if accuracy >= 0.9 else ('良好 👍' if accuracy >= 0.7 else '加油 💪')
        test_count = session.get('test_count', total)

        session.pop('quiz_questions', None)
        session.pop('quiz_answers', None)
        session.pop('quiz_word_ids', None)

        return render_template('test_result.html',
                               correct=correct_count,
                               total=total,
                               accuracy=int(accuracy * 100),
                               score_label=score_label,
                               wrong_items=wrong_items,
                               test_count=test_count)


@app.route('/quiz/retry', methods=['POST'])
def quiz_retry():
    """错题重做：对错题重新生成题目"""
    wrong_items = request.get_json().get('wrong_items', [])
    list_id = get_current_list_id()
    word_ids = [w['word_id'] for w in wrong_items]

    questions = generate_quiz_questions(word_ids, list_id)
    if not questions:
        return jsonify({'error': '无法生成题目'}), 400

    random.shuffle(questions)
    session['quiz_questions'] = questions
    session['quiz_index'] = 0
    session['quiz_answers'] = {}
    session['quiz_mode'] = 'learn'
    session['quiz_word_ids'] = word_ids

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
    return render_template('test_setup.html', stats=stats, default_m=10)


@app.route('/test/start', methods=['POST'])
def test_start():
    list_id = get_current_list_id()
    m = request.form.get('m', 10, type=int)

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
    session['quiz_questions'] = questions
    session['quiz_index'] = 0
    session['quiz_answers'] = {}
    session['quiz_mode'] = 'test'
    session['quiz_word_ids'] = word_ids
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

if __name__ == '__main__':
    init_db()
    app.run(host='127.0.0.1', port=5000, debug=False)
