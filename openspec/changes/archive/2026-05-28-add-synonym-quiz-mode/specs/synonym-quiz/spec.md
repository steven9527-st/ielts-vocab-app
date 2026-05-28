## ADDED Requirements

### Requirement: 同义词词库测验出题方式切换

学习测验与正式文字测试 SHALL 根据词库的 `type` 字段自动切换出题方式：

- `type='synonym'`：题目展示英文词，4 个选项均为英文同义词，正确答案为本词的 `synonyms` 字段
- `type='standard'`：题目展示英文词，4 个选项均为中文释义（既有行为）

#### Scenario: 标准词库使用中文选项

- **GIVEN** 词库 `word_lists.type = 'standard'`
- **WHEN** 用户进入学习测验或文字测试
- **THEN** 系统 SHALL 调用 `generate_quiz_questions()` 走原中文选项逻辑
- **AND** 每道题 4 个选项 SHALL 全部来自 `words.chinese` 字段

#### Scenario: 同义词词库使用英文同义词选项

- **GIVEN** 词库 `word_lists.type = 'synonym'`
- **AND** 该词库下有 ≥ 4 个词的 `synonyms` 字段非空
- **WHEN** 用户进入学习测验或文字测试
- **THEN** 系统 SHALL 走新出题逻辑：
  - 题目展示当前词的 `english`
  - 正确答案为当前词的 `synonyms`
  - 3 个干扰项从同词库其他词的 `synonyms` 中随机选取
- **AND** 4 个选项 SHALL 全部为英文文本

#### Scenario: 干扰项去重

- **GIVEN** 同义词词库测验出题
- **WHEN** 采集干扰项
- **THEN** 干扰项 SHALL 不与正确答案重复
- **AND** 多个干扰项之间 SHALL 不重复
- **AND** 同一道题中 4 个选项 SHALL 互不相同

#### Scenario: 干扰项不足时降级

- **GIVEN** 同义词词库内有同义词的词条总数 < 4（例如只有 3 个词带 synonyms）
- **WHEN** 测验出题
- **THEN** 系统 SHALL 自动降级为中文选项逻辑（同 `type='standard'`）
- **AND** 不应返回选项数 < 4 的题目，避免 UI 异常

#### Scenario: 听力测试豁免

- **GIVEN** 词库 `word_lists.type = 'synonym'`
- **WHEN** 用户进入听力测试（`question_type='audio'`）
- **THEN** 系统 SHALL 仍走中文选项逻辑（不切换为英文同义词选项）
- **AND** 听力测试体验保持"听英文 → 选中文"语义不变

#### Scenario: 学习测验内的错题循环保持一致

- **GIVEN** 用户在同义词词库的学习测验中答错若干题
- **WHEN** 进入错题循环（`/quiz/retry`）
- **THEN** 错题循环的新题目 SHALL 仍按 `type='synonym'` 出英文同义词选项
- **AND** 与首轮测验的出题方式保持一致

#### Scenario: 回退改答案不影响出题方式

- **GIVEN** 用户在同义词词库测验中已答到第 N 题
- **WHEN** 用户点「← 上一题」回退改答案（来自 `add-prev-navigation` 能力）
- **THEN** 回退后的题目 SHALL 维持英文同义词选项展示
- **AND** 选项内容 SHALL 与首次出题时一致（不重新随机）

### Requirement: 词库 type 字段持久化

`word_lists` 表 SHALL 包含 `type` 字段（值为 `'standard'` 或 `'synonym'`），表示词库的语义性质。该字段在词库创建时根据导入模式写入，作为测验出题逻辑的权威依据。

#### Scenario: 标准模式导入写入 type='standard'

- **GIVEN** 用户在 Excel 列映射页选择「标准模式」
- **WHEN** 路由 `/import/excel_apply` 创建词库
- **THEN** 新词库的 `word_lists.type` SHALL 写入 `'standard'`

#### Scenario: 同义词模式导入写入 type='synonym'

- **GIVEN** 用户在 Excel 列映射页选择「同义词模式」（无论是否启用双英文列）
- **WHEN** 路由 `/import/excel_apply` 创建词库
- **THEN** 新词库的 `word_lists.type` SHALL 写入 `'synonym'`

#### Scenario: 既有词库自动迁移

- **GIVEN** 用户升级到包含本能力的版本
- **AND** 数据库中存在 `type` 为 NULL 或默认 `'standard'` 的旧词库
- **WHEN** `init_db()` 执行迁移
- **THEN** 系统 SHALL 对每个旧词库扫描 `synonyms` 字段填充率
- **AND** 填充率 ≥ 80% 的词库 SHALL 被自动标记为 `'synonym'`
- **AND** 填充率 < 80% 的词库 SHALL 保持 `'standard'`
- **AND** 已显式标 `'synonym'` 的词库 SHALL 不被迁移逻辑覆盖

#### Scenario: 迁移幂等

- **GIVEN** 应用启动 N 次
- **WHEN** 每次 `init_db()` 执行迁移
- **THEN** 已正确分类的词库 SHALL 不被重复处理
- **AND** 不应产生多次 UPDATE 或副作用
