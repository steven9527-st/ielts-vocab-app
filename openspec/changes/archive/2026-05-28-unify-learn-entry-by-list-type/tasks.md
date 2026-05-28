## 1. 后端 index 路由扩展

- [x] 1.1 修改 `app.py` `index()` 路由：在 context 中暴露 `current_list_type`（即 `current_list['type']`，模板用 `current_list.type` 访问）
- [x] 1.2 检测 `active_syn_session`：判断 Flask session 中是否有非空 `syn_queue`，传给模板
- [x] 1.3 `calc_streak()` 函数：SQL 改为 `mode IN ('learn', 'learn_synonym')`
- [x] 1.4 `today_completed(list_id)` 函数：SQL 改为 `mode IN ('learn', 'learn_synonym')`

## 2. 同义词学习计入 streak

- [x] 2.1 修改 `app.py` `synonym_start` 路由：在 `session['syn_queue']` 设置之后追加 `session['syn_started_at']`、`session['syn_word_ids']`、`session['syn_list_id']`
- [x] 2.2 修改 `app.py` `synonym_done` 路由：取出 session 数据写入 `study_log`（mode='learn_synonym', accuracy=1.0, duration_s 计算 / 缺失则 0）
- [x] 2.3 try/except 包裹 study_log 写入，失败不阻塞跳转
- [x] 2.4 末尾清理 `syn_queue` `syn_total` `syn_word_ids` `syn_started_at` `syn_list_id`；synonym_abandon 也同步清理

## 3. 前端首页改造

- [x] 3.1 修改 `templates/index.html`：「开始学习」按钮根据 `current_list.type` 动态 `href`（synonym → synonym_setup，否则 → learn_setup）
- [x] 3.2 「继续上次学习」按钮判定条件改为 `active_session or (synonym 时 active_syn_session)`；链接根据 type 分发
- [x] 3.3 完全删除独立的「同义词学习」按钮代码块
- [x] 3.4 保持「测试模式」「词库管理」「导入新词库」按钮位置与样式不变
- [x] 3.5 同义词词库不被 `stats.unmastered == 0` 拦截（同义词学习不标 mastered）

## 4. 测试

- [x] 4.1 新增 `tests/test_learn_entry_dispatch.py`
- [x] 4.2 测试 standard 词库 GET / → HTML 含 `href="/learn/setup"`
- [x] 4.3 测试 synonym 词库 GET / → HTML 含 `href="/learn/synonym/setup"`
- [x] 4.4 测试两种词库下 HTML 都不含独立「同义词学习」文字按钮
- [x] 4.5 测试 active_syn_session 检测：session 设 `syn_queue=[1,2,3]` 后 GET /，HTML 含「继续上次学习」按钮
- [x] 4.6 测试 synonym_done 写入 study_log：mode='learn_synonym'，accuracy=1.0
- [x] 4.7 测试 calc_streak 把 learn_synonym 日期纳入连续天数计算
- [x] 4.8 测试 today_completed 在仅有 learn_synonym 记录时也返回 True
- [x] 4.9 测试 syn_started_at 缺失时 duration_s=0，study_log 仍正常写入
- [x] 4.10 修复回归：test_pdf_table_e2e 旧断言（找"同义词学习"按钮文本）改为验证「开始学习」按钮 href
- [x] 4.11 跑全部既有测试（≥ 72 个）确保零回归：**82 测试全绿**（72 既有 + 10 新增）

## 5. 文档与归档

- [x] 5.1 更新 `README.md`「同义词学习」描述：补充"首页按词库类型智能分发，无需单独选择入口"
- [ ] 5.2 在 main 分支提交所有改动；commit message: "feat(ui): 首页学习按钮按词库 type 智能分发，去除独立同义词学习按钮"
- [ ] 5.3 切到 packaging 分支 merge main，跑 `bash build_mac.sh` 生成新 .app/.dmg
- [ ] 5.4 push packaging 到远端
- [x] 5.5 `openspec validate unify-learn-entry-by-list-type --strict` 通过
- [ ] 5.6 `openspec archive unify-learn-entry-by-list-type -y` 归档
- [ ] 5.7 Mac 实测：切到 C19 同义词词库 → 首页只有一个「开始学习」按钮 → 点击 → 进入同义词学习入口 ✓
- [ ] 5.8 Mac 实测：切到标准词库（雅思 3500）→ 首页「开始学习」→ 进入普通翻卡 ✓
- [ ] 5.9 Mac 实测：完成一轮同义词学习 → 首页 streak 数字 +1，「今日已通关 ✅」徽章显示 ✓
- [ ] 5.10 用户 Win 实测：跨平台行为一致 ✓
