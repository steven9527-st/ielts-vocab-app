## ADDED Requirements

### Requirement: 同义词学完最后一张后自动进入测验

同义词学习流（`/learn/synonym/*` 系列路由）在用户学完本次会话最后一张卡片时，SHALL 不直接跳转到「学习完成」页（`synonym_done`），而是先跳转到测验环节（复用 `learn_quiz` 路由），测验范围严格限定为本次学习的 `syn_word_ids`。测验完成后再进入「学习完成」页。

#### Scenario: 学完最后一张自动跳测验

- **GIVEN** 用户在同义词学习流中
- **AND** 当前是本次会话的最后一张卡片（`syn_queue` 已空 或 已学完 `syn_total` 张）
- **WHEN** 用户点击「下一张」或翻到卡片背面后确认完成
- **THEN** 系统 SHALL 把本次学习的词条 ID 列表（`syn_word_ids`）写入 session 的 `pending_quiz_word_ids`
- **AND** SHALL 写入 `pending_quiz_return_to='synonym_done'` 标记测验完成后的跳转目标
- **AND** SHALL `redirect(url_for('learn_quiz'))` 进入测验流程
- **AND** SHALL 在跳转前完成 `study_log(mode='learn_synonym')` 的写入（确保用户中途退出也已计入 streak）

#### Scenario: learn_quiz 优先消费 pending_quiz_word_ids

- **GIVEN** session 中存在 `pending_quiz_word_ids` 非空
- **WHEN** 用户访问 `/learn/quiz` 路由
- **THEN** `learn_quiz` SHALL 优先使用 `pending_quiz_word_ids` 作为测验范围
- **AND** SHALL 通过 `_get_list_type(list_id)` 判定当前词库类型为 `synonym`
- **AND** SHALL 调用 `generate_quiz_questions(words, list_type='synonym')` 生成同义词测验题目
- **AND** SHALL 在测验题目生成后 `pop('pending_quiz_word_ids')`，避免下次误用

#### Scenario: 同义词测验完成后回到完成页

- **GIVEN** 用户完成了来自同义词学习流的测验
- **AND** session 中 `pending_quiz_return_to == 'synonym_done'`
- **WHEN** 测验提交并展示结果后
- **THEN** 结果页 SHALL 提供「返回同义词完成页」入口（或自动 redirect 到 `synonym_done`）
- **AND** `synonym_done` 页面 SHALL 正常展示「本次共学习 N 个单词的同义词」庆祝文案

#### Scenario: 测验中途用户退出不丢失学习记录

- **GIVEN** 用户从同义词学习跳入测验后，未完成测验就返回首页
- **WHEN** 检查 `study_log` 表
- **THEN** SHALL 存在一条 `mode='learn_synonym'` 记录（本次学习已计入 streak）
- **AND** 不存在 `mode='quiz'` 记录（测验未完成，符合预期）

#### Scenario: session 丢失时的 fallback

- **GIVEN** 用户在测验流程中因刷新/超时导致 `syn_total` 等 session 数据丢失
- **WHEN** 测验完成后跳转到 `synonym_done`
- **THEN** `synonym_done` SHALL 展示通用完成文案（如「学习完成」），而非崩溃
- **AND** SHALL 不重复写入 `study_log`（避免重复统计）

### Requirement: 同义词翻卡支持「上一张」导航

为对齐普通词库学习流的双向流转体验，同义词翻卡（`flashcard_synonym.html`）SHALL 在按钮区永久显示「← 上一张」按钮（首张时灰显/disabled），并提供 `/learn/synonym/prev` 后端路由配套支持。

同义词学习的 session 模型 SHALL 从「队列消费（`syn_queue.pop(0)`）」升级为「游标推进（`syn_index`）」，保留 `syn_word_ids` 全集不变，使「上一张」语义可达。旧 session（只有 `syn_queue` 没有 `syn_index`）SHALL 通过 lazy 迁移自动适配。

#### Scenario: 首张卡片 prev 按钮 disabled

- **GIVEN** 用户进入同义词学习，当前是第 1 / N 张
- **WHEN** `flashcard_synonym.html` 渲染
- **THEN** 「← 上一张」按钮 SHALL 显示但 `disabled`（`prev_available=False`）
- **AND** 键盘 ← 按键 SHALL 无效（前端 `prevAvailable=false`）

#### Scenario: 非首张点 prev 回到上一张

- **GIVEN** 用户已在第 K (K>1) 张卡片
- **WHEN** 点击「← 上一张」按钮 或 按键盘 ←
- **THEN** 后端 SHALL `session['syn_index'] -= 1`（不低于 0）
- **AND** SHALL redirect 回 `synonym_card`，渲染第 K-1 张
- **AND** 进度显示 SHALL 更新为「K-1 / N」

#### Scenario: 翻到背面后才显示「下一张」

- **GIVEN** 用户进入新一张卡片（含 prev 跳转回来的卡片）
- **WHEN** 用户尚未翻到背面
- **THEN** 「下一张 →」按钮 SHALL 隐藏
- **AND** 「← 上一张」按钮 SHALL 始终可见（按 `prev_available` 决定 disabled）
- **WHEN** 用户翻到背面（任意一次后）
- **THEN** 「下一张 →」按钮 SHALL 显示

#### Scenario: 旧 session lazy 迁移

- **GIVEN** session 中只有 `syn_queue` 而无 `syn_index`（升级前残留）
- **WHEN** 访问 `synonym_card` 或 `synonym_next`
- **THEN** 系统 SHALL 按 `syn_total - len(syn_queue)` 推断当前位置写入 `syn_index`
- **AND** 后续操作 SHALL 走游标模型，不再依赖 queue 头部
