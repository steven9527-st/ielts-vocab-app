## Why

当前翻卡学习、学习测验、正式测试三种模式都只能**单向前进**，用户一旦点错下一张 / 误选答案 / 想回头复习刚学过的单词，就**无法回退**——只能放弃整个 session 重来。这造成两类常见痛点：

1. **翻卡时一闪而过**：刚才那个生词没看清就被点没了，无法再回头看一眼
2. **答题误触**：题目还没读完就点了选项；或者答完后想回去改答案

对照成熟的背单词/答题类应用（百词斩、扇贝、网考），"上一题/上一张"是标配功能。补齐这个能力可显著提升学习体验，且对底层数据模型改动可控。

## What Changes

- **翻卡学习**（`/learn/card`）：左下角新增「← 上一张」按钮，已学过的卡片可回退查看，键盘 ← 键同步支持
- **学习测验**（`/learn/quiz` → `/quiz/question`）：题目页左下角新增「← 上一题」按钮，回退后可重新选择答案，最终成绩按最后一次提交计算
- **正式测试**（`/test/setup` → `/quiz/question`，test 模式）：同上，文字测试与听力测试均支持回退改答案
- **数据模型调整**：`learn_session.remaining_ids` 字段语义从"剩余未学"改为「全集 + 当前位置游标」，新增 `current_index` 字段（向后兼容旧 session）
- **进度计数策略**：进度计数器（`X / Total`）始终显示"已达到的最大值"，回退浏览不会让数字倒退（避免迷惑）
- **保留既有快捷键**：→ 键继续前进，← 键新增为后退

## Capabilities

### New Capabilities

- `quiz-navigation`: 学习测验与正式测试中题目级别的前进/后退/改答案能力（涵盖 4 选 1 文字题与听力题的双向流转）

### Modified Capabilities

- `flashcard`: 在既有"翻卡反复翻转"行为之外，新增"翻卡学习会话内前进/后退"Requirement——支持回退到任意已学过的卡片

## Impact

**后端**：
- `app.py`：改造 `/learn/card` / `/learn/next` 路由，新增 `/learn/prev` 路由；改造 `/quiz/question` / `/quiz/answer`，新增 `/quiz/prev` 路由
- `database.py`：`learn_session` 表新增 `current_index INTEGER DEFAULT 0` 字段（带迁移）
- `session` 字典：测验路径不再用 `quiz_index` 单调递增，改为支持回退；`quiz_answers` 字典化存储已能覆盖

**前端**：
- `templates/flashcard.html`：新增「← 上一张」按钮 + 键盘 ← 键监听 + 进度文案微调
- `templates/quiz.html`：新增「← 上一题」按钮 + 已选答案回填到 radio
- `templates/quiz_error.html`：错题循环页同步支持回退（错题循环复用相同 quiz_question 路由）

**测试**：
- 新增 `tests/test_prev_navigation.py`：覆盖翻卡回退、测验回退改答案、首张/末张边界、session 迁移兼容性

**风险**：
- 数据模型变更涉及旧用户的"进行中 session"——需要在 `learn_continue` 路由中加迁移逻辑，将旧 `remaining_ids` 推算出 `current_index`
- 测验改答案后最终分数计算逻辑变动微小（quiz_answers 本来就按 idx 存，覆盖即可），但需测试覆盖
