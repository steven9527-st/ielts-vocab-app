## MODIFIED Requirements

### Requirement: PDF 双路径分发

PDF 上传 SHALL 先尝试编号词表路径（`parse_pdf` 配合 `_ENTRY_RE`）；当且仅当编号词表路径命中率不足时，回退到表格抽取路径（`extract_pdf_tables`）。这与之前"先表格、后编号"的顺序相反，目的是优先采用结构化字段更精准的 `_ENTRY_RE` 路径。

#### Scenario: 编号词表 PDF 命中率达标

- **GIVEN** 用户上传一份编号词表 PDF（每行以 `\d+\.` 开头）
- **WHEN** 后端先调 `parse_pdf`
- **AND** 成功解析的非 failed entries 数 ÷ 总 entries 数 ≥ 30%
- **AND** 总 entries 数 ≥ 5
- **THEN** 系统 SHALL 采用 `parse_pdf` 的结果
- **AND** `extract_pdf_tables` SHALL 不被触发
- **AND** 浏览器 SHALL 跳转到 `/import/preview`

#### Scenario: 带表格线的编号词表 PDF

- **GIVEN** 用户上传一份**带表格线**的编号词表 PDF（如典型雅思教材风格：序号列/单词列/音标列/释义列四列带边框）
- **AND** `extract_pdf_tables` 能命中表格抽取
- **WHEN** 后端先调 `parse_pdf`
- **AND** `_ENTRY_RE` 命中率 ≥ 30%
- **THEN** 系统 SHALL 优先采用 `parse_pdf` 的结果
- **AND** 入库后每条词条的 `english` 字段 SHALL 是真正的英文单词（而不是序号 `"1."` / `"2."`）

#### Scenario: 表格 PDF（无编号格式）回退到表格路径

- **GIVEN** 用户上传一份双列同义词词库 PDF（如 C4 Test 1 风格：英文短语 / 英文同义词）
- **AND** PDF 无 `\d+\.` 编号格式
- **WHEN** 后端先调 `parse_pdf`
- **AND** `_ENTRY_RE` 命中率 < 30%（或总 entries 数 < 5）
- **THEN** 系统 SHALL 回退到 `extract_pdf_tables`
- **AND** 若 `extract_pdf_tables` 抽到表格，浏览器 SHALL 跳转到 `/import/excel_mapping`

#### Scenario: 编号词表 PDF 同时被表格抽取命中（重点保护场景）

- **GIVEN** 一份编号词表 PDF 既能被 `parse_pdf` 高质量解析（命中率 ≥ 30%）
- **AND** 也能被 `extract_pdf_tables` 抽取出表格
- **WHEN** 后端走双路径分发
- **THEN** 系统 SHALL 选择 `parse_pdf` 的结果（不被表格路径"截胡"）
- **AND** 这是本变更修复的核心 bug 场景

#### Scenario: 两条路径都失败

- **GIVEN** 一份完全不像词表的 PDF（如普通文档）
- **WHEN** 后端走双路径分发
- **AND** `parse_pdf` 命中率 < 30% 或 entries 数 < 5
- **AND** `extract_pdf_tables` 也返回 None
- **THEN** 系统 SHALL 返回 `parse_pdf` 的原始结果（可能是空 entries）
- **AND** 浏览器 SHALL 跳转到预览页，用户可看到空数据并自行决定下一步
