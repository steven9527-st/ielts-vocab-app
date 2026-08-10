## ADDED Requirements

### Requirement: 默写学习入口

当当前词库类型为 `'dictation'` 时，首页 SHALL 显示"默写学习"入口（替代标准学习入口）。用户点击后进入默写学习 setup 页。

#### Scenario: 默写词库首页入口

- **GIVEN** 当前词库 `type='dictation'`
- **WHEN** 首页渲染
- **THEN** 学习入口 SHALL 显示"默写学习"
- **AND** 点击进入 `/learn/dictation/setup`

#### Scenario: 非默写词库不显示默写入口

- **GIVEN** 当前词库 `type='standard'` 或 `'synonym'`
- **WHEN** 首页渲染
- **THEN** 不显示"默写学习"入口

### Requirement: 默写学习选词

默写学习 SHALL 只从当前词库中「未掌握（`status='unmastered'`）」的词里随机抽取指定数量。

#### Scenario: 已掌握词不被抽中

- **GIVEN** 默写词库有 20 个词，其中 5 个已 mastered
- **AND** 用户在默写 setup 页选择"学 15 个"
- **WHEN** `dictation_start` 执行选词
- **THEN** 系统 SHALL 只从剩下 15 个未掌握词中抽取

#### Scenario: 无可学词时引导

- **GIVEN** 默写词库所有词都已掌握
- **WHEN** 用户访问默写 setup 页
- **THEN** SHALL 展示引导文案（如「暂无可默写的单词」）
- **AND** 不提供"开始学习"按钮

### Requirement: 默写翻卡交互

默写卡片正面 SHALL 显示中文释义（大字），背面 SHALL 显示英文单词、音标、词性。用户通过翻面来对照自己的默写结果。

#### Scenario: 正面显示中文释义

- **GIVEN** 用户进入默写学习卡片
- **WHEN** 卡片渲染
- **THEN** 正面 SHALL 显示 `word.chinese`（大字、居中）
- **AND** 下方显示提示文字"根据中文默写英文，点击翻面查看"

#### Scenario: 背面显示英文

- **GIVEN** 用户已翻到卡片背面
- **WHEN** 背面渲染
- **THEN** SHALL 显示 `word.english`（大字）、`word.phonetic`、`word.pos`
- **AND** SHALL 提供 🔊 发音按钮
- **AND** SHALL 提供"显示拼写"区域（先隐藏，点击后显示完整单词供对照）

#### Scenario: 翻卡反复翻转

- **GIVEN** 用户在默写卡片页
- **WHEN** 用户点击卡片
- **THEN** 卡片 SHALL 在正反面之间切换
- **AND** 支持 Space 键切换

### Requirement: 默写学习前进/后退

默写学习 SHALL 支持前进/后退翻卡浏览，使用游标模型（`dict_index`）驱动，与现有学习流一致。

#### Scenario: 默认从第一张开始

- **GIVEN** 用户选择了 N 个词开始默写学习
- **WHEN** `dictation_start` 创建学习会话
- **THEN** session 中 `dict_word_ids` SHALL 存储 N 个词 ID 全集
- **AND** `dict_index` SHALL 初始化为 0
- **AND** 跳转到 `/learn/dictation/card` 显示第 1 张

#### Scenario: 前进到下一张

- **GIVEN** 用户在第 K 张（K < N）
- **WHEN** 用户点击"下一张"或按 → 键
- **THEN** `dict_index` SHALL 自增 1
- **AND** 进度计数器显示 "K+1 / N"

#### Scenario: 后退到上一张

- **GIVEN** 用户在第 K 张（K > 1）
- **WHEN** 用户点击"上一张"或按 ← 键
- **THEN** `dict_index` SHALL 自减 1（不低于 0）
- **AND** 渲染第 K-1 张卡片

#### Scenario: 首张时上一张无效

- **GIVEN** 用户在第 1 张
- **WHEN** 用户点击"上一张"或按 ← 键
- **THEN** `dict_index` SHALL 保持为 0
- **AND** 前端按钮 disabled

### Requirement: 默写学完自动进入测验

默写学习完最后一张后 SHALL 自动进入测验（复用 `learn_quiz` 路由），测验范围为本次学习的词。

#### Scenario: 学完最后一张跳测验

- **GIVEN** 用户在默写学习的最后一张卡片
- **WHEN** 用户点击"下一张"
- **THEN** 系统 SHALL 把 `dict_word_ids` 写入 `pending_quiz_word_ids`
- **AND** SHALL 写入 `pending_quiz_return_to='dictation_done'`
- **AND** SHALL 写入 `study_log(mode='learn_dictation', accuracy=1.0)`
- **AND** SHALL redirect 到 `/learn/quiz`

#### Scenario: 测验通关更新 mastered

- **GIVEN** 用户从默写学习进入测验并通关（accuracy=100%）
- **WHEN** `quiz_submit` 处理
- **THEN** SHALL 对本次学习的全部词执行 `UPDATE words SET status='mastered'`
- **AND** SHALL 写 `study_log(mode='quiz', accuracy=1.0)`

### Requirement: 默写学习完成页

默写学习完成后 SHALL 展示完成页，显示本次学习的单词数量。

#### Scenario: 完成页展示

- **GIVEN** 用户完成默写学习（含测验）
- **WHEN** 跳转到 `dictation_done`
- **THEN** 页面 SHALL 显示"本次共默写 N 个单词"
- **AND** 提供"返回首页"按钮
