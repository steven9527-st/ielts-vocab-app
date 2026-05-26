## Why

用户反馈两个问题：(1) 词库管理页看不到删除按钮（代码已存在，需确认重启后可见）；(2) PDF 导入的单词包含多余空格（如 `"GIVE  UP"` 应为 `"GIVE UP"`），影响显示和匹配。

## What Changes

- **PDF 解析空格压缩**：`pdf_parser.py` 解析英文单词时，将连续多个空格压成单个空格
- **删除按钮确认**：`library.html` 删除词库按钮代码已存在于第 12 行，需确保重启后生效

## Capabilities

### New Capabilities
- `compress-word-spaces`: PDF 解析时清理英文单词中的多余空白字符

### Modified Capabilities
（无）

## Impact

- `pdf_parser.py`: 第 57 行和 69 行的 english 提取结果增加 `re.sub(r'\s+', ' ', ...)` 处理
- `library.html`: 无需修改（按钮已就位）
