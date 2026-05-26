# Proposal: 对齐词性与释义（模型 C 内联格式）

## Why

当前 PDF 解析后多词性条目的词性与释义对应关系完全丢失。

**问题示例**：
- `apprentice` → `pos="n.; vt."`、`chinese="学徒，徒弟; 新手; 使…做学徒"`
  → 用户无法判断"新手"是 n. 还是 vt. 的释义
- `calculate` → `pos="vt.; vi."`、`chinese="计算;估计;打算，计划;旨在"`
  → 4 个释义无法对应到 vt./vi.
- `auction` → `chinese="拍卖;; 拍卖;竞卖"` → 出现双分号，提示有缺失但说不清

**根因**：`pos` 和 `chinese` 是两个独立的扁平字符串，靠 `; ` 拼接，丢失了一一对应关系。

**额外发现的 PDF 解析问题**（来自 explore 阶段）：
- `addict` 的 `vt.` 释义被丢弃（在音标续行 `əˈdɪkt (for v.)] vt. 使沉溺` 中，未被识别）
- `survey` 的 `vt.; vi.` 释义被丢弃（同上 + 纯词性续行 `vi. 测量土地`）
- `appropriate` 的 `adj.` 词性被吃掉（在 `(for adj.` 中误当注释剥离）
- `addict` 提取的字符是 `v t .`（PDF 字符间插空），无法被词性正则识别

## What Changes

### 1. 数据格式：模型 C 内联

将 `chinese` 字段改为 **"词性 + 释义"内联** 格式，多词性用 ` | ` 分隔：

```
旧: pos="n.; vt."  chinese="学徒，徒弟; 新手; 使…做学徒"
新: pos="n.; vt."  chinese="n. 学徒，徒弟; 新手 | vt. 使…做学徒"
```

**单词性条目也加前缀**（统一格式）：
```
旧: pos="adj."  chinese="复杂的"
新: pos="adj."  chinese="adj. 复杂的"
```

**空释义忽略**：若某词性没有有效释义，整条不输出。

### 2. PDF 解析增强

- **续行类型 A**（音标残尾 + 词性 + 释义）：识别 `əˈdɪkt (for v.)] vt. 使沉溺` 这类
- **续行类型 B**（纯词性续行）：识别 `vi. 测量土地` 这类
- **`(for adj.)` 提取**：把 `(for adj.` 中的 `adj.` 当成有效词性而非注释丢弃
- **字符间空格修复**：`v t . 使 沉 溺` → `vt. 使沉溺`

### 3. 前端展示

flashcard / library / quiz 等模板渲染 `chinese` 时按 ` | ` split，每个词性一行展示。

## Impact

- **数据库 schema**：不变 ✅
- **修改文件**：
  - `pdf_parser.py`（核心解析逻辑）
  - `templates/flashcard.html`、`templates/library.html`、`templates/quiz.html` 等（渲染）
  - 可能增加 `static/style.css`（视觉样式）
- **数据迁移**：清空 words 表重新导入即可（已验证流程）
- **影响范围**：所有多词性词条（当前 121 条 → 预计 130+ 条）
