"""回归测试：词库字段含换行符导致测验误判（fix-newline-answer-mismatch）

Bug 背景：
  Excel 单元格内换行（Alt+Enter）把 \\n 带进 words.synonyms 等字段。
  浏览器表单提交时按 HTML 标准把裸 LF 规范化为 CRLF，
  服务端 quiz_submit 精确字符串比较失败：
    'different governments have different\\r\\nattitudes'  (用户提交，浏览器规范化后)
    vs 'different governments have different\\nattitudes'   (服务端 q['correct'])
  结果页两行显示完全一致（\\r\\n 与 \\n 渲染相同），用户肉眼无法分辨。

修复三层防线：
  A. database._migrate_strip_newlines —— 存量数据清洗
  B. excel_parser._normalize_cell / pdf_parser._clean_table_rows —— 导入时清洗
  C. app.quiz_submit 比较前 collapse_whitespace 归一化（本文件核心回归场景）
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


class TestCollapseWhitespace(_BaseCase):
    """database.collapse_whitespace 单元测试"""

    def test_lf_folded(self):
        self.assertEqual(
            self.db_mod.collapse_whitespace('different governments have\ndifferent'),
            'different governments have different')

    def test_crlf_folded(self):
        self.assertEqual(
            self.db_mod.collapse_whitespace('different governments have\r\ndifferent'),
            'different governments have different')

    def test_tab_and_multi_space_folded(self):
        self.assertEqual(
            self.db_mod.collapse_whitespace('a\t b   c'),
            'a b c')

    def test_leading_trailing_stripped(self):
        self.assertEqual(self.db_mod.collapse_whitespace('  hello \n'), 'hello')

    def test_none_and_empty_safe(self):
        self.assertEqual(self.db_mod.collapse_whitespace(''), '')
        self.assertEqual(self.db_mod.collapse_whitespace(None), '')

    def test_no_whitespace_unchanged(self):
        self.assertEqual(self.db_mod.collapse_whitespace('hello world'), 'hello world')


class TestMigrateStripNewlines(_BaseCase):
    """A 防线：存量数据清洗迁移"""

    def setUp(self):
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM word_lists")
        conn.commit()
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (1, 'L1', 'synonym')")
        conn.commit()
        conn.close()

    def _insert(self, english, synonyms, chinese='释义'):
        conn = self.db_mod.get_db()
        cur = conn.execute(
            "INSERT INTO words (list_id, english, chinese, synonyms) VALUES (1, ?, ?, ?)",
            (english, chinese, synonyms))
        wid = cur.lastrowid
        conn.commit()
        conn.close()
        return wid

    def test_newline_fields_cleaned(self):
        wid = self._insert(
            'official policies vary from one nation to the\nnext',
            'different governments have different\nattitudes')
        self.db_mod._migrate_strip_newlines(self.db_mod.get_db())
        conn = self.db_mod.get_db()
        row = conn.execute("SELECT english, synonyms FROM words WHERE id=?", (wid,)).fetchone()
        conn.close()
        self.assertEqual(row['english'], 'official policies vary from one nation to the next')
        self.assertEqual(row['synonyms'], 'different governments have different attitudes')

    def test_crlf_cleaned(self):
        wid = self._insert('a\r\nb', 'c\r\nd')
        self.db_mod._migrate_strip_newlines(self.db_mod.get_db())
        conn = self.db_mod.get_db()
        row = conn.execute("SELECT english, synonyms FROM words WHERE id=?", (wid,)).fetchone()
        conn.close()
        self.assertEqual(row['english'], 'a b')
        self.assertEqual(row['synonyms'], 'c d')

    def test_idempotent(self):
        self._insert('x\ny', 'z')
        for _ in range(3):
            conn = self.db_mod.get_db()
            self.db_mod._migrate_strip_newlines(conn)
            conn.close()
        conn = self.db_mod.get_db()
        row = conn.execute("SELECT english FROM words WHERE list_id=1").fetchone()
        conn.close()
        self.assertEqual(row['english'], 'x y')

    def test_conflict_dirty_row_deleted(self):
        """清洗后与已有干净行唯一冲突 → 删除脏行，保留干净行"""
        clean_id = self._insert('a b', 'syn_clean')
        self._insert('a\nb', 'syn_dirty')
        conn = self.db_mod.get_db()
        self.db_mod._migrate_strip_newlines(conn)
        rows = conn.execute("SELECT id, synonyms FROM words WHERE list_id=1").fetchall()
        conn.close()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['id'], clean_id)
        self.assertEqual(rows[0]['synonyms'], 'syn_clean')

    def test_clean_rows_untouched(self):
        wid = self._insert('normal word', 'normal syn')
        conn = self.db_mod.get_db()
        self.db_mod._migrate_strip_newlines(conn)
        row = conn.execute("SELECT english, synonyms FROM words WHERE id=?", (wid,)).fetchone()
        conn.close()
        self.assertEqual(row['english'], 'normal word')
        self.assertEqual(row['synonyms'], 'normal syn')


class TestImportTimeCleaning(_BaseCase):
    """B 防线：导入解析时清洗"""

    def test_excel_normalize_cell_folds_newline(self):
        from excel_parser import _normalize_cell
        self.assertEqual(_normalize_cell('different governments have\ndifferent'), 'different governments have different')
        self.assertEqual(_normalize_cell('a\r\nb\tc'), 'a b c')
        self.assertEqual(_normalize_cell(None), '')
        self.assertEqual(_normalize_cell(3.0), '3')

    def test_pdf_clean_table_rows_folds_newline(self):
        from pdf_parser import _clean_table_rows
        rows = [['word\nx', '释义\ng'], ['w2', 'c2']]
        cleaned = _clean_table_rows(rows)
        self.assertEqual(cleaned[0][0], 'word x')
        self.assertEqual(cleaned[0][1], '释义 g')


class TestGenerateQuestionsCleansNewlines(_BaseCase):
    """C 防线之一：generate_quiz_questions 输出不含换行"""

    def setUp(self):
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM word_lists")
        conn.commit()
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (1, 'L1', 'synonym')")
        # 4 个带 \n 的同义词词条（满足干扰项池下限）
        for i in range(4):
            conn.execute(
                "INSERT INTO words (list_id, english, chinese, synonyms) VALUES (1, ?, ?, ?)",
                (f'eng{i}\ntail{i}', f'释义{i}', f'syn{i}\ntail{i}'))
        conn.commit()
        conn.close()

    def test_correct_and_options_no_newline(self):
        conn = self.db_mod.get_db()
        wids = [r['id'] for r in conn.execute("SELECT id FROM words WHERE list_id=1").fetchall()]
        conn.close()
        questions = self.app_module.generate_quiz_questions(wids, 1, list_type='synonym')
        self.assertTrue(questions)
        for q in questions:
            self.assertNotIn('\n', q['correct'])
            self.assertNotIn('\r', q['correct'])
            for opt in q['options']:
                self.assertNotIn('\n', opt)
                self.assertNotIn('\r', opt)


class TestQuizSubmitCrlfTolerance(_BaseCase):
    """C 防线核心：模拟浏览器 CRLF 规范化后提交，应判对（直接复现用户 bug）"""

    def setUp(self):
        conn = self.db_mod.get_db()
        conn.execute("DELETE FROM words")
        conn.execute("DELETE FROM word_lists")
        conn.execute("DELETE FROM study_log")
        conn.commit()
        conn.execute("INSERT INTO word_lists (id, name, type) VALUES (1, 'L1', 'synonym')")
        for i in range(4):
            conn.execute(
                "INSERT INTO words (list_id, english, chinese, synonyms) VALUES (1, ?, ?, ?)",
                (f'eng{i}', f'释义{i}', f'syn{i}'))
        conn.commit()
        conn.close()
        self.client = self.app.test_client()

    def _seed_quiz_session(self, sess, correct_with_lf):
        """构造 quiz session：q['correct'] 含裸 LF（模拟存量脏数据生成的题目）"""
        token = self.app_module._save_quiz_data({
            'questions': [{
                'word_id': 1,
                'english': 'official policies vary from one nation to the next',
                'correct': correct_with_lf,
                'options': [correct_with_lf, 'syn1', 'syn2', 'syn3'],
            }],
            'word_ids': [1],
            'question_type': 'text',
        })
        sess['quiz_token'] = token
        sess['quiz_index'] = 1
        # 浏览器 newline normalization：LF → CRLF
        sess['quiz_answers'] = {'0': correct_with_lf.replace('\n', '\r\n')}
        sess['quiz_mode'] = 'test'
        sess['quiz_test_type'] = 'text'
        sess['current_list_id'] = 1

    def test_crlf_answer_judged_correct(self):
        correct_with_lf = 'different governments have\ndifferent attitudes'
        with self.client.session_transaction() as sess:
            self._seed_quiz_session(sess, correct_with_lf)
        resp = self.client.get('/quiz/submit', follow_redirects=False)
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        # 判对 → accuracy 100%，无错题详情
        self.assertIn('100%', html)
        self.assertNotIn('错题详情', html)

    def test_wrong_answer_still_wrong(self):
        """归一化不能放过真正的错误答案"""
        correct_with_lf = 'different governments have\ndifferent attitudes'
        with self.client.session_transaction() as sess:
            token = self.app_module._save_quiz_data({
                'questions': [{
                    'word_id': 1,
                    'english': 'eng0',
                    'correct': correct_with_lf,
                    'options': [correct_with_lf, 'syn1', 'syn2', 'syn3'],
                }],
                'word_ids': [1],
                'question_type': 'text',
            })
            sess['quiz_token'] = token
            sess['quiz_index'] = 1
            sess['quiz_answers'] = {'0': 'syn1'}  # 明确选错
            sess['quiz_mode'] = 'test'
            sess['quiz_test_type'] = 'text'
            sess['current_list_id'] = 1
        resp = self.client.get('/quiz/submit', follow_redirects=False)
        html = resp.get_data(as_text=True)
        self.assertIn('0%', html)
        self.assertIn('错题详情', html)


if __name__ == '__main__':
    unittest.main()
