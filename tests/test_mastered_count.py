"""测试 fix-mastered-count change：

覆盖：
  • 20 词学习含 2 词错题重做，通关后 mastered 计数应 +20（而非 +2）
  • 首轮零错误通关（无重做），行为一致
  • 同义词流通关也 UPDATE mastered
  • today_mastered_count 多会话去重合并
  • today_mastered_count 跨词库隔离
  • 历史迁移 _migrate_synonym_mastered 幂等 + 保护 mastered
  • 首页模板：completed_today=True 时显示「今日新增掌握 N 个」
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


class TestLearnQuizMasteredCount(_BaseCase):
    """通关时 mastered 与 total 使用原始 word_ids 全集"""

    def setUp(self):
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM study_log")
        conn.execute("DELETE FROM learn_session")
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM word_lists")
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (1, 'std', 'standard')")
        for i in range(1, 21):  # 20 个词
            conn.execute(
                "INSERT INTO words (id, list_id, english, chinese, status) "
                "VALUES (?, 1, ?, ?, 'unmastered')",
                (i, f'word{i}', f'释义{i}')
            )
        conn.commit()
        conn.close()

    def _start_learn_session(self, client, word_ids):
        """直接塞入 learn_session 记录 + 建 quiz session"""
        conn = self.db_mod.get_db()
        cursor = conn.execute(
            "INSERT INTO learn_session (list_id, date, word_ids, status) "
            "VALUES (1, DATE('now'), ?, 'in_progress')",
            (json.dumps(word_ids),)
        )
        sess_id = cursor.lastrowid
        conn.commit()
        conn.close()

        with client.session_transaction() as sess:
            sess['list_id'] = 1
            sess['list_picked'] = True
            sess['learn_session_id'] = sess_id
            sess['quiz_original_word_ids'] = list(word_ids)

        return sess_id

    def test_full_20_words_no_retry_masters_all(self):
        """20 词首轮全对通关：全部 20 个 UPDATE mastered"""
        client = self.app.test_client()
        word_ids = list(range(1, 21))
        self._start_learn_session(client, word_ids)

        # 走 learn_quiz 生成题目
        client.get('/learn/quiz')

        # 全部答对
        with client.session_transaction() as sess:
            token = sess['quiz_token']
        quiz_data = self.app_module._load_quiz_data(token)
        questions = quiz_data['questions']
        for q in questions:
            client.post('/quiz/answer', data={'answer': q['correct']})

        resp = client.get('/quiz/submit')
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn('今日通关', body)
        self.assertIn('本次学习的 20 个单词已全部标记为已掌握', body)

        # DB 验证：20 个词全部 mastered
        conn = self.db_mod.get_db()
        mastered = conn.execute(
            "SELECT COUNT(*) FROM words WHERE list_id=1 AND status='mastered'"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(mastered, 20)

    def test_20_words_with_retry_still_masters_all_20(self):
        """20 词学习含 2 词错题重做，通关 mastered 应 +20 而非 +2"""
        client = self.app.test_client()
        word_ids = list(range(1, 21))
        self._start_learn_session(client, word_ids)

        client.get('/learn/quiz')
        with client.session_transaction() as sess:
            token = sess['quiz_token']
        quiz_data = self.app_module._load_quiz_data(token)
        questions = quiz_data['questions']

        # 首轮：故意答错 2 题
        wrong_word_ids = []
        for i, q in enumerate(questions):
            if i < 2:
                # 找一个非正确答案
                wrong_opt = next((o for o in q['options'] if o != q['correct']), q['correct'])
                client.post('/quiz/answer', data={'answer': wrong_opt})
                wrong_word_ids.append(q['word_id'])
            else:
                client.post('/quiz/answer', data={'answer': q['correct']})

        # 首轮提交
        resp1 = client.get('/quiz/submit')
        body1 = resp1.get_data(as_text=True)
        self.assertIn('还有 2 题需要重做', body1)

        # 触发 retry
        wrong_items = [{'word_id': wid} for wid in wrong_word_ids]
        resp_retry = client.post('/quiz/retry',
                                 json={'wrong_items': wrong_items},
                                 content_type='application/json')
        self.assertEqual(resp_retry.status_code, 200)

        # 重做：全部答对
        with client.session_transaction() as sess:
            token2 = sess['quiz_token']
        quiz_data2 = self.app_module._load_quiz_data(token2)
        for q in quiz_data2['questions']:
            client.post('/quiz/answer', data={'answer': q['correct']})

        # 再次提交，通关
        resp2 = client.get('/quiz/submit')
        body2 = resp2.get_data(as_text=True)
        self.assertIn('今日通关', body2)
        # 关键断言：显示 20 而不是 2
        self.assertIn('本次学习的 20 个单词已全部标记为已掌握', body2)
        self.assertNotIn('本次学习的 2 个', body2)

        # DB 验证：20 个词全部 mastered
        conn = self.db_mod.get_db()
        mastered = conn.execute(
            "SELECT COUNT(*) FROM words WHERE list_id=1 AND status='mastered'"
        ).fetchone()[0]
        # study_log 记录的 word_ids 长度也应是 20
        row = conn.execute(
            "SELECT word_ids FROM study_log WHERE mode='learn' AND accuracy=1.0"
        ).fetchone()
        conn.close()
        self.assertEqual(mastered, 20)
        logged_ids = json.loads(row['word_ids'])
        self.assertEqual(len(logged_ids), 20)


class TestSynonymFlowMastered(_BaseCase):
    """同义词流通关也标 mastered"""

    def setUp(self):
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM study_log")
        conn.execute("DELETE FROM learn_session")
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM word_lists")
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (1, 'syn', 'synonym')")
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

    def test_synonym_flow_masters_all_words(self):
        """同义词流学 5 词并通关 → 5 个词都 status='mastered'"""
        from datetime import datetime
        client = self.app.test_client()

        # 塞入同义词学习 session（模拟已学完最后一张）
        with client.session_transaction() as sess:
            sess['list_id'] = 1
            sess['list_picked'] = True
            sess['syn_word_ids'] = [1, 2, 3, 4, 5]
            sess['syn_total'] = 5
            sess['syn_index'] = 5  # 已学完
            sess['syn_list_id'] = 1
            sess['syn_started_at'] = datetime.now().isoformat()

        # 触发 synonym_next 学完最后一张 → 跳 learn_quiz
        # 直接调 card（queue 空触发进测验）
        resp = client.get('/learn/synonym/card', follow_redirects=False)
        # → 302 到 /learn/quiz
        self.assertEqual(resp.status_code, 302)

        # 进入测验
        client.get('/learn/quiz')
        with client.session_transaction() as sess:
            token = sess['quiz_token']
            self.assertTrue(sess.get('quiz_synonym_flow'))

        # 全部答对
        quiz_data = self.app_module._load_quiz_data(token)
        for q in quiz_data['questions']:
            client.post('/quiz/answer', data={'answer': q['correct']})

        resp = client.get('/quiz/submit')
        body = resp.get_data(as_text=True)
        self.assertIn('本次共测验了 5 个同义词', body)

        # DB：5 个词全部 mastered（修 bug 核心）
        conn = self.db_mod.get_db()
        mastered = conn.execute(
            "SELECT COUNT(*) FROM words WHERE list_id=1 AND status='mastered'"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(mastered, 5, '同义词流通关后应把 5 个词都标为 mastered')


class TestTodayMasteredCount(_BaseCase):
    """today_mastered_count 辅助函数"""

    def setUp(self):
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM study_log")
        conn.execute("DELETE FROM word_lists")
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (1, 'a', 'standard')")
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (2, 'b', 'standard')")
        conn.commit()
        conn.close()

    def _insert_log(self, list_id, mode, word_ids, accuracy=1.0, date_str=None):
        from datetime import date
        if date_str is None:
            date_str = str(date.today())
        conn = self.db_mod.get_db()
        conn.execute(
            "INSERT INTO study_log (list_id, date, mode, word_ids, accuracy) VALUES (?,?,?,?,?)",
            (list_id, date_str, mode, json.dumps(word_ids), accuracy)
        )
        conn.commit()
        conn.close()

    def test_no_records_returns_zero(self):
        self.assertEqual(self.app_module.today_mastered_count(1), 0)

    def test_single_session_counts_all(self):
        self._insert_log(1, 'learn', list(range(1, 21)))
        self.assertEqual(self.app_module.today_mastered_count(1), 20)

    def test_multi_session_dedupe(self):
        """A: learn 20 词, B: learn_synonym 8 词, C: learn_synonym 5 词含 2 个与 A 重叠 → 31"""
        self._insert_log(1, 'learn', list(range(1, 21)))              # 1-20
        self._insert_log(1, 'learn_synonym', list(range(21, 29)))     # 21-28
        self._insert_log(1, 'learn_synonym', [19, 20, 29, 30, 31])    # 19,20 重叠
        self.assertEqual(self.app_module.today_mastered_count(1), 31)

    def test_cross_list_isolation(self):
        """词库 1 学 10 词、词库 2 学 5 词 → 词库 1 只算 10"""
        self._insert_log(1, 'learn', list(range(1, 11)))
        self._insert_log(2, 'learn', list(range(101, 106)))
        self.assertEqual(self.app_module.today_mastered_count(1), 10)
        self.assertEqual(self.app_module.today_mastered_count(2), 5)

    def test_ignores_non_learn_modes(self):
        """test_text / quiz 模式的记录不计入"""
        self._insert_log(1, 'test_text', list(range(1, 11)))
        self._insert_log(1, 'quiz', list(range(11, 21)))
        self.assertEqual(self.app_module.today_mastered_count(1), 0)

    def test_ignores_non_perfect_accuracy(self):
        """accuracy < 1.0 的记录不计入"""
        self._insert_log(1, 'learn', list(range(1, 11)), accuracy=0.9)
        self.assertEqual(self.app_module.today_mastered_count(1), 0)

    def test_ignores_other_days(self):
        """昨天的记录不计入"""
        self._insert_log(1, 'learn', list(range(1, 11)), date_str='2025-01-01')
        self.assertEqual(self.app_module.today_mastered_count(1), 0)


class TestHistoricalMigration(_BaseCase):
    """_migrate_synonym_mastered 迁移函数"""

    def setUp(self):
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM study_log")
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM word_lists")
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (1, 'syn', 'synonym')")
        for i in range(1, 11):
            conn.execute(
                "INSERT INTO words (id, list_id, english, chinese, status) "
                "VALUES (?, 1, ?, ?, 'unmastered')",
                (i, f'w{i}', f'z{i}')
            )
        conn.commit()
        conn.close()

    def _log_synonym(self, word_ids, accuracy=1.0):
        from datetime import date
        conn = self.db_mod.get_db()
        conn.execute(
            "INSERT INTO study_log (list_id, date, mode, word_ids, accuracy) VALUES (1, ?, 'learn_synonym', ?, ?)",
            (str(date.today()), json.dumps(word_ids), accuracy)
        )
        conn.commit()
        conn.close()

    def test_migration_upgrades_unmastered(self):
        """learn_synonym 通关记录里的词：unmastered → mastered"""
        self._log_synonym([1, 2, 3])
        self._log_synonym([4, 5])

        conn = self.db_mod.get_db()
        self.db_mod._migrate_synonym_mastered(conn)
        conn.close()

        conn = self.db_mod.get_db()
        mastered_ids = [r[0] for r in conn.execute(
            "SELECT id FROM words WHERE status='mastered' ORDER BY id"
        ).fetchall()]
        conn.close()
        self.assertEqual(mastered_ids, [1, 2, 3, 4, 5])

    def test_migration_skips_non_perfect(self):
        """accuracy<1.0 的记录不参与"""
        self._log_synonym([1, 2, 3], accuracy=0.5)
        conn = self.db_mod.get_db()
        self.db_mod._migrate_synonym_mastered(conn)
        conn.close()

        conn = self.db_mod.get_db()
        mastered = conn.execute(
            "SELECT COUNT(*) FROM words WHERE status='mastered'"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(mastered, 0)

    def test_migration_idempotent(self):
        """多次执行结果一致，不出错"""
        self._log_synonym([1, 2, 3])
        conn = self.db_mod.get_db()
        self.db_mod._migrate_synonym_mastered(conn)
        self.db_mod._migrate_synonym_mastered(conn)
        self.db_mod._migrate_synonym_mastered(conn)
        conn.close()

        conn = self.db_mod.get_db()
        mastered = conn.execute(
            "SELECT COUNT(*) FROM words WHERE status='mastered'"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(mastered, 3)

    def test_migration_no_records_safe(self):
        """study_log 无记录时不出错"""
        conn = self.db_mod.get_db()
        self.db_mod._migrate_synonym_mastered(conn)
        conn.close()

        conn = self.db_mod.get_db()
        mastered = conn.execute(
            "SELECT COUNT(*) FROM words WHERE status='mastered'"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(mastered, 0)


class TestIndexTemplate(_BaseCase):
    """首页模板：显示今日新增掌握"""

    def setUp(self):
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM study_log")
        conn.execute("DELETE FROM word_lists")
        conn.execute("DELETE FROM words")
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (1, 'std', 'standard')")
        for i in range(1, 11):
            conn.execute(
                "INSERT INTO words (id, list_id, english, chinese, status) "
                "VALUES (?, 1, ?, ?, 'unmastered')",
                (i, f'w{i}', f'z{i}')
            )
        conn.commit()
        conn.close()

    def test_shows_today_mastered_when_completed(self):
        from datetime import date
        # 制造今日通关记录
        conn = self.db_mod.get_db()
        conn.execute(
            "INSERT INTO study_log (list_id, date, mode, word_ids, accuracy) "
            "VALUES (1, ?, 'learn', ?, 1.0)",
            (str(date.today()), json.dumps(list(range(1, 8))))
        )
        conn.commit()
        conn.close()

        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['list_id'] = 1
            sess['list_picked'] = True

        resp = client.get('/')
        body = resp.get_data(as_text=True)
        self.assertIn('今日已通关', body)
        self.assertIn('今日新增掌握', body)
        self.assertIn('>7</strong>', body)

    def test_hides_today_mastered_when_not_completed(self):
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['list_id'] = 1
            sess['list_picked'] = True
        resp = client.get('/')
        body = resp.get_data(as_text=True)
        self.assertNotIn('今日已通关', body)
        self.assertNotIn('今日新增掌握', body)


if __name__ == '__main__':
    unittest.main(verbosity=2)
