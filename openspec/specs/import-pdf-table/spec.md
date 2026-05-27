# Spec: import-pdf-table


## ADDED Requirements

### Requirement: PDF 双路径分发

PDF 上传 SHALL 先尝试表格抽取路径；当且仅当表格路径未抽到任何有效表格时，回退到现有的编号词表（`_ENTRY_RE`）路径。

#### Scenario: 表格 PDF 上传

- **GIVEN** 用户上传一个含双列带边框表格的 PDF（如雅思 C4-Test1 同义词表）
- **WHEN** 后端调用 `pdfplumber.extract_tables()`
- **AND** 至少一页返回了 ≥2 行 ≥2 列的有效表格
- **THEN** 系统 SHALL 走表格路径
- **AND** 解析得到的 rows 列表 SHALL 写入 Excel 临时文件
- **AND** 浏览器 SHALL 跳转到 `/import/excel_mapping` 列映射页
- **AND** 现有 `_ENTRY_RE` 路径 SHALL 不被触发

#### Scenario: 编号词表 PDF 上传

- **GIVEN** 用户上传一个传统编号词表 PDF（每行以 `\d+\.` 开头）
- **WHEN** 后端调用 `pdfplumber.extract_tables()`
- **AND** 所有页都未返回任何有效表格
- **THEN** 系统 SHALL 降级到现有 `_ENTRY_RE` 编号词表路径
- **AND** 解析行为 SHALL 与未引入本变更前完全一致
- **AND** 浏览器 SHALL 跳转到 `/import/preview`

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
