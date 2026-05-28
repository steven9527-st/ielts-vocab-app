"""单元测试：首页学习按钮按词库 type 智能分发（unify-learn-entry-by-list-type）

覆盖：
  • standard 词库 → 「开始学习」指向 /learn/setup
  • synonym 词库 → 「开始学习」指向 /learn/synonym/setup
  • 独立「同义词学习」按钮已删除
  • active_syn_session 检测 → 显示「继续上次学习」
  • synonym_done 写入 study_log（mode='learn_synonym'）
  • calc_streak / today_completed 包含 learn_synonym
  • syn_started_at 缺失时 duration=0 不阻塞
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta

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
        database.init_db()

    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(cls._tmp_db)
        except Exception:
            pass

    def _reset_db(self):
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM study_log")
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM word_lists")
        conn.commit()
        conn.close()

    def _create_list(self, list_id, name, type_value, with_words=True):
        conn = self.db_mod.get_db()
        conn.execute(
            "INSERT INTO word_lists (id, name, type) VALUES (?, ?, ?)",
            (list_id, name, type_value)
        )
        if with_words:
            for i in range(5):
                conn.execute(
                    "INSERT INTO words (list_id, english, chinese, synonyms, status) VALUES (?, ?, ?, ?, 'unmastered')",
                    (list_id, f'word_{list_id}_{i}', f'释义_{i}',
                     f'syn_{i}' if type_value == 'synonym' else '')
                )
        conn.commit()
        conn.close()


class TestIndexDispatch(_BaseCase):

    def setUp(self):
        self._reset_db()

    def test_standard_list_index_points_to_learn_setup(self):
        self._create_list(1, 'std_lib', 'standard')
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['list_id'] = 1
            sess['list_picked'] = True
        resp = client.get('/')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn('href="/learn/setup"', html, '标准词库应指向 /learn/setup')
        # 「开始学习」按钮的链接不应是同义词路径
        # 用更精确判断：标准词库的「开始学习」按钮链接不应是 synonym_setup
        # 因为可能整个页面其他地方提到过该 URL（虽然现在已删按钮，再保险）

    def test_synonym_list_index_points_to_synonym_setup(self):
        self._create_list(2, 'syn_lib', 'synonym')
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['list_id'] = 2
            sess['list_picked'] = True
        resp = client.get('/')
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn('href="/learn/synonym/setup"', html, '同义词词库应指向 /learn/synonym/setup')

    def test_synonym_list_does_not_show_standalone_synonym_button(self):
        """删除独立「同义词学习」按钮——验证 HTML 里没有形如旁注 `(N)` 的同义词按钮"""
        self._create_list(3, 'syn_lib2', 'synonym')
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['list_id'] = 3
            sess['list_picked'] = True
        resp = client.get('/')
        html = resp.get_data(as_text=True)
        # 旧按钮带 "同义词学习" 文案 + "(N)" 计数，删除后这种独立按钮不应存在
        # 「开始学习」按钮链接到同义词 setup 是允许的
        # 旧独立按钮的特征 class 标识 + (N) 计数小标签
        self.assertNotIn('同义词学习', html, '独立「同义词学习」按钮应已删除')


class TestActiveSynSessionDetection(_BaseCase):

    def setUp(self):
        self._reset_db()
        self._create_list(1, 'syn_lib', 'synonym')

    def test_active_syn_session_shows_continue_button(self):
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['list_id'] = 1
            sess['list_picked'] = True
            sess['syn_queue'] = [1, 2, 3]
            sess['syn_total'] = 3
        resp = client.get('/')
        html = resp.get_data(as_text=True)
        self.assertIn('继续上次学习', html, '同义词词库有 syn_queue 进度时应显示继续按钮')

    def test_no_syn_queue_no_continue_button(self):
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['list_id'] = 1
            sess['list_picked'] = True
            # 不设置 syn_queue
        resp = client.get('/')
        html = resp.get_data(as_text=True)
        self.assertNotIn('继续上次学习', html, '无进度时不应显示继续按钮')


class TestSynonymDoneWritesStudyLog(_BaseCase):

    def setUp(self):
        self._reset_db()
        self._create_list(1, 'syn_lib', 'synonym')

    def test_synonym_done_writes_study_log(self):
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['list_id'] = 1
            sess['list_picked'] = True
            sess['syn_total'] = 3
            sess['syn_word_ids'] = [1, 2, 3]
            sess['syn_started_at'] = '2026-05-28T10:00:00'
            sess['syn_list_id'] = 1
            sess['syn_queue'] = []  # 已全部完成
        resp = client.get('/learn/synonym/done')
        self.assertEqual(resp.status_code, 200)

        # 验证 study_log 写入
        conn = self.db_mod.get_db()
        rows = conn.execute(
            "SELECT mode, accuracy, list_id, word_ids FROM study_log WHERE mode='learn_synonym'"
        ).fetchall()
        conn.close()
        self.assertEqual(len(rows), 1, '应写入一条 mode=learn_synonym 的 study_log')
        self.assertEqual(rows[0]['accuracy'], 1.0)
        self.assertEqual(rows[0]['list_id'], 1)
        self.assertEqual(json.loads(rows[0]['word_ids']), [1, 2, 3])

    def test_synonym_done_without_started_at_writes_duration_0(self):
        """syn_started_at 缺失时 duration=0，仍正常写入"""
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['list_id'] = 1
            sess['list_picked'] = True
            sess['syn_total'] = 2
            sess['syn_word_ids'] = [1, 2]
            sess['syn_list_id'] = 1
            sess['syn_queue'] = []
            # 不设置 syn_started_at
        client.get('/learn/synonym/done')
        conn = self.db_mod.get_db()
        row = conn.execute(
            "SELECT duration_s FROM study_log WHERE mode='learn_synonym'"
        ).fetchone()
        conn.close()
        self.assertEqual(row['duration_s'], 0, '缺 syn_started_at 时 duration_s 应为 0')


class TestStreakAndCompletedIncludeSynonym(_BaseCase):

    def setUp(self):
        self._reset_db()
        self._create_list(1, 'lib', 'synonym')

    def test_today_completed_recognizes_learn_synonym(self):
        """仅有 learn_synonym 记录时 today_completed 也应返回 True"""
        conn = self.db_mod.get_db()
        conn.execute(
            "INSERT INTO study_log (list_id, date, mode, word_ids, accuracy, duration_s) VALUES (?,?,?,?,?,?)",
            (1, str(date.today()), 'learn_synonym', '[1,2,3]', 1.0, 60)
        )
        conn.commit()
        conn.close()
        self.assertTrue(self.app_module.today_completed(1))

    def test_calc_streak_includes_learn_synonym(self):
        """calc_streak 把 learn_synonym 日期纳入连续天数"""
        conn = self.db_mod.get_db()
        # 今天和昨天分别有一次同义词学习
        for d in [date.today(), date.today() - timedelta(days=1)]:
            conn.execute(
                "INSERT INTO study_log (list_id, date, mode, word_ids, accuracy, duration_s) VALUES (?,?,?,?,?,?)",
                (1, str(d), 'learn_synonym', '[1]', 1.0, 30)
            )
        conn.commit()
        conn.close()
        self.assertEqual(self.app_module.calc_streak(), 2, '连续 2 天同义词学习应 streak=2')

    def test_calc_streak_mixed_modes(self):
        """learn 与 learn_synonym 混合时也正确算 streak"""
        conn = self.db_mod.get_db()
        conn.execute(
            "INSERT INTO study_log (list_id, date, mode, word_ids, accuracy, duration_s) VALUES (?,?,?,?,?,?)",
            (1, str(date.today()), 'learn', '[1]', 1.0, 60)
        )
        conn.execute(
            "INSERT INTO study_log (list_id, date, mode, word_ids, accuracy, duration_s) VALUES (?,?,?,?,?,?)",
            (1, str(date.today() - timedelta(days=1)), 'learn_synonym', '[2]', 1.0, 60)
        )
        conn.commit()
        conn.close()
        self.assertEqual(self.app_module.calc_streak(), 2, '混合模式也应计 streak=2')


if __name__ == '__main__':
    unittest.main(verbosity=2)
