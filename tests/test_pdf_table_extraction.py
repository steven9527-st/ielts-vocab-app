"""单元测试：pdf_parser 的表格抽取与文字层探测能力。

测试目标：
  • has_text_layer：扫描图 PDF（无文字层）应返回 False
  • extract_pdf_tables：表格 PDF 应返回正确 rows，且非数据行被剔除
  • extract_pdf_tables：编号词表 PDF 不应误命中（返回 None）

依赖：reportlab 仅在测试期使用，不进 requirements.txt。
"""

import os
import sys
import tempfile
import unittest

# 让本测试文件可独立执行：把项目根目录加入 sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from pdf_parser import has_text_layer, extract_pdf_tables  # noqa: E402


# ─────────────────────────────────────────
# 辅助：用 reportlab 构造测试 PDF
# ─────────────────────────────────────────

def _make_table_pdf(path: str):
    """生成一个含 C4 Test 1 标题 + 文章/题目表头 + 6 行数据的双列表格 PDF"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

    doc = SimpleDocTemplate(path, pagesize=A4)
    data = [
        ['C4 Test 1', ''],  # 标题行（左 cell 占一格，右空）
        ['文章', '题目'],
        ['alarming rate of loss', 'plight'],
        ['formal tuition', 'classroom'],
        ['harbor', 'hold'],
        ['misconception', 'mistaken view'],
        ['modification', 'change/transform/shift'],
        ['majority', 'most'],
    ]
    tbl = Table(data, colWidths=[200, 200])
    tbl.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('SPAN', (0, 0), (1, 0)),  # 标题跨两列
    ]))
    doc.build([tbl])


def _make_numbered_wordlist_pdf(path: str):
    """生成传统编号词表 PDF（无表格边框，纯文字）"""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(path, pagesize=A4)
    c.setFont('Helvetica', 11)
    lines = [
        "1. aback   adv. 大吃一惊",
        "2. abate   v. 减轻; 失效",
        "3. abandon vt. 放弃",
        "4. ability n. 能力",
        "5. above   prep. 在...之上",
    ]
    y = 800
    for line in lines:
        c.drawString(50, y, line)
        y -= 20
    c.showPage()
    c.save()


def _make_image_only_pdf(path: str):
    """生成不含任何文字（仅图形）的 PDF — 模拟扫描图"""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(path, pagesize=A4)
    # 只画矩形和直线，不写任何文字
    c.rect(50, 700, 500, 100, fill=0)
    c.line(50, 600, 550, 600)
    c.line(50, 500, 550, 500)
    c.showPage()
    c.save()


# ─────────────────────────────────────────
# 测试用例
# ─────────────────────────────────────────

class TestHasTextLayer(unittest.TestCase):

    def test_text_pdf_returns_true(self):
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            path = f.name
        try:
            _make_numbered_wordlist_pdf(path)
            self.assertTrue(has_text_layer(path))
        finally:
            os.unlink(path)

    def test_image_only_pdf_returns_false(self):
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            path = f.name
        try:
            _make_image_only_pdf(path)
            self.assertFalse(has_text_layer(path))
        finally:
            os.unlink(path)


class TestExtractPdfTables(unittest.TestCase):

    def test_table_pdf_returns_clean_rows(self):
        """表格 PDF 应正确返回行，且非数据行被剔除"""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            path = f.name
        try:
            _make_table_pdf(path)
            rows = extract_pdf_tables(path)

            self.assertIsNotNone(rows)
            assert rows is not None  # 类型断言，方便 IDE
            # 标题"C4 Test 1"（单 cell）应被剔除
            for r in rows:
                self.assertNotIn('C4 Test 1', r)

            # 表头行可能保留（由后续 looks_like_header 判定），但数据行必须在
            joined = [' | '.join(r) for r in rows]
            self.assertTrue(any('alarming rate of loss' in s for s in joined))
            self.assertTrue(any('plight' in s for s in joined))
            self.assertTrue(any('misconception' in s for s in joined))
            self.assertTrue(any('mistaken view' in s for s in joined))

            # 所有行列数应一致（_clean_table_rows 已对齐）
            widths = {len(r) for r in rows}
            self.assertEqual(len(widths), 1, f'列数不一致: {widths}')

        finally:
            os.unlink(path)

    def test_numbered_wordlist_pdf_returns_none(self):
        """编号词表 PDF（无边框）应返回 None，避免误命中"""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            path = f.name
        try:
            _make_numbered_wordlist_pdf(path)
            rows = extract_pdf_tables(path)
            self.assertIsNone(rows, f'编号词表 PDF 不应抽到表格，但拿到: {rows}')
        finally:
            os.unlink(path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
