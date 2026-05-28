## Why

当前首页提供两个独立学习按钮：

- **「开始学习」** → 永远走 `/learn/setup`（普通翻卡：英文 → 中文）
- **「同义词学习」** → 永远走 `/learn/synonym/setup`（同义词翻卡）

用户必须自己理解词库类型才能选对按钮——典型踩坑：刚导入同义词词库就点了「开始学习」，进入普通翻卡看到的是"英文 → 半段中文"的破碎体验。

既然词库已有 `type` 字段（`add-synonym-quiz-mode` 已实现），首页完全可以**按词库 type 自动分发**到对应入口，让用户永远点对，不再需要"同义词学习"作为独立按钮存在。

## What Changes

- **「开始学习」按钮按词库 type 智能分发**：当前词库 `type='synonym'` → `/learn/synonym/setup`；`type='standard'` → `/learn/setup`（既有路径）
- **「继续上次学习」按钮同理分发**：检测同义词学习的 `syn_queue` 与普通学习的 `learn_session`，按词库 type 优先恢复对应进度
- **去掉「同义词学习」独立按钮**：合并入「开始学习」，避免用户误点
- **同义词学习计入 streak / study_log**：同义词学习完成时也写一条 `study_log` 记录，进入打卡 streak 统计（与普通学习一致）
- **首页词库切换浮层（list-picker）行为不变**：仍按现有逻辑显示
- **测验入口、词库管理、设置等不动**：测验出题已按 type 自动分支（`add-synonym-quiz-mode` 已实现），无需改

## Capabilities

### New Capabilities

- `learn-entry-dispatch`: 学习入口根据当前词库 type 智能分发的能力——按钮可见性、链接目标、断点续传识别、streak 计入规则

### Modified Capabilities

（无）

## Impact

**前端**：
- `templates/index.html`：
  - 「开始学习」按钮的 href 根据 `current_list.type` 动态指向 `learn_setup` 或 `synonym_setup`
  - 「继续上次学习」按钮链接动态指向对应继续路径，且检测条件需覆盖两种 session
  - 删除「同义词学习」单独按钮（含 `stats.with_synonyms > 0` 条件块）

**后端**：
- `app.py` `index()` 路由：
  - 在 context 中额外暴露 `current_list_type`、`active_syn_session`
  - `get_active_session(list_id)` 调用方需扩展为"无论 type 都能检测进行中状态"
- `app.py` `synonym_done` 路由（同义词学习完成处理）：
  - 新增写入 `study_log` 记录（mode='learn_synonym'，accuracy=1.0，duration_s 从 syn 启动时间计算）
- `app.py` `calc_streak()` / `today_completed()` 函数：
  - 扩展 mode 过滤条件，让 `learn_synonym` 也计入

**数据库**：
- 无 schema 变更（study_log 表 mode 字段是 TEXT，已支持新值）
- 同义词学习启动时需要在 session 里多存一个开始时间（用于计算 duration_s）；通过 `session['syn_started_at']` 实现

**测试**：
- 新增 `tests/test_learn_entry_dispatch.py`：覆盖
  - 当前词库 type=synonym 时首页渲染指向 `/learn/synonym/setup`
  - 当前词库 type=standard 时首页指向 `/learn/setup`
  - 同义词学习完成时正确写入 `study_log` 且 `calc_streak` 计入
  - 「继续上次学习」按钮在两种 session 下都能正确呈现

**风险**：
- 低。改动局限于首页按钮分发与 streak 计入；旧用户进行中的 `learn_session` 与 `syn_queue` 不被破坏
- 已经习惯点「同义词学习」按钮的用户需要适应按钮消失（但替代按钮「开始学习」会自动走对路径，体验更顺）
