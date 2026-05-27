## Why

`add-pdf-table-import` 引入的「先表格、后编号词表」双路径分发存在两个互相叠加的设计缺陷，导致**带表格线的编号词表 PDF**（典型如雅思 3500 类教材）解析严重错位：

1. **分发顺序错**：`pdfplumber.extract_tables()` 对任何含表格线的 PDF 都会命中，但其输出质量天然差于 `_ENTRY_RE`——表格路径只能粗糙地把整列丢进 chinese 字段，而 `_ENTRY_RE` 能精准拆出 english / phonetic / pos / chinese 四个结构化字段
2. **`guess_columns` 英文列识别太天真**：把"ASCII 占比最高的列"等同于"英文列"，导致"序号列"（`1.`、`2.`、`3.`）被误选为英文列；真正的英文单词列（`aback`、`abate`）反而被忽略

实测复现：用户 144 页的「雅思阅读高分词汇.pdf」（带 4 列表格线：序号/单词/音标/词性及中文）—— Mac 旧版打包导入 1410 个正确词条；新版打包后 Mac/Win 重新导入都会得到 1911 条错位数据：english 字段是 `"12."` / `"13."`，单词列彻底丢失。

## What Changes

- **反转双路径分发顺序**：PDF 上传后**先**调 `parse_pdf`（`_ENTRY_RE`），命中率 ≥ 30% 则采用其结果直接跳预览页；命中率不足时**才**回退到 `extract_pdf_tables` 表格路径
- **加固 `guess_columns` 英文列识别**：新增"列内容必须像单词"的启发式（至少含若干 ≥2 字母的字母串），过滤"全数字+标点"的序号列
- **保持表格路径**作为同义词词库等场景的 fallback；扫描图 PDF 拒绝逻辑不变
- **新增回归测试**：以「雅思阅读高分词汇.pdf」的输出结构为基准断言修复正确性
- **不变更**数据库 Schema、UI 流程、Excel/CSV 导入路径、扫描图 PDF 处理

## Capabilities

### New Capabilities
（无）

### Modified Capabilities
- `import-pdf-table`：分发顺序调整为「编号词表优先、表格作为 fallback」；新增「编号词表命中率」判定阈值
- `import-excel`：`guess_columns` 英文列识别增加"像单词"启发式过滤，避免误选序号列

## Impact

**代码：**
- `app.py`：`/import/parse` PDF 分支重排顺序——先 `parse_pdf` 试，命中率不足才走 `extract_pdf_tables`
- `excel_parser.py`：`guess_columns` 英文列候选过滤 + 新增 `_looks_like_word_column` 辅助函数
- `pdf_parser.py`：`parse_pdf` 暴露/复用现有的"命中率"统计逻辑

**测试：**
- `tests/test_pdf_route_priority.py`：新增——用真实样本 PDF（暂时通过用户提供的 `雅思阅读高分词汇.pdf`，或抽取一页做 fixture）验证分发顺序
- `tests/test_excel_synonym_mode.py`：新增用例验证"序号列不被误选为英文列"

**依赖 / 打包：** 无新增依赖，需要重新打包 Win/Mac 分发（已知步骤）

**用户数据：** Windows 用户需要删掉已错误导入的词库后重新导入；Mac 用户的旧数据（5/26 用老版导入的）不受影响

**显式不做（Out of Scope）：**
- 不重构整个解析架构（只动分发顺序 + 列识别启发式两处）
- 不调整 `pdfplumber.extract_tables()` 的 `table_settings` 参数（成本高、收益不确定）
- 不引入"用户手动选择 PDF 类型"的 UI（双路径自动判断后不需要）
