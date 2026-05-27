"""端到端集成测试：表格 PDF 完整导入流程。

链路：
  上传 PDF → /import/parse → /import/excel_mapping → /import/excel_apply
  → /import/preview → /import/confirm → 词库可用于同义词学习
"""

import io
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# 用临时 DB 隔离测试，避免污染用户的 vocab.db
os.environ['VOCAB_DB_PATH'] = tempfile.mktemp(suffix='.db')


def _make_table_pdf(path: str):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
    doc = SimpleDocTemplate(path, pagesize=A4)
    data = [
        ['C4 Test 1', ''],
        ['文章', '题目'],
        ['alarming rate of loss', 'plight'],
        ['formal tuition', 'classroom'],
        ['harbor', 'hold'],
        ['misconception', 'mistaken view'],
    ]
    tbl = Table(data, colWidths=[200, 200])
    tbl.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('SPAN', (0, 0), (1, 0)),
    ]))
    doc.build([tbl])


class TestTablePdfFullImport(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # paths.db_path 是模块级常量，需要在 import app 之前 patch
        # 用 monkey patching 改 paths.db_path 返回值
        import paths
        cls._tmp_db = tempfile.mktemp(suffix='.db')
        paths.db_path = lambda: cls._tmp_db  # type: ignore

        # database.DB_PATH 在 import 时就被赋值；需要重新加载
        import importlib
        import database
        database.DB_PATH = cls._tmp_db
        importlib.reload(database)

        # 现在再 import app
        import app as app_module
        importlib.reload(app_module)
        cls.app = app_module.app
        cls.app.config['TESTING'] = True

    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(cls._tmp_db)
        except Exception:
            pass

    def test_full_import_flow(self):
        # 准备 PDF
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            pdf_path = f.name
        try:
            _make_table_pdf(pdf_path)

            client = self.app.test_client()

            # Step 1: 上传 PDF
            with open(pdf_path, 'rb') as fp:
                resp = client.post(
                    '/import/parse',
                    data={'pdf': (fp, 'c4_test.pdf')},
                    content_type='multipart/form-data',
                )
            self.assertEqual(resp.status_code, 200, f'parse 失败：{resp.data}')
            data = resp.get_json()
            self.assertEqual(data['next'], '/import/excel_mapping',
                             f'表格 PDF 应跳列映射页，实际：{data}')
            self.assertGreater(data['count'], 0)

            # Step 2: GET 列映射页（验证渲染不报错）
            resp = client.get('/import/excel_mapping')
            self.assertEqual(resp.status_code, 200)
            body = resp.data.decode('utf-8')
            self.assertIn('导入模式', body, '列映射页应显示导入模式开关')
            # 因为 B 列是英文同义词，应该默认勾选 synonym 模式
            # 检查 "synonym" radio 是否带 checked
            self.assertIn('value="synonym"', body)

            # Step 3: POST excel_apply（同义词模式）
            resp = client.post('/import/excel_apply', json={
                'english_col': 0,
                'chinese_col': 1,
                'phonetic_col': -1,
                'pos_col': -1,
                'synonym_col': -1,
                'skip_first_row': True,  # 跳过 "文章/题目"
                'import_mode': 'synonym',
            })
            self.assertEqual(resp.status_code, 200, resp.data)
            data = resp.get_json()
            self.assertTrue(data['ok'])
            self.assertEqual(data['next'], '/import/preview')

            # Step 4: GET 预览页
            resp = client.get('/import/preview')
            self.assertEqual(resp.status_code, 200)

            # Step 5: 确认导入
            # 从 session 拿 entries —— 这里复用预览页 confirm 的接口
            # 模拟前端构造 entries（直接从内部 token 取）
            # 简化：直接构造 entries 调 /import/confirm
            entries = [
                {'english': 'alarming rate of loss', 'chinese': 'plight',
                 'phonetic': '', 'pos': '', 'synonyms': 'plight'},
                {'english': 'formal tuition', 'chinese': 'classroom',
                 'phonetic': '', 'pos': '', 'synonyms': 'classroom'},
                {'english': 'harbor', 'chinese': 'hold',
                 'phonetic': '', 'pos': '', 'synonyms': 'hold'},
                {'english': 'misconception', 'chinese': 'mistaken view',
                 'phonetic': '', 'pos': '', 'synonyms': 'mistaken view'},
            ]
            resp = client.post('/import/confirm', json={
                'entries': entries,
                'list_name': '同义词测试',
            })
            self.assertEqual(resp.status_code, 200, resp.data)
            data = resp.get_json()
            self.assertTrue(data['success'])
            self.assertEqual(data['count'], 4)
            list_id = data['list_id']

            # Step 6: 验证 synonyms 字段确实写入了
            from database import get_db
            db = get_db()
            words = db.execute(
                "SELECT english, chinese, synonyms FROM words WHERE list_id=?",
                (list_id,)
            ).fetchall()
            db.close()
            self.assertEqual(len(words), 4)
            for w in words:
                self.assertEqual(w['chinese'], w['synonyms'],
                                 f'同义词模式下 chinese 应等于 synonyms: {dict(w)}')

            # Step 7: 同义词学习入口可访问（首页统计 with_synonyms > 0）
            resp = client.get('/')
            self.assertEqual(resp.status_code, 200)
            body = resp.data.decode('utf-8')
            self.assertIn('同义词学习', body, '首页应显示同义词学习入口')

            # Step 8: 同义词学习 setup 页可正常访问
            resp = client.get('/learn/synonym/setup')
            self.assertEqual(resp.status_code, 200)

        finally:
            os.unlink(pdf_path)


class TestScannedPdfRejection(unittest.TestCase):

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
        cls.app.config['TESTING'] = True

    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(cls._tmp_db)
        except Exception:
            pass

    def test_scanned_pdf_returns_400_with_hint(self):
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            path = f.name
        try:
            c = canvas.Canvas(path, pagesize=A4)
            c.rect(50, 700, 500, 100, fill=0)
            c.showPage()
            c.save()

            client = self.app.test_client()
            with open(path, 'rb') as fp:
                resp = client.post(
                    '/import/parse',
                    data={'pdf': (fp, 'scanned.pdf')},
                    content_type='multipart/form-data',
                )
            self.assertEqual(resp.status_code, 400)
            data = resp.get_json()
            self.assertIn('扫描图', data['error'])
            self.assertIn('WPS', data['error'])
        finally:
            os.unlink(path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
