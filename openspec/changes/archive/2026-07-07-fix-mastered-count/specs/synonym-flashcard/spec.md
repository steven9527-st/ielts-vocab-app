## ADDED Requirements

### Requirement: 同义词学习通关时更新 mastered 状态

同义词学习流（`add-synonym-learn-quiz` 引入）在通关（`quiz_submit` 的 `is_synonym_flow` 分支，accuracy=1.0）时 SHALL 对本次学习会话的全部原始词 ID 执行 `UPDATE words SET status='mastered'`，对齐普通学习流的行为。

原始词 ID 来源：`session['quiz_original_word_ids']`（由 `learn_quiz` 进入同义词流时保存）。

#### Scenario: 通关后首页统计正确

- **GIVEN** 用户开始同义词学习 5 个词
- **AND** 学完并测验通关（accuracy=100%）
- **WHEN** 用户返回首页
- **THEN** 首页「已掌握」metric SHALL 至少 +5（相对本次学习前）

#### Scenario: 不通关不标 mastered

- **GIVEN** 用户开始同义词学习 5 个词并进入测验
- **AND** 测验准确率 < 100%（未通关）
- **AND** 用户放弃测验（点「放弃测验」按钮）
- **WHEN** 检查 `words.status`
- **THEN** 这 5 个词的 status SHALL 保持 `unmastered`（未标 mastered）
