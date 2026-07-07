## Why

用户在真实使用中发现两处"已掌握"数字统计不符合直觉：

**Bug 1（通关页）**：本次学习 20 个单词，首轮测验答对 18 个 / 答错 2 个，重做那 2 题后通关。通关页显示"本次学习的 **2** 个单词已全部标记为已掌握"，实际本次应算 **20** 个（前面已答对的 18 个也是本次学习的一部分）。

**Bug 2（首页 metric 卡）**：首页"已掌握"数字应该反映本词库累计掌握的所有词数，但同义词学习流通关的词从未被更新为 `mastered` 状态（`add-synonym-learn-quiz` change 中"不操作 words.status"的决策引入的回归）。用户当天通过同义词学习掌握了多个词，首页却只显示 2。

**用户需求延伸**：首页在"今日已通关 ✅"提示下方，增加"今日新增掌握 N 个"文本，让打卡进度看得见。

## What Changes

- **修复通关页数字**：`quiz_submit` 通关分支 SHALL 使用 `learn_session.word_ids`（学习会话的原始全集）计算 `total`、写入 `study_log`、UPDATE `words.status='mastered'`，而不是 `_load_quiz_data` 中被 `quiz_retry` 覆盖过的 `word_ids`（错题子集）
- **修复同义词流已掌握**：同义词学习流通关时（`quiz_submit` 的 `is_synonym_flow` 分支）SHALL 也执行 `UPDATE words SET status='mastered'`，对齐普通流行为
- **首页新增「今日新增掌握 N 个」文本**：仅在 `completed_today=True` 时显示，N 值来自今日 `study_log(mode IN ('learn', 'learn_synonym') AND accuracy=1.0)` 记录的 `word_ids` 去重合集词数
- **历史数据回补**：提供一次性迁移函数，扫 `study_log` 中所有 `learn_synonym` 且 `accuracy=1.0` 的记录，UPDATE 对应词为 `mastered`（补回本 bug 之前累积漏标的数据）

## Capabilities

### New Capabilities
- `mastery-tracking`: 定义单词"已掌握"状态的判定规则、通关流程的 mastered 更新时机、以及"今日新增掌握"统计能力

### Modified Capabilities
- `synonym-flashcard`: 同义词流通关时需 UPDATE words.status='mastered'（当前 spec 未涉及此点，改为 ADDED requirement）

## Impact

- 代码：`app.py` 的 `quiz_submit` 通关分支（普通流 + 同义词流）、`get_list_stats` 附近新增 `today_mastered_count()` 辅助函数、`index` 视图注入 `today_mastered_count` 变量
- 模板：`templates/index.html` 在「今日已通关」文案下增加数字展示
- DB：无 schema 变更；一次性迁移 UPDATE words.status（幂等）
- 测试：新增 5-8 个测试覆盖 retry 后 total 正确、同义词流 mastered、today count、历史迁移
