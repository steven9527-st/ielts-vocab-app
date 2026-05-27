## Why

当前 PDF 导入仅支持「序号. 单词 英[音标] 词性+释义」格式的编号词表，但用户实际持有的相当一部分 PDF 是**表格形式的同义词词库**（如雅思 C4-Test1 风格的双列表："文章 / 题目"，左列是英文短语，右列是英文同义词）。这类 PDF 在现有 `pdf_parser.py` 下被 `_ENTRY_RE`（行首必须匹配 `\d+\.`）整页跳过，结果是上传后预览页空空，用户误以为"PDF 损坏"或"图片导致失败"。同时同义词学习功能刚上线，急需一条能批量导入同义词词库的链路。

## What Changes

- **新增 PDF 表格识别路径**：上传 PDF 后先尝试 `pdfplumber.extract_tables()`，命中表格则走"类 Excel"列映射流程；未命中则降级到现有 `_ENTRY_RE` 编号词表流程
- **新增导入模式开关**：列映射页增加单选「标准模式 / 同义词模式」。同义词模式下，"释义列"的内容会同时写入 `chinese` 和 `synonyms` 两个字段
- **放宽中文列识别**：当列内中文占比低时不再拒绝，而是把"非英文列那一列"作为释义列候选（保证英文-英文表格也能被自动猜中）
- **PDF 文字层探测**：上传后先检查是否含有可提取文字。若是扫描图 PDF（无文字层），返回明确错误提示，引导用户先用 WPS/Adobe 等工具预处理后再上传
- **多页表格合并**：PDF 中跨页的同结构表格自动合并到同一份 rows 列表，全部导入到同一个新词库
- **非数据行自动清洗**：识别并跳过单 cell 标题行（如 "C4 Test 1"）、表头行（如 "文章 / 题目 / Word / Synonym"）
- **不变更**现有 Excel/CSV 导入流程、不变更编号词表 PDF 解析、不变更数据库 Schema

## Capabilities

### New Capabilities
- `import-pdf-table`：从表格型 PDF 中抽取行列数据并复用列映射流程导入词库，包括文字层检测、跨页表格合并、非数据行清洗、扫描图 PDF 的兜底提示

### Modified Capabilities
- `import-excel`：列映射环节新增「导入模式」选项与同义词字段双写规则；中文列识别策略放宽以兼容英文-英文表格（如同义词词库）

## Impact

**代码：**
- `pdf_parser.py`：新增表格抽取入口函数（不动现有 `_ENTRY_RE` 逻辑）
- `excel_parser.py`：`apply_mapping` 新增 `import_mode` 参数；`guess_columns` 放宽中文列判定
- `app.py`：`/import/parse` 路由对 PDF 增加双路径分发；`/import/excel_apply` 透传 `import_mode`
- `templates/import_excel_mapping.html`：新增"导入模式"单选 UI
- `templates/import.html`：错误提示文案补充扫描图 PDF 引导

**依赖：** 无新增（`pdfplumber` 已在 `requirements.txt`，`extract_tables()` 是其内置能力）

**桌面打包：** 无影响（不引入大体积二进制依赖如 OCR）

**数据：** 无 Schema 变更；同义词模式下 `chinese` 和 `synonyms` 双写，与现有学习/测试/同义词学习路由全部兼容

**显式不做（Out of Scope）：**
- 不实现扫描图 PDF 的 OCR 识别（成本/隐私权衡后留作未来工作）
- 不支持表格 PDF 中嵌入图片的提取（图片不影响文字层抽取）
- 不实现"按页拆分为多个词库"的能力（用户明确选择全部合并）
