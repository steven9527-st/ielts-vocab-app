"""E2E 测试：默写学习流（add-dictation-vocabulary）

覆盖：
  • 默写学习 setup → start → card → next/prev → quiz → done 全流程
  • 默写翻卡正面显示中文、背面显示英文
  • 学完最后一张自动跳填空测验（无 4 词门槛）
  • 测验为填空模式：给中文写英文，大小写不敏感+忽略空格
  • 测验通关后写 study_log + 更新 mastered
  • 错题显示正确拼写对比
  • 默写词库导入（Excel dictation 模式）
  • 默写词库首页入口和 stats 展示
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


class TestDictationLearnFlow(_BaseCase):
    """默写学习流端到端测试"""

    def setUp(self):
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM study_log")
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM word_lists")
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (1, 'dict_lib', 'dictation')")
        for i, (en, zh) in enumerate([
            ('apple', '苹果'),
            ('banana', '香蕉'),
            ('cherry', '樱桃'),
            ('dragon', '龙'),
            ('eagle', '鹰'),
        ], start=1):
            conn.execute(
                "INSERT INTO words (id, list_id, english, chinese, status) "
                "VALUES (?, 1, ?, ?, 'unmastered')",
                (i, en, zh)
            )
        conn.commit()
        conn.close()

    def _start_dictation_session(self, client, word_ids):
        from datetime import datetime
        with client.session_transaction() as sess:
            sess['list_id'] = 1
            sess['list_picked'] = True
            sess['dict_word_ids'] = list(word_ids)
            sess['dict_total'] = len(word_ids)
            sess['dict_index'] = 0
            sess['dict_started_at'] = datetime.now().isoformat()
            sess['dict_list_id'] = 1

    def _do_dictation_quiz(self, client, word_ids):
        """辅助：走完默写学习 → 跳测验 → 返回 quiz questions"""
        self._start_dictation_session(client, word_ids)
        for _ in range(len(word_ids)):
            client.post('/learn/dictation/next')
        client.get('/learn/quiz')
        with client.session_transaction() as sess:
            token = sess.get('quiz_token')
        return self.app_module._load_quiz_data(token)['questions']

    def test_setup_page_renders(self):
        """默写 setup 页正常渲染"""
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['list_id'] = 1
            sess['list_picked'] = True
        resp = client.get('/learn/dictation/setup')
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn('默写学习', body)
        self.assertIn('开始默写', body)

    def test_start_creates_session(self):
        """start 初始化 session 并跳转 card"""
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['list_id'] = 1
            sess['list_picked'] = True
        resp = client.post('/learn/dictation/start', data={'n': 3}, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/learn/dictation/card', resp.location)

        with client.session_transaction() as sess:
            self.assertEqual(sess['dict_total'], 3)
            self.assertEqual(sess['dict_index'], 0)
            self.assertEqual(len(sess['dict_word_ids']), 3)

    def test_card_front_shows_chinese(self):
        """默写卡片正面显示中文释义"""
        client = self.app.test_client()
        self._start_dictation_session(client, [1, 2, 3])
        resp = client.get('/learn/dictation/card')
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn('苹果', body)
        self.assertIn('默写模式', body)
        self.assertIn('点击翻面查看答案', body)

    def test_next_and_prev_navigation(self):
        """前进/后退导航正常"""
        client = self.app.test_client()
        self._start_dictation_session(client, [1, 2, 3])

        # 第 1 张：prev 不可用
        resp = client.get('/learn/dictation/card')
        body = resp.get_data(as_text=True)
        self.assertIn('const prevAvailable = false;', body)

        # next → 第 2 张
        client.post('/learn/dictation/next')
        with client.session_transaction() as sess:
            self.assertEqual(sess['dict_index'], 1)
        resp = client.get('/learn/dictation/card')
        body = resp.get_data(as_text=True)
        self.assertIn('const prevAvailable = true;', body)
        self.assertIn('2 / 3', body)

        # prev → 回到第 1 张
        client.post('/learn/dictation/prev')
        with client.session_transaction() as sess:
            self.assertEqual(sess['dict_index'], 0)

    def test_last_card_redirects_to_quiz(self):
        """学完最后一张跳填空测验（无 4 词门槛）"""
        client = self.app.test_client()
        self._start_dictation_session(client, [1, 2])

        client.post('/learn/dictation/next')  # idx=1
        resp = client.post('/learn/dictation/next', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/learn/quiz', resp.location)

    def test_quiz_renders_dictation_template(self):
        """测验页渲染默写填空模板（含输入框）"""
        questions = self._do_dictation_quiz(self.app.test_client(), [1, 2])
        # 验证题目结构：有 chinese + correct，无 options
        for q in questions:
            self.assertIn('chinese', q)
            self.assertIn('correct', q)
            self.assertNotIn('options', q)

    def test_quiz_dictation_page_has_input(self):
        """默写测验页有输入框而非选项按钮"""
        client = self.app.test_client()
        self._start_dictation_session(client, [1, 2])
        for _ in range(2):
            client.post('/learn/dictation/next')
        client.get('/learn/quiz')
        resp = client.get('/quiz/question')
        body = resp.get_data(as_text=True)
        # 应有输入框和"下一题"按钮，无选项按钮
        self.assertIn('输入英文单词', body)
        self.assertIn('下一题', body)
        self.assertNotIn('quiz-option', body)

    def test_dictation_quiz_case_insensitive(self):
        """默写测验大小写不敏感"""
        client = self.app.test_client()
        questions = self._do_dictation_quiz(client, [1, 2])

        # 全部用大写答
        for q in questions:
            client.post('/quiz/answer', data={'answer': q['correct'].upper()})
        resp = client.get('/quiz/submit')
        body = resp.get_data(as_text=True)
        self.assertIn('今日通关', body)

    def test_dictation_quiz_strips_whitespace(self):
        """默写测验忽略首尾空格"""
        client = self.app.test_client()
        questions = self._do_dictation_quiz(client, [1, 2])

        for q in questions:
            client.post('/quiz/answer', data={'answer': f'  {q["correct"]}  '})
        resp = client.get('/quiz/submit')
        body = resp.get_data(as_text=True)
        self.assertIn('今日通关', body)

    def test_dictation_quiz_wrong_answer(self):
        """默写测验答错显示正确拼写"""
        client = self.app.test_client()
        questions = self._do_dictation_quiz(client, [1, 2])

        # 第 1 题答对，第 2 题答错
        client.post('/quiz/answer', data={'answer': questions[0]['correct']})
        client.post('/quiz/answer', data={'answer': 'wronganswer'})
        resp = client.get('/quiz/submit')
        body = resp.get_data(as_text=True)
        self.assertIn('1 / 2', body)  # 1对1错
        self.assertIn('正确拼写', body)
        self.assertIn('你的默写', body)

    def test_full_flow_writes_both_logs(self):
        """完整通关：study_log 应有 learn_dictation + quiz 两条"""
        client = self.app.test_client()
        questions = self._do_dictation_quiz(client, [1, 2])

        for q in questions:
            client.post('/quiz/answer', data={'answer': q['correct']})

        resp = client.get('/quiz/submit')
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn('今日通关', body)
        self.assertIn('默写', body)
        self.assertIn('/learn/dictation/done', body)

        # study_log 应有两条
        conn = self.db_mod.get_db()
        modes = [r['mode'] for r in conn.execute("SELECT mode FROM study_log ORDER BY id").fetchall()]
        conn.close()
        self.assertEqual(sorted(modes), ['learn_dictation', 'quiz'])

    def test_quiz_pass_updates_mastered(self):
        """测验通关后词状态更新为 mastered"""
        client = self.app.test_client()
        questions = self._do_dictation_quiz(client, [1, 2])

        for q in questions:
            client.post('/quiz/answer', data={'answer': q['correct']})
        client.get('/quiz/submit')

        conn = self.db_mod.get_db()
        mastered = conn.execute(
            "SELECT COUNT(*) FROM words WHERE list_id=1 AND status='mastered'"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(mastered, 2)

    def test_dictation_done_page(self):
        """默写完成页正常渲染"""
        client = self.app.test_client()
        self._start_dictation_session(client, [1, 2])
        resp = client.get('/learn/dictation/done')
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn('默写完成', body)

    def test_abandon_cleans_session(self):
        """放弃默写清理 session"""
        client = self.app.test_client()
        self._start_dictation_session(client, [1, 2, 3])
        client.post('/learn/dictation/abandon')

        with client.session_transaction() as sess:
            self.assertNotIn('dict_word_ids', sess)
            self.assertNotIn('dict_index', sess)

    def test_small_library_goes_to_quiz(self):
        """默写词库 <4 个词也进测验（填空无干扰项门槛）"""
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM study_log")
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM word_lists")
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (1, 'tiny', 'dictation')")
        conn.execute("INSERT INTO words (id, list_id, english, chinese, status) VALUES (1, 1, 'a', 'A', 'unmastered')")
        conn.execute("INSERT INTO words (id, list_id, english, chinese, status) VALUES (2, 1, 'b', 'B', 'unmastered')")
        conn.commit()
        conn.close()

        client = self.app.test_client()
        self._start_dictation_session(client, [1, 2])

        client.post('/learn/dictation/next')
        resp = client.post('/learn/dictation/next', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        # 应跳测验而非直接完成
        self.assertIn('/learn/quiz', resp.location)


class TestDictationImport(_BaseCase):
    """默写词库导入测试"""

    def setUp(self):
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM study_log")
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM word_lists")
        conn.commit()
        conn.close()

    def test_import_dictation_type(self):
        """导入时选择 dictation 模式创建 dictation 类型词库"""
        client = self.app.test_client()

        with client.session_transaction() as sess:
            sess['import_mode'] = 'dictation'
            sess['import_filename'] = 'test.csv'

        resp = client.post('/import/confirm',
                           json={
                               'entries': [
                                   {'english': 'hello', 'chinese': '你好', 'phonetic': '', 'pos': '', 'synonyms': ''},
                                   {'english': 'world', 'chinese': '世界', 'phonetic': '', 'pos': '', 'synonyms': ''},
                               ],
                               'list_name': '默写测试库'
                           })
        data = resp.get_json()
        self.assertTrue(data['success'])

        conn = self.db_mod.get_db()
        row = conn.execute("SELECT type FROM word_lists WHERE name='默写测试库'").fetchone()
        conn.close()
        self.assertEqual(row['type'], 'dictation')

    def test_get_list_type_dictation(self):
        """_get_list_type 返回 dictation"""
        conn = self.db_mod.get_db()
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (99, 'dict_test', 'dictation')")
        conn.commit()
        conn.close()

        result = self.app_module._get_list_type(99)
        self.assertEqual(result, 'dictation')


class TestDictationIndexEntry(_BaseCase):
    """默写词库首页入口测试"""

    def setUp(self):
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM study_log")
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM word_lists")
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (1, 'dict_lib', 'dictation')")
        for i in range(1, 6):
            conn.execute(
                "INSERT INTO words (id, list_id, english, chinese, status) VALUES (?, 1, ?, ?, 'unmastered')",
                (i, f'word{i}', f'词{i}')
            )
        conn.commit()
        conn.close()

    def test_index_shows_dictation_entry(self):
        """默写词库首页显示"开始默写"按钮"""
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['list_id'] = 1
            sess['list_picked'] = True
        resp = client.get('/')
        body = resp.get_data(as_text=True)
        self.assertIn('开始默写', body)

    def test_index_stats_normal(self):
        """默写词库首页 stats 正常展示"""
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['list_id'] = 1
            sess['list_picked'] = True
        resp = client.get('/')
        body = resp.get_data(as_text=True)
        self.assertIn('词库总数', body)
        self.assertIn('未掌握', body)


if __name__ == '__main__':
    unittest.main(verbosity=2)
