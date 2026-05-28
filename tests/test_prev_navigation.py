"""单元测试：翻卡与测验的双向流转（add-prev-navigation）

覆盖：
  • /learn/prev 让 current_index 自减；首张时 prev 无效
  • /quiz/prev 让 quiz_index 自减；首题时 prev 无效
  • 回退后改答案，最终 quiz_answers 是改后的值
  • max_reached 不倒退：前进到 N → prev → display 仍为 N
  • 旧 session 迁移：current_index=NULL 时根据 remaining_ids 回填
  • abandon 清理 learn_max_reached；submit 清理 quiz_max_reached
"""

import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class _BaseCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import paths
        cls._tmp_db = tempfile.mktemp(suffix='.db')
        paths.db_path = lambda: cls._tmp_db  # type: ignore
        import importlib
        import database
        database.DB_PATH = cls._tmp_db
        importlib.reload(database)
        import app as app_module
        importlib.reload(app_module)
        cls.app = app_module.app
        cls.app_module = app_module
        cls.app.config['TESTING'] = True
        cls.db_mod = database

        # 准备词库：6 个词（够生成 4 选 1）
        database.init_db()
        conn = database.get_db()
        conn.execute("INSERT INTO word_lists (id, name) VALUES (1, 'test')")
        for i, (en, zh) in enumerate([
            ('apple', '苹果'), ('banana', '香蕉'), ('cherry', '樱桃'),
            ('date', '枣'), ('elderberry', '接骨木莓'), ('fig', '无花果'),
        ], start=1):
            conn.execute(
                "INSERT INTO words (id, list_id, english, chinese, status) VALUES (?, 1, ?, ?, 'unmastered')",
                (i, en, zh)
            )
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(cls._tmp_db)
        except Exception:
            pass

    def _make_learn_session(self, word_ids, current_index=0, remaining_ids=None):
        """直接插入一个 learn_session，返回 session id"""
        conn = self.db_mod.get_db()
        rem = json.dumps(remaining_ids) if remaining_ids is not None else json.dumps(word_ids)
        c = conn.execute(
            "INSERT INTO learn_session (list_id, date, word_ids, remaining_ids, current_index, status) "
            "VALUES (1, '2026-05-28', ?, ?, ?, 'in_progress')",
            (json.dumps(word_ids), rem, current_index)
        )
        sid = c.lastrowid
        conn.commit()
        conn.close()
        return sid


class TestLearnPrev(_BaseCase):

    def test_learn_prev_decrements_current_index(self):
        sid = self._make_learn_session([1, 2, 3, 4, 5], current_index=3)
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['learn_session_id'] = sid
            sess['learn_total'] = 5
            sess['list_id'] = 1

        resp = client.post('/learn/prev', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)

        conn = self.db_mod.get_db()
        ci = conn.execute('SELECT current_index FROM learn_session WHERE id=?', (sid,)).fetchone()[0]
        conn.close()
        self.assertEqual(ci, 2, '上一张后 current_index 应为 2')

    def test_learn_prev_at_first_card_is_noop(self):
        sid = self._make_learn_session([1, 2, 3], current_index=0)
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['learn_session_id'] = sid
            sess['learn_total'] = 3
            sess['list_id'] = 1

        client.post('/learn/prev', follow_redirects=False)

        conn = self.db_mod.get_db()
        ci = conn.execute('SELECT current_index FROM learn_session WHERE id=?', (sid,)).fetchone()[0]
        conn.close()
        self.assertEqual(ci, 0, '首张时 prev 不应改变 current_index')

    def test_legacy_session_migration(self):
        """旧 session 无 current_index，访问 /learn/card 时按 remaining_ids 推算"""
        # 模拟旧 session：current_index=NULL，word_ids=5个，remaining_ids=3个 → 应推出 ci=2
        conn = self.db_mod.get_db()
        c = conn.execute(
            "INSERT INTO learn_session (list_id, date, word_ids, remaining_ids, current_index, status) "
            "VALUES (1, '2026-05-28', ?, ?, NULL, 'in_progress')",
            (json.dumps([1, 2, 3, 4, 5]), json.dumps([3, 4, 5]))
        )
        sid = c.lastrowid
        conn.commit()
        conn.close()

        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['learn_session_id'] = sid
            sess['learn_total'] = 5
            sess['list_id'] = 1

        client.get('/learn/card', follow_redirects=False)

        conn = self.db_mod.get_db()
        ci = conn.execute('SELECT current_index FROM learn_session WHERE id=?', (sid,)).fetchone()[0]
        conn.close()
        self.assertEqual(ci, 2, '迁移后 current_index 应为 len(word_ids) - len(remaining)')


