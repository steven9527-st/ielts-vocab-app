## ADDED Requirements

### Requirement: 测验题目级双向流转

学习测验（`mode='learn'`）与正式测试（`mode='test'`，含文字与听力两种 `question_type`）的题目页 SHALL 支持用户在已加载的题目序列内前进与后退。后端 SHALL 维护 `quiz_index` 游标，支持自增与自减；用户提交答案后游标自增，点击「上一题」时游标自减。

#### Scenario: 默认从第一题开始

- **GIVEN** 用户从 `/learn/quiz` 或 `/test/setup` 提交进入测验
- **WHEN** 后端创建 quiz_token 与题目集
- **THEN** `session['quiz_index']` SHALL 初始化为 0
- **AND** `session['quiz_answers']` SHALL 为空字典
- **AND** 跳转到 `/quiz/question` 显示第 1 题，计数器显示 "1 / Total"

#### Scenario: 选择答案后自动前进

- **GIVEN** 用户当前在第 K 题（`quiz_index = K - 1`）
- **WHEN** 用户点击某个选项并提交
- **THEN** 后端 SHALL 把选择写入 `session['quiz_answers'][str(K-1)]`
- **AND** `quiz_index` SHALL 自增 1
- **AND** 跳转到第 K+1 题；若 K == Total 则跳转到 `/quiz/submit`

#### Scenario: 点击「上一题」后退

- **GIVEN** 用户当前在第 K 题（`quiz_index = K - 1`）且 K > 1
- **WHEN** 用户点击「← 上一题」按钮或按 ← 键
- **THEN** 后端 SHALL 将 `quiz_index` 自减 1
- **AND** 跳转回第 K-1 题
- **AND** 该题对应的 radio 选项 SHALL 自动预选回 `session['quiz_answers'][str(K-2)]` 中保存的答案

#### Scenario: 回退后修改答案

- **GIVEN** 用户在第 K-1 题原先选了选项 A
- **AND** 已通过「上一题」回到第 K-1 题
- **WHEN** 用户改选选项 B 并提交
- **THEN** `session['quiz_answers'][str(K-2)]` SHALL 覆盖为 B
- **AND** 最终成绩按覆盖后的答案计算

#### Scenario: 第一题时「上一题」无效

- **GIVEN** 用户当前在第 1 题（`quiz_index = 0`）
- **WHEN** 用户点击「← 上一题」按钮或按 ← 键
- **THEN** 后端 SHALL 不改变 `quiz_index`
- **AND** 前端按钮 SHALL 处于灰显（disabled）状态
- **AND** ← 键事件 SHALL 静默忽略

#### Scenario: 进度计数显示「最大已达进度」

- **GIVEN** 用户曾经前进到过第 K 题（`quiz_max_reached = K`）后回退到第 J 题（J < K）
- **WHEN** 题目页渲染
- **THEN** 计数器 SHALL 显示 "K / Total"，而非 "J / Total"
- **AND** 用户再次前进到第 K+1 题时，`quiz_max_reached` SHALL 更新为 K+1

#### Scenario: 听力测试模式回退不自动重播

- **GIVEN** 用户在听力测试模式（`question_type='listening'`）的第 K 题
- **WHEN** 用户通过「上一题」回退到第 K-1 题
- **THEN** 系统 SHALL 不自动调用 `speakWord()` 播放该题的音频
- **AND** 用户需主动点击 🔊 按钮才重新听音

#### Scenario: 提交测验清理回退状态

- **GIVEN** 用户在最后一题（第 Total 题）提交答案
- **WHEN** 后端跳转到 `/quiz/submit`
- **THEN** 系统 SHALL 计算最终成绩（基于 `quiz_answers` 当前快照）
- **AND** `session['quiz_index']` `session['quiz_answers']` `session['quiz_max_reached']` `session['quiz_token']` SHALL 被清除

#### Scenario: 错题循环模式同样支持回退

- **GIVEN** 学习测验结束后用户进入错题循环（`/quiz/retry`）
- **WHEN** 新一轮 quiz_index 与 quiz_answers 被重置
- **THEN** 错题循环内的题目流转 SHALL 与正常测验一致，支持「上一题」回退与改答案

#### Scenario: 中途放弃测验清理状态

- **GIVEN** 用户在测验中关闭页面或导航离开
- **WHEN** 用户下次进入新测验（任意 mode）
- **THEN** 旧的 `quiz_max_reached` 临时状态 SHALL 在新 quiz_token 生成时被清除，不污染新一轮测验
