"""单元测试：Excel 解析层的同义词模式与中文列识别放宽。

覆盖：
  • guess_columns 对英文-英文双列输入应正确识别 + suggested_mode='synonym'
  • apply_mapping(import_mode='synonym') 应使 chinese == synonyms
  • 标准 Excel 词表（含中文释义）应保持原行为，suggested_mode='standard'
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from excel_parser import guess_columns, apply_mapping  # noqa: E402


class TestGuessColumnsEnglishOnly(unittest.TestCase):
    """英文-英文同义词词库：B 列也是英文，需走退化策略"""

    def test_english_english_table(self):
        rows = [
            ['alarming rate of loss', 'plight'],
            ['formal tuition', 'classroom'],
            ['harbor', 'hold'],
            ['misconception', 'mistaken view'],
            ['modification', 'change/transform/shift'],
            ['majority', 'most'],
        ]
        g = guess_columns(rows)
        self.assertEqual(g['english_col'], 0, f'english_col 应为 0, 实际 {g}')
        self.assertEqual(g['chinese_col'], 1, f'chinese_col 应为 1（退化策略）, 实际 {g}')
        self.assertEqual(g['suggested_mode'], 'synonym',
                         f'B 列无中文应推荐同义词模式, 实际 {g["suggested_mode"]}')

    def test_table_with_header(self):
        rows = [
            ['文章', '题目'],
            ['alarming rate of loss', 'plight'],
            ['formal tuition', 'classroom'],
            ['harbor', 'hold'],
        ]
        g = guess_columns(rows)
        self.assertEqual(g['english_col'], 0)
        self.assertEqual(g['chinese_col'], 1)
        self.assertEqual(g['suggested_mode'], 'synonym')


class TestGuessColumnsStandard(unittest.TestCase):
    """标准词表：B 列含中文，应保持现有行为"""

    def test_standard_chinese_meaning(self):
        rows = [
            ['Word', 'Meaning'],
            ['abate', '减轻; 失效'],
            ['friend', '朋友'],
            ['large', '大的'],
        ]
        g = guess_columns(rows)
        self.assertEqual(g['english_col'], 0)
        self.assertEqual(g['chinese_col'], 1)
        self.assertEqual(g['suggested_mode'], 'standard',
                         f'B 列含中文应推荐标准模式, 实际 {g["suggested_mode"]}')


class TestApplyMappingSynonymMode(unittest.TestCase):
    """同义词模式：chinese == synonyms"""

    def test_synonym_mode_dual_write(self):
        rows = [
            ['alarming rate of loss', 'plight'],
            ['misconception', 'mistaken view'],
        ]
        entries = apply_mapping(
            rows,
            english_col=0,
            chinese_col=1,
            skip_first_row=False,
            import_mode='synonym',
        )
        self.assertEqual(len(entries), 2)
        for e in entries:
            self.assertEqual(e['chinese'], e['synonyms'],
                             f'同义词模式下 chinese 与 synonyms 应一致: {e}')
            self.assertFalse(e['failed'])

    def test_standard_mode_keeps_synonyms_empty(self):
        rows = [
            ['abate', '减轻; 失效'],
            ['friend', '朋友'],
        ]
        entries = apply_mapping(
            rows,
            english_col=0,
            chinese_col=1,
            skip_first_row=False,
            import_mode='standard',
        )
        for e in entries:
            self.assertEqual(e['synonyms'], '',
                             f'标准模式下 synonyms 应为空: {e}')

    def test_explicit_synonym_col_overrides_mode(self):
        """显式 synonym_col 优先于模式推断"""
        rows = [
            ['abate', '减轻', 'reduce, lessen'],
        ]
        entries = apply_mapping(
            rows,
            english_col=0,
            chinese_col=1,
            synonym_col=2,
            skip_first_row=False,
            import_mode='synonym',  # 即使是 synonym 模式
        )
        # 显式列优先：synonyms 应该是显式列的值，不是 chinese 复制
        self.assertEqual(entries[0]['synonyms'], 'reduce, lessen')
        self.assertEqual(entries[0]['chinese'], '减轻')

    def test_invalid_import_mode_raises(self):
        rows = [['abate', '减轻']]
        with self.assertRaises(RuntimeError):
            apply_mapping(rows, english_col=0, chinese_col=1,
                          skip_first_row=False, import_mode='invalid')


if __name__ == '__main__':
    unittest.main(verbosity=2)
