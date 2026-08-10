## MODIFIED Requirements

### Requirement: 学习功能始终可用

学习功能 SHALL 在所有情况下保持可用，包括词库全部单词已被掌握时。选词逻辑 SHALL 优先从未掌握词中选取，未掌握词数量不足时用全词库补齐。

#### Scenario: 全部掌握后学习按钮仍可用

- **GIVEN** 当前词库全部单词 `status='mastered'`（`unmastered==0`）
- **WHEN** 首页渲染
- **THEN** "开始学习"按钮 SHALL 保持可用（非 disabled）
- **AND** 不显示"词库已全部掌握，去测试模式巩固吧"文案

#### Scenario: 全部掌握后 setup 页正常

- **GIVEN** 当前词库全部单词 `status='mastered'`（`unmastered==0`）
- **AND** 用户点击首页"开始学习"
- **WHEN** `/learn/setup` 渲染
- **THEN** 输入框 `max` SHALL 设为 `stats.total`（全词库数量）
- **AND** `default_n` SHALL 为 `min(20, stats.total)`
- **AND** 不显示"剩余仅 0 个"之类的误导提示

#### Scenario: 选词优先未掌握再补齐

- **GIVEN** 词库有 30 个词，其中 5 个 unmastered / 25 个 mastered
- **AND** 用户在 setup 选择"学 20 个"
- **WHEN** `learn_start` 执行
- **THEN** 选词池 SHALL 包含全部 5 个 unmastered 词
- **AND** 再从 25 个 mastered 词中补齐 15 个
- **AND** 去重后刚好 20 个词

#### Scenario: 全部掌握后选词来自全词库

- **GIVEN** 词库有 30 个词，全部 `status='mastered'`（`unmastered==0`）
- **AND** 用户在 setup 选择"学 10 个"
- **WHEN** `learn_start` 执行
- **THEN** 选词池 SHALL 从全词库 30 个词中随机抽取 10 个
- **AND** 正常创建 `learn_session`
- **AND** 正常进入学习翻卡流程
