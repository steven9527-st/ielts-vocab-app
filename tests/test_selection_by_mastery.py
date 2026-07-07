"""测试 align-selection-by-mastery change：

覆盖：
  • 同义词学习只从 unmastered 词中选（跳过 mastered）
  • 同义词学习 setup 页：所有含同义词都掌握时的引导页
  • 测试模式只从 mastered 词中选
  • 测试模式 setup 页：mastered < 4 时的拦截
  • get_list_stats 新字段 unmastered_with_synonyms
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


class TestGetListStats(_BaseCase):
    """get_list_stats 新字段 unmastered_with_synonyms"""

    def setUp(self):
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM word_lists")
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (1, 'x', 'standard')")
        conn.commit()
        conn.close()

    def _add_word(self, wid, status, synonyms):
        conn = self.db_mod.get_db()
        conn.execute(
            "INSERT INTO words (id, list_id, english, chinese, synonyms, status) "
            "VALUES (?, 1, ?, ?, ?, ?)",
            (wid, f'w{wid}', f'z{wid}', synonyms or '', status)
        )
        conn.commit()
        conn.close()

    def test_new_field_computed(self):
        # 4 类词各造 1 条：
        # A: mastered + has synonym
        self._add_word(1, 'mastered', 'syn1')
        # B: mastered + no synonym
        self._add_word(2, 'mastered', '')
        # C: unmastered + has synonym
        self._add_word(3, 'unmastered', 'syn3')
        # D: unmastered + no synonym
        self._add_word(4, 'unmastered', '')

        stats = self.app_module.get_list_stats(1)
        self.assertEqual(stats['total'], 4)
        self.assertEqual(stats['mastered'], 2)
        self.assertEqual(stats['unmastered'], 2)
        self.assertEqual(stats['with_synonyms'], 2)
        self.assertEqual(stats['unmastered_with_synonyms'], 1, '只有词 3 是 unmastered 且有同义词')


class TestSynonymSelectionByMastery(_BaseCase):
    """同义词学习只从未掌握词中选"""

    def setUp(self):
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM word_lists")
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (1, 'syn', 'synonym')")
        # 20 词全部含同义词，前 5 个 mastered
        for i in range(1, 21):
            status = 'mastered' if i <= 5 else 'unmastered'
            conn.execute(
                "INSERT INTO words (id, list_id, english, chinese, synonyms, status) "
                "VALUES (?, 1, ?, ?, ?, ?)",
                (i, f'w{i}', f'z{i}', f'syn{i}', status)
            )
        conn.commit()
        conn.close()

    def test_only_unmastered_selected(self):
        """请求学 15 个 → 只从 15 个 unmastered 中抽"""
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['list_id'] = 1
            sess['list_picked'] = True

        resp = client.post('/learn/synonym/start', data={'n': 15}, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)

        with client.session_transaction() as sess:
            picked = sess.get('syn_word_ids') or []

        self.assertEqual(len(picked), 15)
        # 全部应是 unmastered（id >= 6）
        for wid in picked:
            self.assertGreaterEqual(wid, 6, f'不应抽中 mastered 词 id={wid}')

    def test_shortage_returns_actual_count(self):
        """请求 30 但只有 15 未掌握 → 抽 15"""
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['list_id'] = 1
            sess['list_picked'] = True

        resp = client.post('/learn/synonym/start', data={'n': 30})
        with client.session_transaction() as sess:
            picked = sess.get('syn_word_ids') or []
        self.assertEqual(len(picked), 15)

    def test_all_mastered_setup_shows_guide(self):
        """所有含同义词都掌握 → setup 页展示引导"""
        # 把剩下 15 个也标 mastered
        conn = self.db_mod.get_db()
        conn.execute("UPDATE words SET status='mastered' WHERE list_id=1")
        conn.commit()
        conn.close()

        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['list_id'] = 1
            sess['list_picked'] = True

        resp = client.get('/learn/synonym/setup')
        body = resp.get_data(as_text=True)
        self.assertIn('都已掌握了', body)
        self.assertIn('去测试', body)
        self.assertNotIn('开始学习', body)


class TestTestSelectionByMastery(_BaseCase):
    """测试模式只从 mastered 词中选"""

    def setUp(self):
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM word_lists")
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (1, 'std', 'standard')")
        # 30 词，12 mastered / 18 unmastered
        for i in range(1, 31):
            status = 'mastered' if i <= 12 else 'unmastered'
            conn.execute(
                "INSERT INTO words (id, list_id, english, chinese, status) "
                "VALUES (?, 1, ?, ?, ?)",
                (i, f'w{i}', f'z{i}', status)
            )
        conn.commit()
        conn.close()

    def test_only_mastered_in_questions(self):
        """测 10 题：题目 word_id 全部对应 mastered 词"""
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['list_id'] = 1
            sess['list_picked'] = True

        resp = client.post('/test/start', data={'m': 10, 'test_type': 'text'}, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)

        with client.session_transaction() as sess:
            token = sess.get('quiz_token')
        quiz_data = self.app_module._load_quiz_data(token)
        question_wids = [q['word_id'] for q in quiz_data['questions']]

        self.assertEqual(len(question_wids), 10)
        for wid in question_wids:
            self.assertLessEqual(wid, 12, f'题目 word_id={wid} 应对应 mastered 词 (id<=12)')

    def test_start_rejects_when_mastered_below_4(self):
        """如果 mastered < 4，直接进入 start 也应被拒绝（防御性双层保护）"""
        conn = self.db_mod.get_db()
        # 把 mastered 缩到 3 个
        conn.execute("UPDATE words SET status='unmastered' WHERE id > 3")
        conn.commit()
        conn.close()

        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['list_id'] = 1
            sess['list_picked'] = True

        resp = client.post('/test/start', data={'m': 3, 'test_type': 'text'})
        body = resp.get_data(as_text=True)
        self.assertIn('已掌握词不足', body)


class TestTestSetupInterception(_BaseCase):
    """test_setup 拦截页面"""

    def setUp(self):
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM word_lists")
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (1, 'std', 'standard')")
        conn.commit()
        conn.close()

    def _seed(self, mastered_count, unmastered_count):
        conn = self.db_mod.get_db()
        for i in range(1, mastered_count + 1):
            conn.execute(
                "INSERT INTO words (id, list_id, english, chinese, status) "
                "VALUES (?, 1, ?, ?, 'mastered')",
                (i, f'm{i}', f'zm{i}')
            )
        for j in range(mastered_count + 1, mastered_count + unmastered_count + 1):
            conn.execute(
                "INSERT INTO words (id, list_id, english, chinese, status) "
                "VALUES (?, 1, ?, ?, 'unmastered')",
                (j, f'u{j}', f'zu{j}')
            )
        conn.commit()
        conn.close()

    def test_mastered_below_4_shows_guide(self):
        """mastered=2 → 展示引导页，无开始按钮"""
        self._seed(mastered_count=2, unmastered_count=20)
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['list_id'] = 1
            sess['list_picked'] = True

        resp = client.get('/test/setup')
        body = resp.get_data(as_text=True)
        self.assertIn('已掌握词不足 4 个', body)
        self.assertIn('去学习', body)
        # 没有测试类型/题数输入表单
        self.assertNotIn('id="startBtn"', body)

    def test_mastered_ge_4_normal_form(self):
        """mastered=10 → 正常渲染，subtitle 显示已掌握"""
        self._seed(mastered_count=10, unmastered_count=5)
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['list_id'] = 1
            sess['list_picked'] = True

        resp = client.get('/test/setup')
        body = resp.get_data(as_text=True)
        self.assertIn('从已掌握的 10 个单词中随机出题', body)
        self.assertIn('id="startBtn"', body)
        # max 属性用 mastered 数
        self.assertIn('max="10"', body)


if __name__ == '__main__':
    unittest.main(verbosity=2)
