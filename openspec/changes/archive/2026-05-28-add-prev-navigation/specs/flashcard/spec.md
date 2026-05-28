## ADDED Requirements

### Requirement: 翻卡学习会话内前进与后退

翻卡学习会话 SHALL 支持用户在已加载的卡片序列内双向流转：通过「下一张」前进到下一个未学卡片，通过「上一张」回退到任意已学过的卡片重新查看。后端 SHALL 以「卡片全集 + 当前位置游标」状态模型驱动，确保前进/后退状态对称。

#### Scenario: 默认从第一张开始

- **GIVEN** 用户在学习设置页 (`/learn/setup`) 提交了今日学习量 N（如 20）
- **WHEN** 后端创建 learn_session
- **THEN** `word_ids` SHALL 存储抽取出来的 N 个单词 ID 全集
- **AND** `current_index` SHALL 初始化为 0
- **AND** 跳转到 `/learn/card` 显示第 1 张卡片，进度计数器显示 "1 / N"

#### Scenario: 点击「下一张」前进

- **GIVEN** 用户当前在第 K 张卡片（`current_index = K - 1`）且 K < N
- **AND** 卡片已翻到背面（`everFlipped = true`）
- **WHEN** 用户点击「下一张 →」按钮或按 → 键
- **THEN** 后端 SHALL 将 `current_index` 自增 1
- **AND** 进度计数器 SHALL 推进显示 "K+1 / N"
- **AND** 旧 `remaining_ids` 字段保留但不再作为权威数据源

#### Scenario: 点击「上一张」后退

- **GIVEN** 用户当前在第 K 张卡片（`current_index = K - 1`）且 K > 1
- **WHEN** 用户点击「← 上一张」按钮或按 ← 键
- **THEN** 后端 SHALL 将 `current_index` 自减 1
- **AND** 跳转回 `/learn/card` 显示第 K-1 张卡片
- **AND** 卡片 SHALL 从正面（英文）开始展示，需用户再次点击翻看背面

#### Scenario: 第一张时「上一张」无效

- **GIVEN** 用户当前在第 1 张卡片（`current_index = 0`）
- **WHEN** 用户点击「← 上一张」按钮或按 ← 键
- **THEN** 后端 SHALL 不改变 `current_index`
- **AND** 前端按钮 SHALL 处于灰显（disabled）状态
- **AND** ← 键事件 SHALL 静默忽略，不弹任何提示

#### Scenario: 最后一张点击「下一张」进入测验

- **GIVEN** 用户当前在第 N 张卡片（`current_index = N - 1`）
- **WHEN** 用户点击「下一张 →」按钮
- **THEN** 后端 SHALL 跳转到 `/learn/quiz` 生成测验
- **AND** learn_session.current_index SHALL 保留为 N-1（用于断点续传时回到测验阶段）

#### Scenario: 进度计数显示「最大已达进度」

- **GIVEN** 用户曾经前进到过第 K 张（`max_reached = K`）后回退到第 J 张（J < K）
- **WHEN** 卡片页渲染
- **THEN** 进度计数器 SHALL 显示 "K / N"，而非 "J / N"
- **AND** 用户再次前进到第 K+1 张时，计数器 SHALL 更新为 "K+1 / N"，`max_reached` SHALL 同步更新

#### Scenario: 断点续传保留游标位置

- **GIVEN** 用户已学到第 K 张关闭浏览器（learn_session.status='in_progress'）
- **WHEN** 用户再次访问首页点击「继续学习」(`/learn/continue`)
- **THEN** 后端 SHALL 从 learn_session 读取 `current_index` 并恢复到第 K 张
- **AND** `max_reached` SHALL 从 session 临时存储中读取（若过期则按 `current_index + 1` 初始化）

#### Scenario: 旧版会话兼容（无 current_index 字段）

- **GIVEN** 用户的 learn_session 由旧版应用创建，`current_index` 字段为 NULL
- **AND** 旧 `remaining_ids` 字段有数据
- **WHEN** 用户访问 `/learn/card` 或 `/learn/continue`
- **THEN** 后端 SHALL 计算 `current_index = len(word_ids) - len(remaining_ids)`
- **AND** 回填到数据库（lazy 迁移）
- **AND** 用户体验上无中断，进度位置准确恢复

#### Scenario: 放弃学习清理状态

- **GIVEN** 用户在学习中点击「放弃今日」(`/learn/abandon`)
- **WHEN** 后端处理 abandon
- **THEN** learn_session.status SHALL 标记为 'abandoned'
- **AND** Flask session 中的 `learn_max_reached` 临时键 SHALL 被清除
- **AND** `current_index` 不再被使用（无需清除 DB 字段）
