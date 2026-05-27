# Spec: import-pdf-table


## ADDED Requirements

### Requirement: PDF 双路径分发

PDF 上传 SHALL 先尝试编号词表路径（`parse_pdf` 配合 `_ENTRY_RE`）；当且仅当编号词表路径命中率不足时，回退到表格抽取路径（`extract_pdf_tables`）。目的是优先采用结构化字段更精准的 `_ENTRY_RE` 路径。

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

#### Scenario: 两条路径都失败

- **GIVEN** 一份完全不像词表的 PDF（如普通文档）
- **WHEN** 后端走双路径分发
- **AND** `parse_pdf` 命中率 < 30% 或 entries 数 < 5
- **AND** `extract_pdf_tables` 也返回 None
- **THEN** 系统 SHALL 返回 `parse_pdf` 的原始结果（可能是空 entries）
- **AND** 浏览器 SHALL 跳转到预览页，用户可看到空数据并自行决定下一步


### Requirement: PDF 文字层探测

上传 PDF 时系统 SHALL 检测是否包含可提取的文字层；扫描图 PDF SHALL 被明确拒绝并给出引导提示。

#### Scenario: 扫描图 PDF（无文字层）

- **GIVEN** 用户上传一个由扫描得到的 PDF（不含矢量文字）
- **WHEN** 后端读取所有页面字符
- **AND** 字符总数 < 10
- **THEN** 系统 SHALL 返回 400 错误
- **AND** 错误文案 SHALL 包含"看起来是扫描图"和"请先用 WPS / Adobe Acrobat 等工具将其转换为可选中文字的 PDF"的引导
- **AND** 系统 SHALL 不尝试任何 OCR 处理

#### Scenario: 文字层 PDF

- **GIVEN** 用户上传一个含可选中文字的 PDF
- **WHEN** 后端读取
- **THEN** 字符总数 SHALL ≥ 10
- **AND** 系统 SHALL 继续后续解析流程

### Requirement: 跨页表格合并

PDF 中跨多页的同结构表格 SHALL 被合并到同一份 rows 列表，全部导入到同一个新词库。

#### Scenario: 多页同结构表格

- **GIVEN** 用户上传一个 5 页的 PDF
- **AND** 每页都包含一个 2 列表格
- **WHEN** 后端抽取
- **THEN** 系统 SHALL flatten 所有页的所有表格行到同一个 rows 列表
- **AND** 后续列映射流程 SHALL 把所有数据导入到同一个新建词库

#### Scenario: 列数不一致的行

- **GIVEN** 多页表格中某些行的列数与主表不一致（如合并单元格产物）
- **WHEN** 系统对齐结构
- **THEN** 列数与最常见列数不一致的整行 SHALL 被剔除
- **AND** 剔除行 SHALL 不出现在预览页

### Requirement: 非数据行清洗

表格抽取后系统 SHALL 自动跳过非数据行（标题行、表头行、空行）。

#### Scenario: 单 cell 标题行

- **GIVEN** 表格首行是标题（如"C4 Test 1"），仅一个非空 cell，其余为空或不存在
- **WHEN** 系统清洗
- **THEN** 该行 SHALL 被剔除
- **AND** 不进入列映射页的预览

#### Scenario: 表头行命中

- **GIVEN** 第二行是表头（如`["文章", "题目"]`、`["Word", "Synonym"]`、`["单词", "释义"]`）
- **WHEN** `looks_like_header` 判定
- **THEN** 列映射页"第一行是表头"复选框 SHALL 默认勾选
- **AND** 应用映射时 SHALL 跳过该行

#### Scenario: 第一列为空的行

- **GIVEN** 某行第一列（英文列）为空
- **AND** 第二列有内容
- **WHEN** 应用映射
- **THEN** 该行 entries 的 `failed` 字段 SHALL 为 true
- **AND** 用户在预览校对页 SHALL 看到红色高亮，可手动补全或删除

### Requirement: 不引入新依赖

本能力 SHALL 仅依赖已在 `requirements.txt` 中的 `pdfplumber`，不新增任何第三方包。

#### Scenario: 依赖检查

- **GIVEN** 一份未变更的 `requirements.txt`
- **WHEN** 用户拉取本变更后运行 `pip install -r requirements.txt`
- **THEN** 不应出现任何新的依赖
- **AND** 桌面打包后的 app 体积 SHALL 不显著增加（< 5MB 浮动）
