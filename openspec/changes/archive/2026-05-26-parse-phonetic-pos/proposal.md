## Why

PDF 导入时，原始词条包含音标和词性信息（如 `1. ABANDON 英[ə'bændən] v. 放弃；遗弃`），但当前解析器只提取 english 和 chinese，丢弃了 phonetic 和 pos。用户希望在单词卡片和学习界面中看到完整信息。

## What Changes

- **pdf_parser.py**：正则增加捕获组，提取英式音标和词性
- **database.py**：words 表新增 `phonetic` TEXT、`pos` TEXT 两列
- **app.py**：导入接口写入新字段，API 查询返回新字段
- **flashcard.html**：翻卡背面显示音标+词性
- **import_preview.html**：预览表增加音标/词性列，支持编辑
- **library.html**：单词列表显示音标和词性

## Capabilities

### New Capabilities
- `parse-phonetic-pos`: PDF 解析时完整提取音标和词性并入库展示

### Modified Capabilities
（无）

## Impact

- 数据库 schema 变更：words 表新增 2 列（需 ALTER TABLE 或重建）
- 已有数据的 phonetic/pos 为空字符串（向后兼容）
- 导入预览、词库管理、学习卡片、测验等全链路 UI 变更
