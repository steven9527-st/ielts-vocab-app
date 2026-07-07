"""测试 add-fully-mastered-tier change：

覆盖：
  • get_list_stats 三态计数（mastered 口径不含 fully_mastered，新增 fully_mastered 字段）
  • test_start 只从 mastered 选（fully_mastered 天然被排除）
  • POST /mastery/promote 正常升级 + 跳过非 mastered + 空列表
  • PATCH /api/word/<id> 支持 fully_mastered
  • quiz_result / test_result 展示单词列表 + checkbox
  • index 首页 4 张 metric 卡（含完全掌握）
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


class TestGetListStatsTriState(_BaseCase):
    """get_list_stats 三态计数"""

    def setUp(self):
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM word_lists")
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (1, 'x', 'standard')")
        # 50 unmastered / 30 mastered / 20 fully_mastered
        wid = 1
        for status, n in [('unmastered', 50), ('mastered', 30), ('fully_mastered', 20)]:
            for _ in range(n):
                conn.execute(
                    "INSERT INTO words (id, list_id, english, chinese, status) VALUES (?,1,?,?,?)",
                    (wid, f'w{wid}', f'z{wid}', status)
                )
                wid += 1
        conn.commit()
        conn.close()

    def test_three_state_counts(self):
        stats = self.app_module.get_list_stats(1)
        self.assertEqual(stats['total'], 100)
        self.assertEqual(stats['unmastered'], 50)
        self.assertEqual(stats['mastered'], 30)
        self.assertEqual(stats['fully_mastered'], 20)
        # 三者之和 == total
        self.assertEqual(stats['unmastered'] + stats['mastered'] + stats['fully_mastered'], 100)


class TestTestStartExcludesFullyMastered(_BaseCase):
    """test_start 选词只用 mastered，fully_mastered 被排除"""

    def setUp(self):
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM word_lists")
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (1, 'x', 'standard')")
        # 5 mastered (id 1-5) / 3 fully_mastered (id 6-8)
        for i in range(1, 6):
            conn.execute("INSERT INTO words (id, list_id, english, chinese, status) VALUES (?,1,?,?,'mastered')",
                         (i, f'm{i}', f'zm{i}'))
        for i in range(6, 9):
            conn.execute("INSERT INTO words (id, list_id, english, chinese, status) VALUES (?,1,?,?,'fully_mastered')",
                         (i, f'f{i}', f'zf{i}'))
        conn.commit()
        conn.close()

    def test_only_mastered_selected(self):
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['list_id'] = 1
            sess['list_picked'] = True

        resp = client.post('/test/start', data={'m': 5, 'test_type': 'text'}, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)

        with client.session_transaction() as sess:
            token = sess.get('quiz_token')
        quiz_data = self.app_module._load_quiz_data(token)
        wids = [q['word_id'] for q in quiz_data['questions']]
        self.assertEqual(len(wids), 5)
        for wid in wids:
            self.assertLessEqual(wid, 5, f'word_id={wid} 应对应 mastered 词 (id≤5)')


class TestMasteryPromote(_BaseCase):
    """POST /mastery/promote 端点"""

    def setUp(self):
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM word_lists")
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (1, 'x', 'standard')")
        for i in range(1, 6):
            conn.execute("INSERT INTO words (id, list_id, english, chinese, status) VALUES (?,1,?,?,'mastered')",
                         (i, f'w{i}', f'z{i}'))
        # 词 5 是 unmastered
        conn.execute("UPDATE words SET status='unmastered' WHERE id=5")
        conn.commit()
        conn.close()

    def test_promote_normal(self):
        client = self.app.test_client()
        resp = client.post('/mastery/promote',
                           json={'word_ids': [1, 2, 3]},
                           content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['promoted'], 3)

        conn = self.db_mod.get_db()
        rows = conn.execute("SELECT id, status FROM words WHERE id IN (1,2,3) ORDER BY id").fetchall()
        conn.close()
        for r in rows:
            self.assertEqual(r['status'], 'fully_mastered')

    def test_promote_skips_non_mastered(self):
        """word_ids 里混入 unmastered 词（id=5），应只升级 mastered 词"""
        client = self.app.test_client()
        resp = client.post('/mastery/promote',
                           json={'word_ids': [1, 2, 5]},
                           content_type='application/json')
        data = resp.get_json()
        self.assertEqual(data['promoted'], 2, '词 5 是 unmastered 应被跳过')

        conn = self.db_mod.get_db()
        r5 = conn.execute("SELECT status FROM words WHERE id=5").fetchone()
        conn.close()
        self.assertEqual(r5['status'], 'unmastered', '词 5 status 应保持 unmastered')

    def test_promote_empty_list(self):
        client = self.app.test_client()
        resp = client.post('/mastery/promote',
                           json={'word_ids': []},
                           content_type='application/json')
        data = resp.get_json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['promoted'], 0)

    def test_promote_invalid_type(self):
        client = self.app.test_client()
        resp = client.post('/mastery/promote',
                           json={'word_ids': 'not a list'},
                           content_type='application/json')
        self.assertEqual(resp.status_code, 400)

    def test_promote_idempotent(self):
        """已经是 fully_mastered 的词再次 promote 不出错，promoted=0"""
        client = self.app.test_client()
        client.post('/mastery/promote', json={'word_ids': [1]}, content_type='application/json')
        resp = client.post('/mastery/promote', json={'word_ids': [1]}, content_type='application/json')
        data = resp.get_json()
        self.assertEqual(data['promoted'], 0, '已 fully_mastered 的词第二次 promote 应为 0')


class TestPatchWordAcceptsFullyMastered(_BaseCase):
    """PATCH /api/word/<id> 支持 fully_mastered 状态"""

    def setUp(self):
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM word_lists")
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (1, 'x', 'standard')")
        conn.execute("INSERT INTO words (id, list_id, english, chinese, status) VALUES (10, 1, 'a', 'A', 'mastered')")
        conn.commit()
        conn.close()

    def test_patch_to_fully_mastered(self):
        client = self.app.test_client()
        resp = client.put('/api/word/10',
                          json={'status': 'fully_mastered'},
                          content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        conn = self.db_mod.get_db()
        r = conn.execute("SELECT status FROM words WHERE id=10").fetchone()
        conn.close()
        self.assertEqual(r['status'], 'fully_mastered')


class TestIndexShowsFourMetrics(_BaseCase):
    """首页展示 4 张 metric 卡"""

    def setUp(self):
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM word_lists")
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (1, 'x', 'standard')")
        # 2 unmastered / 3 mastered / 4 fully_mastered
        wid = 1
        for status, n in [('unmastered', 2), ('mastered', 3), ('fully_mastered', 4)]:
            for _ in range(n):
                conn.execute("INSERT INTO words (id, list_id, english, chinese, status) VALUES (?,1,?,?,?)",
                             (wid, f'w{wid}', f'z{wid}', status))
                wid += 1
        conn.commit()
        conn.close()

    def test_index_shows_four_cards(self):
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['list_id'] = 1
            sess['list_picked'] = True

        resp = client.get('/')
        body = resp.get_data(as_text=True)
        self.assertIn('词库总数', body)
        self.assertIn('已掌握', body)
        self.assertIn('完全掌握', body)
        self.assertIn('未掌握', body)
        # metric-grid--4 class 应出现
        self.assertIn('metric-grid--4', body)
        # 数字精确匹配
        self.assertIn('>9<', body)  # total
        self.assertIn('>3<', body)  # mastered
        self.assertIn('>4<', body)  # fully_mastered
        self.assertIn('>2<', body)  # unmastered


class TestResultPageShowsPromoteSection(_BaseCase):
    """结果页展示单词列表 + checkbox"""

    def setUp(self):
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM word_lists")
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (1, 'x', 'standard')")
        for i in range(1, 11):
            conn.execute("INSERT INTO words (id, list_id, english, chinese, status) VALUES (?,1,?,?,'mastered')",
                         (i, f'word{i}', f'释义{i}'))
        conn.commit()
        conn.close()

    def test_test_result_shows_promote_section(self):
        """完成一次 test 测试后，结果页应含 promote-section"""
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['list_id'] = 1
            sess['list_picked'] = True

        # 启动测试
        client.post('/test/start', data={'m': 5, 'test_type': 'text'})
        with client.session_transaction() as sess:
            token = sess.get('quiz_token')
        quiz_data = self.app_module._load_quiz_data(token)
        # 全部答对
        for q in quiz_data['questions']:
            client.post('/quiz/answer', data={'answer': q['correct']})
        resp = client.get('/quiz/submit')
        body = resp.get_data(as_text=True)

        # 应出现完全掌握勾选区
        self.assertIn('promote-section', body)
        self.assertIn('promote-checkbox', body)
        self.assertIn('加入完全掌握', body)


if __name__ == '__main__':
    unittest.main(verbosity=2)
