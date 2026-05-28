"""E2E 测试：同义词学习流"学完即测"闭环（add-synonym-learn-quiz）

覆盖：
  • 学完最后一张自动跳测验（而非直接 synonym_done）
  • learn_quiz 优先消费 pending_quiz_word_ids
  • 测验提交后 quiz_result 模板渲染同义词流按钮（synonym_flow=True）
  • study_log 写入时机：learn_synonym 在跳测验前写入，quiz 在通关后写入
  • 中途退出场景：learn_synonym 已写入、quiz 未写入
  • 词库 <4 个词时退回旧行为（不测验）
  • session 缺失时 synonym_done 走 fallback 不崩溃
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
        cls.db_mod = database
        cls.app.config['TESTING'] = True
        cls.app.config['SECRET_KEY'] = 'test'
        database.init_db()

    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(cls._tmp_db)
        except Exception:
            pass


class TestSynonymLearnQuizFlow(_BaseCase):
    """学完 → 跳测验 → 完成的端到端流"""

    def setUp(self):
        # 准备一个同义词词库（5 个词，全部带 synonyms，够 4 个干扰项门槛）
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM study_log")
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM word_lists")
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (1, 'syn_lib', 'synonym')")
        for i, (en, zh, syn) in enumerate([
            ('alpha', '甲', 'first letter'),
            ('beta', '乙', 'second letter'),
            ('gamma', '丙', 'third letter'),
            ('delta', '丁', 'fourth letter'),
            ('epsilon', '戊', 'fifth letter'),
        ], start=1):
            conn.execute(
                "INSERT INTO words (id, list_id, english, chinese, synonyms, status) "
                "VALUES (?, 1, ?, ?, ?, 'unmastered')",
                (i, en, zh, syn)
            )
        conn.commit()
        conn.close()

    def _start_synonym_session(self, client, word_ids):
        """直接在 session 里塞入同义词学习状态，绕过 setup 页面"""
        from datetime import datetime
        with client.session_transaction() as sess:
            sess['list_id'] = 1
            sess['list_picked'] = True
            sess['syn_queue'] = list(word_ids)
            sess['syn_total'] = len(word_ids)
            sess['syn_word_ids'] = list(word_ids)
            sess['syn_started_at'] = datetime.now().isoformat()
            sess['syn_list_id'] = 1

    def test_last_card_redirects_to_quiz_not_done(self):
        """学完最后一张：synonym/next 应跳 learn_quiz，而不是 synonym_done"""
        client = self.app.test_client()
        self._start_synonym_session(client, [1])  # 只有 1 张卡

        resp = client.post('/learn/synonym/next', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        # 跳转链应该 → /learn/quiz（learn_quiz 路由），再进一步 redirect 到 /quiz/question
        self.assertTrue(
            resp.location.endswith('/learn/quiz') or '/learn/quiz' in resp.location,
            f'应跳 /learn/quiz，实际 {resp.location}'
        )

    def test_learn_quiz_consumes_pending_word_ids(self):
        """learn_quiz 优先用 pending_quiz_word_ids 生成题目，不依赖 learn_session"""
        client = self.app.test_client()
        self._start_synonym_session(client, [1])

        # 走完整流程
        resp = client.post('/learn/synonym/next', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)

        # 接着访问 /learn/quiz，应该 redirect 到 /quiz/question（题目已生成）
        resp2 = client.get('/learn/quiz', follow_redirects=False)
        self.assertEqual(resp2.status_code, 302)
        self.assertIn('/quiz/question', resp2.location)

        # 验证 session 标记
        with client.session_transaction() as sess:
            self.assertTrue(sess.get('quiz_synonym_flow'), 'quiz_synonym_flow 应被标记')
            self.assertNotIn('pending_quiz_word_ids', sess, 'pending_quiz_word_ids 应被消费')
            self.assertEqual(sess.get('pending_quiz_return_to'), 'synonym_done')
            self.assertEqual(sess.get('quiz_mode'), 'learn')

    def test_learn_synonym_log_written_before_quiz(self):
        """跳测验前 learn_synonym 应已写入 study_log（避免中途退出丢统计）"""
        client = self.app.test_client()
        self._start_synonym_session(client, [1, 2, 3])

        # 学完前：study_log 为空
        conn = self.db_mod.get_db()
        count_before = conn.execute("SELECT COUNT(*) FROM study_log WHERE mode='learn_synonym'").fetchone()[0]
        conn.close()
        self.assertEqual(count_before, 0)

        # 模拟学完 3 张
        for _ in range(3):
            client.post('/learn/synonym/next')

        # 此时还没进测验，但 learn_synonym 应已写入
        conn = self.db_mod.get_db()
        rows = conn.execute(
            "SELECT word_ids, list_id FROM study_log WHERE mode='learn_synonym'"
        ).fetchall()
        conn.close()
        self.assertEqual(len(rows), 1)
        self.assertEqual(json.loads(rows[0]['word_ids']), [1, 2, 3])
        self.assertEqual(rows[0]['list_id'], 1)

    def test_full_flow_writes_both_logs(self):
        """完整通关流程：study_log 应有 learn_synonym + quiz 两条"""
        client = self.app.test_client()
        self._start_synonym_session(client, [1, 2])

        # 学完 2 张 → 跳测验
        for _ in range(2):
            client.post('/learn/synonym/next')
        # 进入测验
        client.get('/learn/quiz')

        # 全部答对（同义词模式选项是英文同义词；通过 quiz_data 取正确答案）
        from app import _load_quiz_data  # noqa
        with client.session_transaction() as sess:
            token = sess.get('quiz_token')
        quiz_data = self.app_module._load_quiz_data(token)
        questions = quiz_data['questions']

        for q in questions:
            client.post('/quiz/answer', data={'answer': q['correct']})

        # 提交
        resp = client.get('/quiz/submit')
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn('今日通关', body, '应展示通关页')
        # 同义词流的通关页文案
        self.assertIn('同义词', body)
        # 按钮指向 synonym_done
        self.assertIn('/learn/synonym/done', body)

        # study_log 应有两条
        conn = self.db_mod.get_db()
        modes = [r['mode'] for r in conn.execute("SELECT mode FROM study_log ORDER BY id").fetchall()]
        conn.close()
        self.assertEqual(sorted(modes), ['learn_synonym', 'quiz'])

    def test_synonym_done_skips_duplicate_log(self):
        """synonym_done 检测到 syn_logged 标记后不重复写 learn_synonym"""
        client = self.app.test_client()
        self._start_synonym_session(client, [1, 2])

        # 完整通关
        for _ in range(2):
            client.post('/learn/synonym/next')
        client.get('/learn/quiz')
        with client.session_transaction() as sess:
            token = sess.get('quiz_token')
        questions = self.app_module._load_quiz_data(token)['questions']
        for q in questions:
            client.post('/quiz/answer', data={'answer': q['correct']})
        client.get('/quiz/submit')

        # 此时访问 synonym_done 完成页
        resp = client.get('/learn/synonym/done')
        self.assertEqual(resp.status_code, 200)

        # learn_synonym 应仍只有 1 条（没被重复写）
        conn = self.db_mod.get_db()
        count = conn.execute("SELECT COUNT(*) FROM study_log WHERE mode='learn_synonym'").fetchone()[0]
        conn.close()
        self.assertEqual(count, 1, 'synonym_done 不应重复写 learn_synonym')

    def test_abandon_quiz_keeps_learn_synonym_log(self):
        """中途退出测验：learn_synonym 已写入、quiz 未写入"""
        client = self.app.test_client()
        self._start_synonym_session(client, [1, 2])

        # 学完进入测验
        for _ in range(2):
            client.post('/learn/synonym/next')
        client.get('/learn/quiz')

        # 不答题，直接放弃（点测验页面的"放弃测验"按钮即 synonym_abandon）
        client.post('/learn/synonym/abandon')

        # learn_synonym 应已写入；quiz 不应写入
        conn = self.db_mod.get_db()
        modes = [r['mode'] for r in conn.execute("SELECT mode FROM study_log").fetchall()]
        conn.close()
        self.assertEqual(modes, ['learn_synonym'])

    def test_small_library_skips_quiz(self):
        """词库 <4 个词时跳过测验，直接到 synonym_done（保持旧行为）"""
        # 重建一个只有 2 个词的词库
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM study_log")
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM word_lists")
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (1, 'tiny', 'synonym')")
        conn.execute("INSERT INTO words (id, list_id, english, chinese, synonyms, status) VALUES (1, 1, 'a', 'A', 'first', 'unmastered')")
        conn.execute("INSERT INTO words (id, list_id, english, chinese, synonyms, status) VALUES (2, 1, 'b', 'B', 'second', 'unmastered')")
        conn.commit()
        conn.close()

        client = self.app.test_client()
        self._start_synonym_session(client, [1, 2])

        # 学完第 1 张 → 继续 card
        client.post('/learn/synonym/next')
        # 学完最后 1 张 → 期望直接跳 synonym_done（词库太小，绕过测验）
        resp = client.post('/learn/synonym/next', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/learn/synonym/done', resp.location)

        # learn_synonym 应在 synonym_done 兜底写入
        # 跟进访问 synonym_done
        client.get('/learn/synonym/done')
        conn = self.db_mod.get_db()
        count = conn.execute("SELECT COUNT(*) FROM study_log WHERE mode='learn_synonym'").fetchone()[0]
        conn.close()
        self.assertEqual(count, 1)

    def test_synonym_done_no_session_does_not_crash(self):
        """session 完全空时访问 synonym_done 不应崩溃"""
        client = self.app.test_client()
        # 但需要至少一个 list 存在以便 get_current_list_id 不返回 None
        resp = client.get('/learn/synonym/done')
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn('学习完成', body)

        # 不应写入 study_log（word_ids 为空）
        conn = self.db_mod.get_db()
        count = conn.execute("SELECT COUNT(*) FROM study_log WHERE mode='learn_synonym'").fetchone()[0]
        conn.close()
        self.assertEqual(count, 0)


class TestSynonymPrevNavigation(_BaseCase):
    """同义词学习「上一张」导航"""

    def setUp(self):
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM study_log")
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM word_lists")
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (1, 'syn_lib', 'synonym')")
        for i, (en, zh, syn) in enumerate([
            ('alpha', '甲', 'first letter'),
            ('beta', '乙', 'second letter'),
            ('gamma', '丙', 'third letter'),
            ('delta', '丁', 'fourth letter'),
        ], start=1):
            conn.execute(
                "INSERT INTO words (id, list_id, english, chinese, synonyms, status) "
                "VALUES (?, 1, ?, ?, ?, 'unmastered')",
                (i, en, zh, syn)
            )
        conn.commit()
        conn.close()

    def _start(self, client, word_ids):
        from datetime import datetime
        with client.session_transaction() as sess:
            sess['list_id'] = 1
            sess['list_picked'] = True
            sess['syn_queue'] = list(word_ids)
            sess['syn_total'] = len(word_ids)
            sess['syn_index'] = 0
            sess['syn_word_ids'] = list(word_ids)
            sess['syn_started_at'] = datetime.now().isoformat()
            sess['syn_list_id'] = 1

    def test_first_card_prev_disabled(self):
        """首张卡：prev_available=False，按钮 disabled"""
        client = self.app.test_client()
        self._start(client, [1, 2, 3])
        resp = client.get('/learn/synonym/card')
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn('← 上一张', body)
        # 通过 prev_available JS 变量精确判断
        self.assertIn('const prevAvailable = false;', body)

    def test_second_card_prev_enabled(self):
        """next 一次后，prev 可用"""
        client = self.app.test_client()
        self._start(client, [1, 2, 3])
        client.post('/learn/synonym/next')
        resp = client.get('/learn/synonym/card')
        body = resp.get_data(as_text=True)
        self.assertIn('← 上一张', body)
        self.assertIn('const prevAvailable = true;', body)
        # 进度应该是 2 / 3
        self.assertIn('2 / 3', body)

    def test_prev_goes_back(self):
        """prev 应使游标 -1，回到上一张"""
        client = self.app.test_client()
        self._start(client, [1, 2, 3])
        client.post('/learn/synonym/next')  # idx=1
        client.post('/learn/synonym/next')  # idx=2
        with client.session_transaction() as sess:
            self.assertEqual(sess['syn_index'], 2)

        client.post('/learn/synonym/prev')
        with client.session_transaction() as sess:
            self.assertEqual(sess['syn_index'], 1)

    def test_prev_at_first_stays(self):
        """首张点 prev 不动（max(0, -1) = 0）"""
        client = self.app.test_client()
        self._start(client, [1, 2, 3])
        client.post('/learn/synonym/prev')
        with client.session_transaction() as sess:
            self.assertEqual(sess['syn_index'], 0)

    def test_last_card_next_triggers_quiz_path(self):
        """游标模型下，最后一张 next 仍触发跳测验"""
        client = self.app.test_client()
        self._start(client, [1, 2])
        client.post('/learn/synonym/next')  # idx=1（最后一张）
        resp = client.post('/learn/synonym/next', follow_redirects=False)
        # 4 词词库够测验门槛 → 跳 learn_quiz
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/learn/quiz', resp.location)


if __name__ == '__main__':
    unittest.main(verbosity=2)
