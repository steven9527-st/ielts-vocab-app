## Why

普通词库的学习流是「学完最后一张 → 自动进入测验 → 测验完成页」的完整闭环，让用户当场巩固刚学的单词。同义词词库目前学完最后一张直接跳到"学习完成"页，缺失了"学完即测"环节，体验上比普通流弱一截，也无法当场检验同义词记忆效果。

## What Changes

- 同义词学习流学完最后一张后，**自动跳转到测验**（复用已有的 `synonym-quiz` 能力，用本次学习的 `syn_word_ids` 作为测验范围）
- 测验完成后再进入「学习完成」页（保留现有的「再来一组 / 返回首页」按钮）
- 完成页 `synonym_done` 的 `study_log` 写入逻辑保持不变（仍记录 `learn_synonym` 模式，用于 streak / today_completed 统计）
- 测验环节本身的 `study_log` 由 `learn_quiz` 通用流程负责，无需额外改动

## Capabilities

### New Capabilities
<!-- 无新增 capability -->

### Modified Capabilities
- `synonym-flashcard`: 学完最后一张的跳转目标从「完成页」改为「测验页」，测验结束后再到完成页

## Impact

- 代码：`app.py` 中 `synonym_done` 前的跳转逻辑（`/learn/synonym/next` 等路由的"已学完"分支），需要插入"先跳 learn_quiz"环节；可能需要在 session 中标记"本次测验完成后回到 synonym_done"
- 复用：`generate_quiz_questions(list_type='synonym')` 已支持同义词测验模式（英文选项、听力豁免），不需要重复实现
- 数据：`study_log` 多一条 `learn_quiz` 记录（这是期望行为，和普通流一致）
- 测试：新增同义词学完即测的 e2e 测试；原有 `synonym_done` 直跳测试需要更新断言
