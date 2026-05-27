"""单元测试：PDF 双路径分发顺序（修复 fix-pdf-import-route-priority）

核心场景：
  • 带表格线的编号词表 PDF —— 必须走 _ENTRY_RE 而非表格抽取
    （这是 5/27 修复的主 bug：用户的「雅思阅读高分词汇.pdf」）
  • 不含编号格式的表格 PDF —— 仍应走表格抽取路径（同义词词库场景不退化）
"""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# 用临时 DB 隔离测试
os.environ['VOCAB_DB_PATH'] = tempfile.mktemp(suffix='.db')


def _make_numbered_table_pdf(path: str):
    """生成「带表格线 + 编号格式」的 PDF，模拟用户雅思词表。

    布局（4 列带边框）：
      ┌─────┬──────────┬──────────────┬────────────────────┐
      │ 序号 │  单词    │   音标       │  词性及中文含义     │
      ├─────┼──────────┼──────────────┼────────────────────┤
      │  1. │  aback   │ 英 [ə'bæk]   │ adv. 大吃一惊       │
      │  2. │  abate   │ 英 [əˈbeɪt]  │ v. 减轻              │
      │ ... │  ...     │ ...          │ ...                 │
      └─────┴──────────┴──────────────┴────────────────────┘

    注意：必须保证 extract_text() 后每行能被 _ENTRY_RE 匹配
    （即整行连起来是 "1. aback 英 [ə'bæk] adv. 大吃一惊"）
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

    doc = SimpleDocTemplate(path, pagesize=A4)
    data = [
        ['序号', '单词', '音标', '词性及中文含义'],
        ['1.', 'aback', "[e'baek]", 'adv. da chi yi jing'],
        ['2.', 'abate', "[e'beIt]", 'v. jian qing'],
        ['3.', 'abnormal', "[eb'no:m(e)l]", 'adj. bu zheng chang de'],
        ['4.', 'abolish', "[e'bOlIS]", 'vt. fei chu'],
        ['5.', 'abrupt', "[e'brApt]", 'adj. tu ran de'],
        ['6.', 'absence', "['aebs(e)ns]", 'n. que xi'],
        ['7.', 'absolute', "['aebs(e)lu:t]", 'adj. jue dui de'],
        ['8.', 'absorb', "[eb'so:b]", 'vt. xi shou'],
        ['9.', 'abstract', "['aebstraekt]", 'adj. chou xiang de'],
        ['10.', 'absurd', "[eb'se:d]", 'adj. huang miu de'],
    ]
    tbl = Table(data, colWidths=[40, 80, 100, 200])
    tbl.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    doc.build([tbl])


def _make_synonym_table_pdf(path: str):
    """生成不含编号格式的双列同义词词库 PDF（add-pdf-table-import 场景）"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

    doc = SimpleDocTemplate(path, pagesize=A4)
    data = [
        ['Word', 'Synonym'],
        ['alarming rate of loss', 'plight'],
        ['formal tuition', 'classroom'],
        ['harbor', 'hold'],
        ['misconception', 'mistaken view'],
        ['modification', 'change'],
        ['majority', 'most'],
    ]
    tbl = Table(data, colWidths=[200, 200])
    tbl.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    doc.build([tbl])


class TestNumberedPdfPriority(unittest.TestCase):
    """带表格线的编号词表 PDF —— 必须走 _ENTRY_RE 路径"""

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

    def test_numbered_pdf_uses_entry_re_path(self):
        """带表格线的编号词表 PDF 应走 _ENTRY_RE 路径（跳预览页而非列映射页）"""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            pdf_path = f.name
        try:
            _make_numbered_table_pdf(pdf_path)

            client = self.app.test_client()
            with open(pdf_path, 'rb') as fp:
                resp = client.post(
                    '/import/parse',
                    data={'pdf': (fp, 'numbered.pdf')},
                    content_type='multipart/form-data',
                )
            self.assertEqual(resp.status_code, 200, resp.data)
            data = resp.get_json()

            # 关键断言：应跳 /import/preview（走老路径），而不是 /import/excel_mapping
            self.assertEqual(data['next'], '/import/preview',
                             f'编号词表 PDF 应该走 _ENTRY_RE 路径而非表格路径。实际返回：{data}')

            # entries 中第一条 english 应是 "aback"，不是 "1."
            entries = data.get('entries') or []
            self.assertTrue(entries, '应有解析结果')
            firsts = [e['english'] for e in entries[:3] if not e.get('failed')]
            self.assertIn('aback', firsts,
                          f'前 3 条 english 应包含 "aback"，实际：{firsts}')
            # 反向断言：序号不应被当成 english
            self.assertNotIn('1.', firsts,
                             f'序号 "1." 不应出现在 english 字段中：{firsts}')

        finally:
            os.unlink(pdf_path)


class TestSynonymPdfFallback(unittest.TestCase):
    """不含编号格式的表格 PDF —— 仍应走表格抽取路径（不退化）"""

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

    def test_synonym_pdf_still_uses_table_path(self):
        """无编号的双列表格 PDF 应回退到 extract_pdf_tables 走列映射页"""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            pdf_path = f.name
        try:
            _make_synonym_table_pdf(pdf_path)

            client = self.app.test_client()
            with open(pdf_path, 'rb') as fp:
                resp = client.post(
                    '/import/parse',
                    data={'pdf': (fp, 'synonym.pdf')},
                    content_type='multipart/form-data',
                )
            self.assertEqual(resp.status_code, 200, resp.data)
            data = resp.get_json()

            # 应跳列映射页（走 fallback 表格路径）
            self.assertEqual(data['next'], '/import/excel_mapping',
                             f'无编号表格 PDF 应回退到表格路径。实际：{data}')

        finally:
            os.unlink(pdf_path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
