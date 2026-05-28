"""单元测试：双英文列同义词导入（add-paired-synonym-import）

覆盖：
  • _split_chinese_pair 全部边界
  • apply_mapping 双列展开（一行 → 两条 entries 互为同义词）
  • apply_mapping english_col_2=-1 时走原路径（向后兼容）
  • apply_mapping 标准模式即便误传 english_col_2 也忽略
  • D 列无 / 时 entry2.chinese 为空且 failed=True
  • /import/excel_apply 路由列冲突校验
"""

import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class TestSplitChinesePair(unittest.TestCase):
    """_split_chinese_pair 纯逻辑测试"""

    @classmethod
    def setUpClass(cls):
        from excel_parser import _split_chinese_pair
        cls.split = staticmethod(_split_chinese_pair)

    def test_standard_split(self):
        self.assertEqual(self.split('A / B'), ('A', 'B'))
        self.assertEqual(self.split('保持某事关闭 / 防止某事出现'),
                         ('保持某事关闭', '防止某事出现'))

    def test_no_space_split(self):
        self.assertEqual(self.split('A/B'), ('A', 'B'))
        self.assertEqual(self.split('损失/困境'), ('损失', '困境'))

    def test_multiple_separators(self):
        # 仅以第一个 / 拆分
        self.assertEqual(self.split('A / B / C'), ('A', 'B / C'))
        self.assertEqual(self.split('A/B/C/D'), ('A', 'B/C/D'))

    def test_no_separator(self):
        self.assertEqual(self.split('损失率惊人'), ('损失率惊人', ''))
        self.assertEqual(self.split('plight'), ('plight', ''))

    def test_empty(self):
        self.assertEqual(self.split(''), ('', ''))
        self.assertEqual(self.split('   '), ('', ''))

    def test_non_string(self):
        self.assertEqual(self.split(None), ('', ''))
        self.assertEqual(self.split(123), ('', ''))
        self.assertEqual(self.split([]), ('', ''))

    def test_padding_whitespace(self):
        self.assertEqual(self.split('  A / B  '), ('A', 'B'))
        self.assertEqual(self.split('  A  /  B  '), ('A', 'B'))


class TestApplyMappingPaired(unittest.TestCase):
    """双列展开测试"""

    @classmethod
    def setUpClass(cls):
        from excel_parser import apply_mapping
        cls.apply = staticmethod(apply_mapping)

    def test_paired_expansion(self):
        """同义词模式 + 指定 english_col_2 → 一行展开为两条互为同义词的 entries"""
        rows = [
            ['章节', '文章 (英文)', '题目 (英文)', '中文翻译'],  # header
            ['C19 Test 1', 'keep sth off', 'prevent sth from appearing',
             '保持某事关闭 / 防止某事出现'],
            ['C19 Test 1', 'routine', 'frequent exposure', '常规 / 频繁接触'],
        ]
        entries = self.apply(
            rows,
            english_col=1,
            chinese_col=3,
            english_col_2=2,
            import_mode='synonym',
            skip_first_row=True,
        )
        # 2 行 × 2 = 4 条 entries
        self.assertEqual(len(entries), 4, '双列展开应输出 N×2 条')

        # entry1: keep sth off
        self.assertEqual(entries[0]['english'], 'keep sth off')
        self.assertEqual(entries[0]['chinese'], '保持某事关闭')
        self.assertEqual(entries[0]['synonyms'], 'prevent sth from appearing')
        self.assertFalse(entries[0]['failed'])

        # entry2: prevent sth from appearing
        self.assertEqual(entries[1]['english'], 'prevent sth from appearing')
        self.assertEqual(entries[1]['chinese'], '防止某事出现')
        self.assertEqual(entries[1]['synonyms'], 'keep sth off')
        self.assertFalse(entries[1]['failed'])

        # entry3: routine
        self.assertEqual(entries[2]['english'], 'routine')
        self.assertEqual(entries[2]['chinese'], '常规')
        self.assertEqual(entries[2]['synonyms'], 'frequent exposure')

        # entry4: frequent exposure
        self.assertEqual(entries[3]['english'], 'frequent exposure')
        self.assertEqual(entries[3]['chinese'], '频繁接触')
        self.assertEqual(entries[3]['synonyms'], 'routine')

    def test_no_separator_marks_entry2_failed(self):
        """D 列无 / 时 entry2.chinese 为空且 failed=True"""
        rows = [
            ['_', 'header', 'header2', 'header_zh'],
            ['_', 'plight', 'distress', '困境'],  # 无 /
        ]
        entries = self.apply(
            rows, english_col=1, chinese_col=3, english_col_2=2,
            import_mode='synonym', skip_first_row=True,
        )
        self.assertEqual(len(entries), 2)
        # entry1 拿到完整中文
        self.assertEqual(entries[0]['english'], 'plight')
        self.assertEqual(entries[0]['chinese'], '困境')
        self.assertFalse(entries[0]['failed'])
        # entry2 chinese 为空 → failed
        self.assertEqual(entries[1]['english'], 'distress')
        self.assertEqual(entries[1]['chinese'], '')
        self.assertTrue(entries[1]['failed'])

    def test_english_col_2_negative_falls_back(self):
        """english_col_2=-1 时走原路径（向后兼容）"""
        rows = [
            ['en', 'zh'],
            ['plight', '困境'],
        ]
        # 不传 english_col_2，默认 -1
        entries = self.apply(rows, english_col=0, chinese_col=1,
                             import_mode='synonym', skip_first_row=True)
        self.assertEqual(len(entries), 1, 'english_col_2=-1 应走原路径，1 行 → 1 条')
        self.assertEqual(entries[0]['english'], 'plight')
        self.assertEqual(entries[0]['chinese'], '困境')
        # 同义词模式自动复制 chinese 到 synonyms
        self.assertEqual(entries[0]['synonyms'], '困境')

    def test_standard_mode_ignores_english_col_2(self):
        """标准模式即便误传 english_col_2 也忽略"""
        rows = [
            ['en', 'en2', 'zh'],
            ['hello', 'world', '你好'],
        ]
        entries = self.apply(
            rows, english_col=0, chinese_col=2, english_col_2=1,
            import_mode='standard', skip_first_row=True,
        )
        self.assertEqual(len(entries), 1, '标准模式应忽略 english_col_2')
        self.assertEqual(entries[0]['english'], 'hello')
        self.assertEqual(entries[0]['chinese'], '你好')

    def test_blank_row_skipped(self):
        """整行空白 → 跳过"""
        rows = [
            ['en', 'en2', 'zh'],
            ['', '', ''],
            ['plight', 'distress', '困境 / 痛苦'],
        ]
        entries = self.apply(
            rows, english_col=0, chinese_col=2, english_col_2=1,
            import_mode='synonym', skip_first_row=True,
        )
        self.assertEqual(len(entries), 2, '空行被跳过')
        self.assertEqual(entries[0]['english'], 'plight')


