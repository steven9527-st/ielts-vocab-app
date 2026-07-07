## ADDED Requirements

### Requirement: 同义词学习只从未掌握词中选取

同义词学习流（`synonym_start`）SHALL 只从当前词库中「未掌握（`status='unmastered'`）且含同义词（`synonyms` 非空）」的词里随机抽取指定数量，避免用户重复学习已掌握的词。

#### Scenario: 已掌握词不被抽中

- **GIVEN** 词库有 20 个含同义词的词，其中 5 个已 mastered
- **AND** 用户在同义词学习 setup 页选择"学 15 个"
- **WHEN** `synonym_start` 执行选词
- **THEN** 系统 SHALL 只从剩下 15 个未掌握词中抽取
- **AND** 抽中的 15 个词 `status` 全部为 `unmastered`

#### Scenario: 未掌握词不足时按实际数量选取

- **GIVEN** 词库有 20 个含同义词的词，其中 18 个已 mastered
- **AND** 用户请求学 15 个
- **WHEN** `synonym_start` 执行选词
- **THEN** 系统 SHALL 只抽出实际的 2 个未掌握词
- **AND** 正常进入学习流程

#### Scenario: 所有含同义词的词都已掌握时

- **GIVEN** 词库所有含同义词的词都已掌握
- **WHEN** 用户访问 `synonym_setup`
- **THEN** setup 页 SHALL 展示引导文案（如「暂无可学的同义词单词，去测试模式复习吧」）
- **AND** 不提供"开始学习"按钮
