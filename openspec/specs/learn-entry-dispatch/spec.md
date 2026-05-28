# learn-entry-dispatch Specification

## Purpose
TBD - created by archiving change unify-learn-entry-by-list-type. Update Purpose after archive.
## Requirements
### Requirement: 首页「开始学习」按钮按词库 type 智能分发

首页 Dashboard 仅展示一个「开始学习」按钮（不再有独立的「同义词学习」按钮），按钮目标链接 SHALL 根据当前词库的 `type` 字段动态决定：

- `type='standard'` → 跳转到 `/learn/setup`（普通翻卡入口）
- `type='synonym'` → 跳转到 `/learn/synonym/setup`（同义词翻卡入口）

#### Scenario: 标准词库点击「开始学习」

- **GIVEN** 当前词库 `word_lists.type = 'standard'`
- **WHEN** 首页渲染
- **THEN** 「开始学习」按钮的 `href` SHALL 指向 `/learn/setup`

#### Scenario: 同义词词库点击「开始学习」

- **GIVEN** 当前词库 `word_lists.type = 'synonym'`
- **WHEN** 首页渲染
- **THEN** 「开始学习」按钮的 `href` SHALL 指向 `/learn/synonym/setup`

#### Scenario: 移除独立「同义词学习」按钮

- **GIVEN** 任何词库类型
- **WHEN** 首页渲染
- **THEN** 首页 SHALL 不再渲染独立的「同义词学习」按钮
- **AND** `stats.with_synonyms` 字段不再驱动任何按钮可见性

### Requirement: 「继续上次学习」按钮按词库 type 分发

「继续上次学习」按钮 SHALL 在用户存在任一种进行中的学习 session（普通 `learn_session` 或同义词 `syn_queue`）时可见，链接目标根据当前词库 type 决定：

- `type='standard'` → `/learn/continue`
- `type='synonym'` → `/learn/synonym/setup`（同义词进度在 Flask session 中天然恢复）

#### Scenario: 标准词库有进行中 learn_session

- **GIVEN** 当前词库 `type='standard'` 且存在 `learn_session.status='in_progress'`
- **WHEN** 首页渲染
- **THEN** 「继续上次学习」按钮 SHALL 可见
- **AND** `href` 指向 `/learn/continue`

#### Scenario: 同义词词库有进行中 syn_queue

- **GIVEN** 当前词库 `type='synonym'` 且 Flask session 内 `syn_queue` 非空
- **WHEN** 首页渲染
- **THEN** 「继续上次学习」按钮 SHALL 可见
- **AND** `href` 指向 `/learn/synonym/setup`

#### Scenario: 当日已通关时不显示「继续上次学习」

- **GIVEN** 用户当日已完成学习（`today_completed = True`）
- **WHEN** 首页渲染
- **THEN** 「继续上次学习」按钮 SHALL 不显示
- **AND** 「今日已通关 ✅」徽章 SHALL 显示

### Requirement: 同义词学习计入 streak 与 study_log

同义词学习完成（用户翻完所有同义词卡片）时，系统 SHALL 写入 `study_log` 记录（`mode='learn_synonym'`），并被 `calc_streak()` 与 `today_completed()` 函数纳入统计，与普通学习地位等同。

#### Scenario: 同义词学习完成写入 study_log

- **GIVEN** 用户在同义词学习中翻完所有卡片，跳转到 `/learn/synonym/done`
- **WHEN** `synonym_done` 路由处理
- **THEN** 系统 SHALL 在 `study_log` 表插入一条记录
  - `mode='learn_synonym'`
  - `accuracy=1.0`
  - `word_ids` 为本次学习的同义词 word_id 列表
  - `duration_s` 为开始到完成的秒数（无法计算则为 0）
- **AND** 写入失败 SHALL 仅记 warning log，不阻塞页面跳转

#### Scenario: calc_streak 包含 learn_synonym

- **GIVEN** 用户某日完成同义词学习（study_log 有 `mode='learn_synonym'` 记录）
- **WHEN** `calc_streak()` 计算连续学习天数
- **THEN** SHALL 把含 `learn_synonym` 的日期纳入 streak 计算
- **AND** 与普通 `learn` mode 同等地位

#### Scenario: today_completed 包含 learn_synonym

- **GIVEN** 当前词库为同义词词库且用户今日已完成一轮同义词学习
- **WHEN** 首页查询 `today_completed(list_id)`
- **THEN** SHALL 返回 True
- **AND** 「今日已通关 ✅」徽章正常显示

### Requirement: 同义词学习启动时记录开始时间

同义词学习启动时 SHALL 在 Flask session 中记录开始时间戳，用于 `synonym_done` 计算学习时长。

#### Scenario: synonym_start 设置 syn_started_at

- **GIVEN** 用户在同义词学习设置页点击「开始」
- **WHEN** `synonym_start` 路由处理（成功创建 syn_queue 后）
- **THEN** SHALL 设置 `session['syn_started_at'] = datetime.now().isoformat()`

#### Scenario: 开始时间丢失时降级

- **GIVEN** 用户 Flask session 被清除或过期，`syn_started_at` 不存在
- **WHEN** `synonym_done` 计算 duration_s
- **THEN** SHALL 写入 `duration_s = 0`
- **AND** 仍正常写入 study_log（不阻塞 streak 更新）

