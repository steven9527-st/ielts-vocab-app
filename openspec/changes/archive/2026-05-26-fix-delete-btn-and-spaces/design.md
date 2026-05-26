## Context

`pdf_parser.py` 使用正则 `([a-zA-Z][a-zA-Z\s\-]*?)` 提取英文单词，该正则允许内部空格以支持多词短语（如 `look after`）。但 PDF 文本提取常产生多余空格，导致解析结果如 `"GIVE  UP"`（双空格）。当前仅做 `.strip()` 处理尾部空格，未压缩中间连续空格。

删除词库按钮代码已在 `library.html:12` 就位，CSS 样式 `.btn--danger` 已定义（`:158-163`）。

## Goals / Non-Goals

**Goals:**
- PDF 解析的英文单词中，连续空白字符压缩为单个空格
- 删除按钮在重启后可见并正常工作

**Non-Goals:**
- 不修改正则本身（仍需支持多词短语）
- 不改变导入预览页的手动编辑逻辑

## Decisions

**使用 `re.sub(r'\s+', ' ', text)` 压缩空白**：在两处 english 提取后（成功匹配第 57 行、失败回退第 69 行）均增加空格压缩。选择 `re.sub` 而非 `' '.join(text.split())` 是因为后者会丢失原始空格语义——但此处两者效果等价，`re.sub` 更直观。

## Risks / Trade-offs

[多词短语误压] → 不影响：`'GIVE  UP'` → `'GIVE UP'`（正确）；`'LOOK AFTER'` → `'LOOK AFTER'`（不变）
