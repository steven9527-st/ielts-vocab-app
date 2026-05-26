## Why

PDF 词库中部分单词具有多个词性和对应释义（如 `complex adj. 复杂的 n. 情结`），但当前解析器 `_clean_meaning()` 只提取第一个词性，导致第二个及后续的词性和释义全部丢失或混入 chinese 字段。共影响 9 个条目，且其中 3 个（#1153 shelter, #1257 survey, #1266 swing）同时存在断字未修复的问题。

## What Changes

- **重写 `_clean_meaning()` 函数**：从 meaning_raw 中提取**所有** (pos, chinese) 对，而非仅第一个
  - 支持空格分隔模式：`adj. 复杂的 n. 情结`
  - 支持 `&` / `& vi.` 连接模式：`vt. & vi. 计算`
  - 输出扁平化格式：`pos="adj.; n."`, `chinese="复杂的; 情结"`
- **修复断字正则漏网**：#1153/#1257/#1266 的断字未被 `_BREAK_FIX_RE` 匹配（前缀 >3 字母或后缀含音标残留）
- **数据库无需改动**：words 表的 `pos`(TEXT) 和 `chinese`(TEXT) 字段已可容纳多词性内容

## Capabilities

### New Capabilities
- `multi-pos-extraction`: 从 PDF 单行词条中提取多词性和多释义的解析能力

### Modified Capabilities
- (无)

## Impact

- **pdf_parser.py**: 重写 `_clean_meaning()`, 增强 `_BREAK_FIX_RE`
- **database.py**: 无需改动
- **templates/**: 前端展示可能需要按分号拆分多词性（后续优化）