class TestLearnMaxReached(_BaseCase):

    def test_learn_max_reached_does_not_regress(self):
        """前进到 idx=4 后回退到 idx=1，session.learn_max_reached 应保留 5（=4+1）"""
        sid = self._make_learn_session([1, 2, 3, 4, 5], current_index=4)
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['learn_session_id'] = sid
            sess['learn_total'] = 5
            sess['list_id'] = 1

        # 访问 card 触发 max_reached 更新
        client.get('/learn/card')
        with client.session_transaction() as sess:
            self.assertEqual(sess.get('learn_max_reached'), 5)

        # 回到第 2 张（current_index=1）
        conn = self.db_mod.get_db()
        conn.execute('UPDATE learn_session SET current_index=1 WHERE id=?', (sid,))
        conn.commit()
        conn.close()
        client.get('/learn/card')
        with client.session_transaction() as sess:
            self.assertEqual(sess.get('learn_max_reached'), 5, 'max_reached 不应倒退')

    def test_learn_abandon_clears_max_reached(self):
        sid = self._make_learn_session([1, 2, 3], current_index=2)
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['learn_session_id'] = sid
            sess['learn_total'] = 3
            sess['learn_max_reached'] = 3
            sess['list_id'] = 1

        client.post('/learn/abandon')

        with client.session_transaction() as sess:
            self.assertIsNone(sess.get('learn_max_reached'), 'abandon 后应清理 learn_max_reached')


class TestQuizPrev(_BaseCase):

    def _setup_quiz(self, client, num_questions=5):
        """构造一个 quiz_token 与对应数据"""
        questions = [
            {'word_id': i + 1, 'english': f'w{i}', 'correct': f'ans{i}',
             'options': [f'ans{i}', f'opt{i}b', f'opt{i}c', f'opt{i}d']}
            for i in range(num_questions)
        ]
        token = self.app_module._save_quiz_data({
            'questions': questions,
            'word_ids': [q['word_id'] for q in questions],
        })
        with client.session_transaction() as sess:
            sess['quiz_token'] = token
            sess['quiz_index'] = 0
            sess['quiz_answers'] = {}
            sess['quiz_mode'] = 'learn'
            sess['quiz_max_reached'] = 1
            sess['list_id'] = 1
        return token, questions

    def test_quiz_prev_decrements_index(self):
        client = self.app.test_client()
        self._setup_quiz(client, 5)
        with client.session_transaction() as sess:
            sess['quiz_index'] = 3

        client.post('/quiz/prev', follow_redirects=False)
        with client.session_transaction() as sess:
            self.assertEqual(sess.get('quiz_index'), 2)

    def test_quiz_prev_at_first_question_is_noop(self):
        client = self.app.test_client()
        self._setup_quiz(client, 5)
        with client.session_transaction() as sess:
            sess['quiz_index'] = 0

        client.post('/quiz/prev', follow_redirects=False)
        with client.session_transaction() as sess:
            self.assertEqual(sess.get('quiz_index'), 0, '首题时 prev 不应改变 quiz_index')

    def test_quiz_prev_redirects_with_from_prev_flag(self):
        """回退应带 from_prev=1 query 参数，便于前端听力题不自动播"""
        client = self.app.test_client()
        self._setup_quiz(client, 5)
        with client.session_transaction() as sess:
            sess['quiz_index'] = 2

        resp = client.post('/quiz/prev', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('from_prev=1', resp.location)

    def test_change_answer_after_prev(self):
        """回退后改答案：最终 quiz_answers 是覆盖后的值"""
        client = self.app.test_client()
        self._setup_quiz(client, 3)

        # 第 1 题选 'wrong_a'
        client.post('/quiz/answer', data={'answer': 'wrong_a'})
        # 第 2 题选 'wrong_b'
        client.post('/quiz/answer', data={'answer': 'wrong_b'})
        # 回到第 2 题
        client.post('/quiz/prev')
        # 改选 'ans1'（正确）
        client.post('/quiz/answer', data={'answer': 'ans1'})

        with client.session_transaction() as sess:
            answers = sess.get('quiz_answers', {})
            self.assertEqual(answers.get('1'), 'ans1', '回退改答案后应保留最新选择')
            self.assertEqual(answers.get('0'), 'wrong_a')


class TestQuizMaxReached(_BaseCase):

    def test_quiz_max_reached_does_not_regress(self):
        """前进到 idx=3 后回退到 idx=0，quiz_max_reached 应保留 4"""
        client = self.app.test_client()
        questions = [
            {'word_id': i + 1, 'english': f'w{i}', 'correct': 'a',
             'options': ['a', 'b', 'c', 'd']}
            for i in range(5)
        ]
        token = self.app_module._save_quiz_data({
            'questions': questions, 'word_ids': [1, 2, 3, 4, 5]
        })
        with client.session_transaction() as sess:
            sess['quiz_token'] = token
            sess['quiz_index'] = 3
            sess['quiz_answers'] = {}
            sess['quiz_mode'] = 'learn'
            sess['quiz_max_reached'] = 1
            sess['list_id'] = 1

        # 访问 question 触发 max_reached 更新
        client.get('/quiz/question')
        with client.session_transaction() as sess:
            self.assertEqual(sess.get('quiz_max_reached'), 4)

        # 回到第 1 题
        with client.session_transaction() as sess:
            sess['quiz_index'] = 0
        client.get('/quiz/question')
        with client.session_transaction() as sess:
            self.assertEqual(sess.get('quiz_max_reached'), 4, 'quiz_max_reached 不应倒退')


if __name__ == '__main__':
    unittest.main(verbosity=2)
