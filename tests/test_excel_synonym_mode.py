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


class TestGuessColumnsExcludesNumberColumn(unittest.TestCase):
    """序号列不能被误选为英文列（修复 fix-pdf-import-route-priority）"""

    def test_four_columns_with_index(self):
        """4 列输入：序号 / 单词 / 音标 / 中文释义
        典型场景：表格 PDF 抽出来的雅思词表
        """
        rows = [
            ['1.', 'aback', "[e'baek]", 'adv. 大吃一惊'],
            ['2.', 'abate', "[e'beIt]", 'v. 减轻; 失效'],
            ['3.', 'abnormal', "[eb'no:m(e)l]", 'adj. 不正常的'],
            ['4.', 'abolish', "[e'bOlIS]", 'vt. 废除'],
            ['5.', 'abrupt', "[e'brApt]", 'adj. 突然的'],
        ]
        g = guess_columns(rows)
        # 关键断言：english_col 应是 1（单词列），不是 0（序号列）
        self.assertEqual(g['english_col'], 1,
                         f'english_col 应为 1（单词列），不应为 0（序号列）。实际 {g}')
        # 中文列应是最后一列
        self.assertEqual(g['chinese_col'], 3, f'chinese_col 应为 3，实际 {g}')

    def test_pure_number_column_excluded(self):
        """单纯的序号列（"100.", "1000."）不应被选为英文列"""
        rows = [
            ['100.', 'combination', 'n. 结合; 联合体'],
            ['101.', 'auction', 'n. 拍卖'],
            ['1000.', 'protest', 'n. 抗议'],
            ['1001.', 'prototype', 'n. 原型'],
        ]
        g = guess_columns(rows)
        self.assertEqual(g['english_col'], 1,
                         f'english_col 应为单词列 1，不应为序号列 0。实际 {g}')

    def test_fallback_when_no_word_like_column(self):
        """所有列都不像英文单词时（如全数字）→ 回退到 ASCII 占比规则
        这是 D2 兜底机制：不破坏极端边界场景
        """
        rows = [
            ['123', '456'],
            ['789', '012'],
        ]
        g = guess_columns(rows)
        # 不期望特定值，但至少不应该报错或返回 -1（除非中文也没有）
        # 这里只验证不抛异常
        self.assertIn('english_col', g)


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
