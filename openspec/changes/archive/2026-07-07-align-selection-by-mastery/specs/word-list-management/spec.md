## ADDED Requirements

### Requirement: 测试模式只从已掌握词中选取

测试模式（`test_start`，含文字测试和听力测试）SHALL 只从当前词库中「已掌握（`status='mastered'`）」的词里随机抽题，让测试专注于验证/巩固既有记忆。

#### Scenario: 只测已掌握词

- **GIVEN** 词库有 30 个词，其中 12 个 mastered / 18 个 unmastered
- **AND** 用户在测试 setup 页选择"测 10 题"
- **WHEN** `test_start` 执行
- **THEN** 系统 SHALL 只从 12 个 mastered 词中随机抽 10 个作为题目
- **AND** 10 个题目对应的 word_id 全部对应 `status='mastered'` 的词

#### Scenario: 已掌握词不足 4 个时拦截

- **GIVEN** 词库总 30 词，但 mastered 只有 3 个
- **WHEN** 用户访问 `test_setup`
- **THEN** setup 页 SHALL 显示引导文案「当前词库已掌握词不足 4 个，请先去学习一些单词再来测试」
- **AND** SHALL 提供"返回首页"或"去学习"按钮
- **AND** 不显示题数输入和"开始测试"按钮

#### Scenario: 干扰项来自全词库不变

- **GIVEN** 测试题目本身从 mastered 池选取
- **WHEN** `generate_quiz_questions` 生成题目的 4 选 1
- **THEN** 干扰项 SHALL 仍从全词库随机选取（保留既有行为）
- **AND** 不受 status 限制，保证选项池充足

### Requirement: get_list_stats 补充"未掌握且含同义词"字段

`get_list_stats(list_id)` 返回值 SHALL 新增字段 `unmastered_with_synonyms`（`status='unmastered' AND synonyms 非空` 的词数），供同义词学习 setup 页作为题数上限和文案数据源。

#### Scenario: 新字段计算

- **GIVEN** 词库有 100 个词
  - 其中 60 个 mastered
  - 40 个 unmastered
  - 60 个含 synonyms（其中 40 个 mastered、20 个 unmastered）
- **WHEN** 调用 `get_list_stats(list_id)`
- **THEN** 返回 dict SHALL 包含
  - `total: 100`
  - `mastered: 60`
  - `unmastered: 40`
  - `with_synonyms: 60`
  - `unmastered_with_synonyms: 20`（新增字段）