class TestRouteColumnConflict(unittest.TestCase):
    """/import/excel_apply 路由列冲突校验"""

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

        database.init_db()

    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(cls._tmp_db)
        except Exception:
            pass

    def _setup_session(self, client, rows):
        """灌一个 excel raw token 到 session 里"""
        token = self.app_module._save_excel_raw({
            'rows': rows,
            'filename': 'test.xlsx',
        })
        with client.session_transaction() as sess:
            sess['excel_raw_token'] = token
        return token

    def test_english_col_2_equals_english_col_returns_400(self):
        client = self.app.test_client()
        self._setup_session(client, [['a', 'b', 'c'], ['x', 'y', 'z']])
        resp = client.post(
            '/import/excel_apply',
            data=json.dumps({
                'english_col': 0,
                'chinese_col': 2,
                'english_col_2': 0,  # 与 english_col 相同
                'import_mode': 'synonym',
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('英文列 2', resp.get_json().get('error', ''))

    def test_english_col_2_equals_chinese_col_returns_400(self):
        client = self.app.test_client()
        self._setup_session(client, [['a', 'b', 'c'], ['x', 'y', 'z']])
        resp = client.post(
            '/import/excel_apply',
            data=json.dumps({
                'english_col': 0,
                'chinese_col': 2,
                'english_col_2': 2,  # 与 chinese_col 相同
                'import_mode': 'synonym',
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('英文列 2', resp.get_json().get('error', ''))

    def test_standard_mode_ignores_english_col_2_conflict(self):
        """标准模式下即便 english_col_2 与其他列冲突也不返回 400（被忽略）"""
        client = self.app.test_client()
        self._setup_session(client, [
            ['en', 'zh'],
            ['plight', '困境'],
        ])
        resp = client.post(
            '/import/excel_apply',
            data=json.dumps({
                'english_col': 0,
                'chinese_col': 1,
                'english_col_2': 0,  # 标准模式下应被忽略
                'import_mode': 'standard',
                'skip_first_row': True,
            }),
            content_type='application/json',
        )
        # 不应被 english_col_2 冲突阻止
        self.assertEqual(resp.status_code, 200,
                         f'标准模式应忽略 english_col_2 冲突，实际 {resp.status_code} body={resp.data[:200]!r}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
