# 支持 Excel / CSV 导入词库

## Why

目前仅支持 PDF 导入，对于「网上下载的成品词表」「从其他单词 App 导出的列表」「自己整理的简单单词表」等更常见来源，用户必须先转格式。Excel/CSV 是这类词表最普遍的载体，应作为一等公民导入渠道。

## What Changes

新增 Excel / CSV 文件导入能力，与现有 PDF 导入并存，**预览校对、确认导入下游流程完全复用**。

- 导入页 (`/import`) 接受 `.xlsx / .xls / .csv / .pdf` 四种文件
- 后端按文件扩展名分发到不同解析器：
  - `.pdf` → 现有 `pdf_parser.parse_pdf()`（不变）
  - `.xlsx / .xls / .csv` → 新增 `excel_parser.parse_table()`
- **Excel/CSV 多 Sheet**：仅读取第一个 Sheet
- **列识别（方案 ①）**：
  - 用户在新增的"列映射"页选择**英文列**和**中文列**（必选两列）
  - **音标 / 词性自动识别**：根据列名匹配（`phonetic / 音标 / IPA / pronunciation` → 音标列；`pos / 词性 / part of speech` → 词性列），识别不到则留空
  - 自动检测"第一行是否为表头"（启发式：第一行单元格不含中文字符且看起来不像单词数据 → 视为表头）
  - 用户可手动勾选/取消"第一行是表头"
- 解析输出与 PDF 一致的 `[{english, chinese, phonetic, pos, failed}]`，进入相同的预览校对页
- 不实现"追加到现有词库"功能（确认导入仍然新建一个词库，与 PDF 流程一致）

## Impact

- **Affected specs**：新增 1 个 capability spec
  - `import-excel`：Excel / CSV 文件导入
- **Affected code**：
  - `requirements.txt`：新增 `openpyxl>=3.1`（CSV 用 Python 标准库 `csv`，xls 不强制支持）
  - `excel_parser.py`（**新增**）：统一 Excel / CSV 解析器
  - `app.py`：
    - `/import/parse` 增加文件类型分发逻辑
    - 新增 `/import/excel_mapping`（GET 渲染列映射页）和 `/import/excel_apply`（POST 应用映射 → 转换为 entries → 跳到预览页）
  - `templates/import.html`：`accept` 属性扩展、文案更新
  - `templates/import_excel_mapping.html`（**新增**）：列映射 UI
- **Breaking changes**：无
- **Non-goals**：
  - 不支持 `.xls`（老格式，需要 xlrd 且对中文编码处理麻烦）→ 仅在 UI 中支持 `.xlsx / .csv`
  - 不做"追加到现有词库"
  - 不做模板下载
  - 不读多个 Sheet
  - 不做"列含义全自由映射"（5 列下拉），用户只指定英文/中文两列
