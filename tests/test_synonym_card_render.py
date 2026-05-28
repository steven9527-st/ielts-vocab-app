"""单元测试：同义词卡片中文显示（show-chinese-on-synonym-card）

覆盖：
  • has_cjk Jinja test 函数行为
  • 词条 chinese 非空 → 正面渲染含 .synonym-front-chinese
  • 词条 chinese 为空 → 正面不渲染中文行
  • SYNONYMS 列表中含中文项 → 该项打 .synonym-syn--cn class
  • SYNONYMS 列表全英文 → 无项打 .synonym-syn--cn class
"""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class TestHasCjkFunction(unittest.TestCase):
    """has_cjk 函数纯逻辑测试"""

    @classmethod
    def setUpClass(cls):
        from app import has_cjk
        cls.has_cjk = staticmethod(has_cjk)

    def test_pure_chinese(self):
        self.assertTrue(self.has_cjk('折磨'))
        self.assertTrue(self.has_cjk('令人警觉的损失速度'))

    def test_pure_english(self):
        self.assertFalse(self.has_cjk('plight'))
        self.assertFalse(self.has_cjk('catastrophe'))
        self.assertFalse(self.has_cjk('abc, def'))

    def test_mixed(self):
        self.assertTrue(self.has_cjk('plight 折磨'))
        self.assertTrue(self.has_cjk('a折b'))

    def test_empty(self):
        self.assertFalse(self.has_cjk(''))
        self.assertFalse(self.has_cjk('   '))

    def test_non_string_safe(self):
        self.assertFalse(self.has_cjk(None))
        self.assertFalse(self.has_cjk(123))
        self.assertFalse(self.has_cjk([]))


class _RenderBaseCase(unittest.TestCase):
    """构造一个有 list 和带同义词的词条的测试环境"""

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

        # 准备词库
        database.init_db()
        conn = database.get_db()
        conn.execute("INSERT INTO word_lists (id, name) VALUES (1, 'test')")
        # 词 1：有中文 + 同义词全英
        conn.execute(
            "INSERT INTO words (id, list_id, english, chinese, phonetic, synonyms, status) "
            "VALUES (1, 1, 'alarming rate of loss', '令人警觉的损失速度', '', 'plight, catastrophe', 'unmastered')"
        )
        # 词 2：无中文 + 同义词全英
        conn.execute(
            "INSERT INTO words (id, list_id, english, chinese, phonetic, synonyms, status) "
            "VALUES (2, 1, 'harbor', '', '', 'hold, shelter', 'unmastered')"
        )
        # 词 3：有中文 + 同义词混合中英
        conn.execute(
            "INSERT INTO words (id, list_id, english, chinese, phonetic, synonyms, status) "
            "VALUES (3, 1, 'plight', '困境', '', 'distress, 折磨, hardship', 'unmastered')"
        )
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(cls._tmp_db)
        except Exception:
            pass

    def _render_card(self, word_id):
        """模拟进入同义词卡片页，返回 HTML"""
        client = self.app.test_client()
        with client.session_transaction() as sess:
            sess['syn_queue'] = [word_id]
            sess['syn_total'] = 1
            sess['list_id'] = 1
        resp = client.get('/learn/synonym/card')
        self.assertEqual(resp.status_code, 200,
                         f'渲染失败 status={resp.status_code} body={resp.data[:200]!r}')
        return resp.get_data(as_text=True)


class TestSynonymCardRender(_RenderBaseCase):

    def test_word_with_chinese_renders_front_chinese(self):
        """词条 chinese 非空 → 正面含 .synonym-front-chinese class 与中文文本"""
        html = self._render_card(1)
        self.assertIn('synonym-front-chinese', html, '正面应渲染 .synonym-front-chinese')
        self.assertIn('令人警觉的损失速度', html)

    def test_word_without_chinese_skips_front_chinese(self):
        """词条 chinese 为空 → 正面不渲染中文行"""
        html = self._render_card(2)
        self.assertNotIn('synonym-front-chinese', html,
                         '空 chinese 不应渲染 .synonym-front-chinese class')

    def test_pure_english_synonyms_no_cn_class(self):
        """同义词全英 → 无项打 .synonym-syn--cn"""
        html = self._render_card(1)
        self.assertNotIn('synonym-syn--cn', html,
                         '全英同义词不应有 .synonym-syn--cn class')

    def test_mixed_synonyms_marks_cn_items(self):
        """同义词含中文项 → 该项打 .synonym-syn--cn class"""
        html = self._render_card(3)
        self.assertIn('synonym-syn--cn', html,
                      '含中文同义词应至少出现一次 .synonym-syn--cn class')
        # 中文项与英文项都应该出现在 HTML 中
        self.assertIn('折磨', html)
        self.assertIn('distress', html)
        self.assertIn('hardship', html)


if __name__ == '__main__':
    unittest.main(verbosity=2)
