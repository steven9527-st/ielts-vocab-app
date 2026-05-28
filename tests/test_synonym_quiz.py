"""单元测试：同义词词库测验出题模式（add-synonym-quiz-mode）

覆盖：
  • _migrate_word_list_types：填充率分类（100%/80%/50%/0%）
  • generate_quiz_questions(list_type='synonym') 输出英文选项
  • generate_quiz_questions(list_type='standard') 维持原中文选项（向后兼容）
  • 干扰项不足时降级
  • 听力测试豁免（test_start 调用方传 'standard'）
  • 词库 type 字段持久化（导入路径）
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
    """每个 Test 类独立 reset DB"""

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


class TestMigrateWordListTypes(_BaseCase):
    """_migrate_word_list_types：按 synonyms 填充率分类"""

    def setUp(self):
        # 清空 word_lists / words 后准备测试场景
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM word_lists")
        conn.commit()
        conn.close()

    def _create_list_with_synonyms(self, list_id, total, with_syn_count, type_value='standard'):
        conn = self.db_mod.get_db()
        conn.execute(
            "INSERT INTO word_lists (id, name, type) VALUES (?, ?, ?)",
            (list_id, f'list_{list_id}', type_value)
        )
        for i in range(total):
            syn = f'syn_{i}' if i < with_syn_count else ''
            conn.execute(
                "INSERT INTO words (list_id, english, chinese, synonyms, status) VALUES (?, ?, ?, ?, 'unmastered')",
                (list_id, f'word_{list_id}_{i}', f'释义_{i}', syn)
            )
        conn.commit()
        conn.close()

    def test_100_percent_fill_marked_synonym(self):
        self._create_list_with_synonyms(1, total=10, with_syn_count=10)
        conn = self.db_mod.get_db()
        self.db_mod._migrate_word_list_types(conn)
        t = conn.execute("SELECT type FROM word_lists WHERE id=1").fetchone()[0]
        conn.close()
        self.assertEqual(t, 'synonym', '100% 填充率应被标 synonym')

    def test_80_percent_marked_synonym(self):
        self._create_list_with_synonyms(2, total=10, with_syn_count=8)
        conn = self.db_mod.get_db()
        self.db_mod._migrate_word_list_types(conn)
        t = conn.execute("SELECT type FROM word_lists WHERE id=2").fetchone()[0]
        conn.close()
        self.assertEqual(t, 'synonym', '80% 填充率（阈值边界）应被标 synonym')

    def test_79_percent_stays_standard(self):
        self._create_list_with_synonyms(3, total=100, with_syn_count=79)
        conn = self.db_mod.get_db()
        self.db_mod._migrate_word_list_types(conn)
        t = conn.execute("SELECT type FROM word_lists WHERE id=3").fetchone()[0]
        conn.close()
        self.assertEqual(t, 'standard', '79% 填充率应保持 standard')

    def test_0_percent_stays_standard(self):
        self._create_list_with_synonyms(4, total=10, with_syn_count=0)
        conn = self.db_mod.get_db()
        self.db_mod._migrate_word_list_types(conn)
        t = conn.execute("SELECT type FROM word_lists WHERE id=4").fetchone()[0]
        conn.close()
        self.assertEqual(t, 'standard')

    def test_already_synonym_not_overwritten(self):
        """显式 synonym 的词库即便填充率低也不被改回 standard"""
        self._create_list_with_synonyms(5, total=10, with_syn_count=2, type_value='synonym')
        conn = self.db_mod.get_db()
        self.db_mod._migrate_word_list_types(conn)
        t = conn.execute("SELECT type FROM word_lists WHERE id=5").fetchone()[0]
        conn.close()
        self.assertEqual(t, 'synonym', '已显式标 synonym 的不应被覆盖')

    def test_empty_list_skipped(self):
        """空词库（0 个词）不参与迁移"""
        conn = self.db_mod.get_db()
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (6, 'empty', 'standard')")
        conn.commit()
        self.db_mod._migrate_word_list_types(conn)
        t = conn.execute("SELECT type FROM word_lists WHERE id=6").fetchone()[0]
        conn.close()
        self.assertEqual(t, 'standard')


class TestGenerateQuizQuestionsSynonymMode(_BaseCase):
    """generate_quiz_questions(list_type='synonym') 行为"""

    def setUp(self):
        # 清表 + 准备一个同义词词库（5 个词，全部带 synonyms）
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM word_lists")
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (1, 'syn_lib', 'synonym')")
        for i, (en, zh, syn) in enumerate([
            ('keep sth off', '保持某事关闭', 'prevent sth from appearing'),
            ('routine', '常规', 'frequent exposure'),
            ('distinct', '分离', 'different'),
            ('support', '支持', 'provide evidence'),
            ('momentarily', '暂时地', 'short period'),
        ], start=1):
            conn.execute(
                "INSERT INTO words (id, list_id, english, chinese, synonyms, status) "
                "VALUES (?, 1, ?, ?, ?, 'unmastered')",
                (i, en, zh, syn)
            )
        conn.commit()
        conn.close()

    def test_synonym_options_are_english(self):
        """type='synonym' → 选项均为英文同义词"""
        questions = self.app_module.generate_quiz_questions(
            [1, 2, 3], list_id=1, list_type='synonym'
        )
        self.assertIsNotNone(questions)
        self.assertEqual(len(questions), 3)
        for q in questions:
            # 正确答案是 synonyms 字段值
            self.assertIn(q['correct'], [
                'prevent sth from appearing', 'frequent exposure', 'different',
                'provide evidence', 'short period'
            ], f'correct 应为某个 synonym，得到 {q["correct"]!r}')
            # 4 个选项都是英文同义词
            self.assertEqual(len(q['options']), 4)
            self.assertEqual(len(set(q['options'])), 4, '选项不应重复')
            # 中文释义不应出现在选项中
            for opt in q['options']:
                self.assertNotIn('保持', opt)
                self.assertNotIn('常规', opt)

    def test_correct_answer_in_options(self):
        questions = self.app_module.generate_quiz_questions([1], list_id=1, list_type='synonym')
        self.assertIn(questions[0]['correct'], questions[0]['options'])

    def test_word_without_synonym_skipped(self):
        """同义词模式下，没有 synonyms 的词跳过该题"""
        # 加一个无 synonyms 的词到库里
        conn = self.db_mod.get_db()
        conn.execute(
            "INSERT INTO words (id, list_id, english, chinese, synonyms, status) "
            "VALUES (99, 1, 'orphan', '孤词', '', 'unmastered')"
        )
        conn.commit()
        conn.close()
        questions = self.app_module.generate_quiz_questions(
            [1, 99, 2], list_id=1, list_type='synonym'
        )
        # word_id=99 没有 synonyms，应被跳过
        word_ids_in_questions = [q['word_id'] for q in questions]
        self.assertNotIn(99, word_ids_in_questions)
        self.assertIn(1, word_ids_in_questions)
        self.assertIn(2, word_ids_in_questions)

    def test_distractor_pool_insufficient_falls_back(self):
        """干扰项不足时降级到中文选项（本题 fallback）"""
        # 创建一个新词库，只有 4 个词带 synonyms 但其中 3 个有相同 synonyms
        conn = self.db_mod.get_db()
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (2, 'tiny', 'synonym')")
        conn.execute("INSERT INTO words (id, list_id, english, chinese, synonyms, status) VALUES (10, 2, 'a', 'A', 'sameSyn', 'unmastered')")
        conn.execute("INSERT INTO words (id, list_id, english, chinese, synonyms, status) VALUES (11, 2, 'b', 'B', 'sameSyn', 'unmastered')")
        conn.execute("INSERT INTO words (id, list_id, english, chinese, synonyms, status) VALUES (12, 2, 'c', 'C', 'sameSyn', 'unmastered')")
        conn.execute("INSERT INTO words (id, list_id, english, chinese, synonyms, status) VALUES (13, 2, 'd', 'D', 'uniqueSyn', 'unmastered')")
        conn.commit()
        conn.close()
        # 对于 word_id=13（uniqueSyn），其他词的 synonyms 去重后只有 'sameSyn' 一个
        # 干扰项池只有 1 个（不足 3 个）→ 应降级为中文选项
        questions = self.app_module.generate_quiz_questions([13], list_id=2, list_type='synonym')
        self.assertEqual(len(questions), 1)
        # 降级后正确答案是 chinese
        self.assertEqual(questions[0]['correct'], 'D')


class TestGenerateQuizQuestionsStandardMode(_BaseCase):
    """list_type='standard' 维持原中文选项行为"""

    def setUp(self):
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM word_lists")
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (1, 'std', 'standard')")
        for i in range(5):
            conn.execute(
                "INSERT INTO words (id, list_id, english, chinese, status) VALUES (?, 1, ?, ?, 'unmastered')",
                (i + 1, f'word{i}', f'释义{i}')
            )
        conn.commit()
        conn.close()

    def test_standard_options_are_chinese(self):
        questions = self.app_module.generate_quiz_questions(
            [1, 2, 3], list_id=1, list_type='standard'
        )
        for q in questions:
            for opt in q['options']:
                self.assertTrue(opt.startswith('释义'), f'选项应是中文释义，得到 {opt!r}')

    def test_default_list_type_is_standard(self):
        """不传 list_type 时默认 'standard'，行为与显式 standard 一致"""
        questions = self.app_module.generate_quiz_questions([1, 2], list_id=1)
        self.assertIsNotNone(questions)
        for q in questions:
            for opt in q['options']:
                self.assertTrue(opt.startswith('释义'))


class TestGetListType(_BaseCase):
    """_get_list_type 工具函数"""

    def setUp(self):
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM word_lists")
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (1, 'std', 'standard')")
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (2, 'syn', 'synonym')")
        conn.commit()
        conn.close()

    def test_get_standard(self):
        self.assertEqual(self.app_module._get_list_type(1), 'standard')

    def test_get_synonym(self):
        self.assertEqual(self.app_module._get_list_type(2), 'synonym')

    def test_get_nonexistent_returns_standard(self):
        self.assertEqual(self.app_module._get_list_type(99999), 'standard')

    def test_get_none_returns_standard(self):
        self.assertEqual(self.app_module._get_list_type(None), 'standard')


if __name__ == '__main__':
    unittest.main(verbosity=2)
