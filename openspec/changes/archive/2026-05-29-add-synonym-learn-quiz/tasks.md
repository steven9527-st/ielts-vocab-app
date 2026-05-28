## 1. 摸清现状

- [x] 1.1 阅读 `app.py` 中 `learn_quiz` 路由（普通流测验入口），确认它如何从 session/learn_session 取词、如何调 `generate_quiz_questions`
- [x] 1.2 阅读 `synonym_done` 路由及前置跳转点（`/learn/synonym/next` 等），梳理 session key 流转（`syn_word_ids`/`syn_total`/`syn_started_at`/`syn_list_id`/`syn_queue`）
- [x] 1.3 阅读 `templates/quiz_result.html` 或测验完成跳转目标，确认能否注入「返回 synonym_done」分支

## 2. 后端改造

- [x] 2.1 在同义词学习"学完最后一张"分支，把跳转目标从 `synonym_done` 改为：先把 `syn_word_ids` 复制到 `session['pending_quiz_word_ids']`、设置 `session['pending_quiz_return_to'] = 'synonym_done'`，再 `redirect(url_for('learn_quiz'))`
- [x] 2.2 在跳转测验**之前**就把 `study_log(mode='learn_synonym')` 写入数据库（提取为辅助函数 `_write_synonym_study_log()`），避免用户中途退出丢失学习记录
- [x] 2.3 修改 `synonym_done` 路由：移除原 study_log 写入（已上移到 2.2），保留页面渲染逻辑；session 数据缺失时走 fallback 通用文案
- [x] 2.4 修改 `learn_quiz` 路由：若 `session.get('pending_quiz_word_ids')` 非空，优先用它作为测验范围；通过 `_get_list_type(list_id)` 决定 `list_type` 参数；生成题目后 `pop('pending_quiz_word_ids')`
- [x] 2.5 修改测验完成跳转逻辑：若 `session.get('pending_quiz_return_to') == 'synonym_done'`，测验提交完成时 `pop` 该 key 并 `redirect(url_for('synonym_done'))`

## 3. 前端/模板

- [x] 3.1 检查 `quiz_result.html` 等测验结果页，若使用"再来一组/返回首页"按钮则保持原样；同义词路径下若选择"自动 redirect"方案则无需改模板
- [x] 3.2 `flashcard_synonym_done.html` 文案保持不变（再来一组 + 返回首页）

## 4. 测试

- [x] 4.1 新增 e2e 测试 `tests/test_synonym_learn_quiz_flow.py`：模拟登录 → 同义词学习 N 张 → 学完最后一张 → 断言被 redirect 到 quiz 页 → 提交测验 → 断言进入 synonym_done 页
- [x] 4.2 测试 `study_log` 写入：学完跳测验后立刻断言已有 `mode='learn_synonym'` 一条；测验完成后断言增加 `mode='quiz'` 一条
- [x] 4.3 测试中途退出场景：学完跳测验，但不提交测验直接访问首页 → 断言 `mode='learn_synonym'` 已写入、`mode='quiz'` 未写入
- [x] 4.4 测试 session fallback：在测验前清空 `syn_*` session → 访问 `synonym_done` → 断言不崩溃、展示通用文案、不重复写 study_log
- [x] 4.5 更新可能受影响的旧测试（如 `test_synonym_*` 中断言"学完直接跳 synonym_done"的用例）
- [x] 4.6 跑全量测试 `pytest tests/ -v`，确认 82+ 全绿

## 5. 验收 & 收尾

- [x] 5.1 本地手测：同义词词库点开始学习 → 学完 → 进入测验 → 提交 → 完成页
- [x] 5.2 手测中途退出场景，确认 streak 计数不丢
- [x] 5.3 `openspec validate add-synonym-learn-quiz` 通过
- [x] 5.4 git commit + push
- [x] 5.5 OpenSpec archive

## 6. 补丁：同义词翻卡支持「上一张」导航（测试反馈追加）

- [x] 6.1 后端 `synonym_start` 初始化 `session['syn_index']=0`；`synonym_card`/`synonym_next` 改为游标模型（支持 lazy 迁移旧 session）
- [x] 6.2 新增 `/learn/synonym/prev` 路由：`syn_index -= 1`（不低于 0），redirect 回 card
- [x] 6.3 `synonym_card` 传 `prev_available` 给模板
- [x] 6.4 `synonym_abandon` / `synonym_done` 清理 `syn_index` session key
- [x] 6.5 `flashcard_synonym.html` 加「← 上一张」按钮（永久显示，首张 disabled）+ 键盘 ← 快捷键，对齐 `flashcard.html` 体验
- [x] 6.6 新增 5 个测试覆盖：首张 disabled / 非首张可用 / prev 回退 / 首张点 prev 不动 / 最后一张 next 仍跳测验
- [x] 6.7 跑全量测试 95 全绿
