## 1. 数据库 schema 迁移

- [x] 1.1 在 `database.py` 的 `init_db()` 中，对 `learn_session` 表执行 `ALTER TABLE learn_session ADD COLUMN current_index INTEGER`，用 try/except 吞掉"duplicate column"错误实现幂等
- [x] 1.2 验证：删除 `vocab.db` 后启动应用 → 重新建表带 current_index 字段；保留旧 `vocab.db` 启动 → ALTER 成功不报错

## 2. 翻卡学习后端改造

- [x] 2.1 修改 `app.py` 的 `/learn/start` 路由：创建 learn_session 时 `current_index` 显式写入 0
- [x] 2.2 改造 `/learn/card` 路由：以 `word_ids[current_index]` 取当前词，不再用 `remaining_ids[0]`；进度数字改用 `max(current_index + 1, session.get('learn_max_reached', current_index + 1))`
- [x] 2.3 在 `/learn/card` 渲染时把 `session['learn_max_reached']` 更新为 `max(current, current_index + 1)`
- [x] 2.4 改造 `/learn/next` 路由：`current_index += 1`，越界时跳转 `/learn/quiz`；不再 `remaining.pop(0)`
- [x] 2.5 新增 `/learn/prev` 路由（POST）：`current_index = max(0, current_index - 1)`，redirect 回 `/learn/card`
- [x] 2.6 在 `/learn/continue` 路由中加 lazy 迁移：若 `current_index` 为 NULL，按 `len(word_ids) - len(remaining_ids)` 回填并 UPDATE 数据库
- [x] 2.7 在 `/learn/card` 路由内加入 clamp 防御：`current_index = min(max(0, current_index), len(word_ids) - 1)`
- [x] 2.8 修改 `/learn/abandon` 路由末尾清理 `session.pop('learn_max_reached', None)`

## 3. 翻卡学习前端改造

- [x] 3.1 修改 `templates/flashcard.html`：在「下一张 →」按钮左侧新增「← 上一张」按钮 form，action 指向 `/learn/prev`
- [x] 3.2 在第一张时（模板传入 `current == 1`）将「上一张」按钮设为 `disabled` 并改样式为灰显
- [x] 3.3 修改键盘脚本：监听 `e.code === 'ArrowLeft'` 时提交 prev 表单（除非已在第一张）
- [x] 3.4 模板传入 `prev_available` 布尔值（由后端根据 `current_index > 0` 计算）替代纯前端判断，便于一致

## 4. 测验后端改造

- [x] 4.1 三处 quiz 初始化（`/learn/quiz` / `/quiz/retry` / `/test/start`）：在 quiz_index 重置同处 `session['quiz_max_reached'] = 1`；`api_switch_list_safe` 切库清理处同步 pop
- [x] 4.2 改造 `/quiz/question` 路由：读取 `session['quiz_answers'].get(str(idx))` 作为 `preselected` 传给模板；更新 `quiz_max_reached = max(current, idx + 1)`；读取 `from_prev` query 参数透传给模板
- [x] 4.3 改造 `/quiz/answer` 路由：保持现有 `quiz_index += 1` 逻辑（dict 覆盖天然支持改答案）
- [x] 4.4 新增 `/quiz/prev` 路由（POST）：`session['quiz_index'] = max(0, session['quiz_index'] - 1)`，redirect 到 `/quiz/question?from_prev=1`
- [x] 4.5 在 `/quiz/submit` 两个出口（learn 通关、test mode）追加清理 `session.pop('quiz_max_reached', None)`

## 5. 测验前端改造

- [x] 5.1 修改 `templates/quiz.html`：在选项区下方新增「← 上一题」按钮 form，action 指向 `/quiz/prev`
- [x] 5.2 在第一题时（`prev_available == False`）将「上一题」按钮设为 `disabled` 灰显
- [x] 5.3 模板根据 `preselected` 给对应选项 button 加 `quiz-option--selected` class 视觉标记
- [x] 5.4 加键盘 ← 键监听：提交 prev 表单（首题除外）
- [x] 5.5 听力题逻辑：仅在 `from_prev=false` 时 setTimeout autoPlay；回退访问不自动重播
- [x] 5.6 `static/style.css` 新增 `.quiz-option--selected` 样式（深色边框 + 字母圈反色）

## 6. 进度计数显示

- [x] 6.1 模板（flashcard.html + quiz.html）的进度文案改为显示后端传入的 `display_progress`（已计算 max_reached）
- [x] 6.2 后端 `/learn/card` 与 `/quiz/question` 路由统一构造 `display_progress = max(current_position, max_reached)` 传给模板

## 7. 单元测试

- [x] 7.1 新增 `tests/test_prev_navigation.py`：测试 `/learn/prev` 让 `current_index` 自减；首张时 prev 无效（仍为 0）
- [x] 7.2 测试 `/quiz/prev` 让 `quiz_index` 自减；首题时 prev 无效
- [x] 7.3 测试回退后改答案：用 test_client 模拟答 A → prev → 答 B → submit，验证最终 `quiz_answers` 是 B
- [x] 7.4 测试 max_reached 不倒退：前进到 idx=5 → prev 到 idx=2 → 渲染时 display=5（learn 与 quiz 双场景）
- [x] 7.5 测试旧 session 迁移：构造 `current_index=NULL + remaining_ids=[c,d,e] + word_ids=[a,b,c,d,e]` 的 session → 访问 `/learn/card` → 迁移后 current_index=2
- [x] 7.6 测试 abandon 清理 `learn_max_reached`（test_learn_abandon_clears_max_reached）
- [x] 7.7 跑全部既有测试（含 test_heartbeat 等）确保零回归：**32 测试全绿**（22 既有 + 10 新增）

## 8. 文档与验收

- [x] 8.1 更新 `README.md`「功能」段落：翻卡学习追加"双向流转"，学习测验/测试模式追加"可回退改答案"
- [x] 8.2 在 main 分支提交所有改动；commit message 标注 "feat(navigation): 翻卡与测验支持双向流转"
- [x] 8.3 切到 packaging 分支 merge main，跑 `bash build_mac.sh` 生成新 .app/.dmg
- [x] 8.4 push packaging 到远端，提示用户在 Win 虚拟机 pull 后 `build_win.bat`
- [x] 8.5 `openspec validate add-prev-navigation --strict` 通过
- [x] 8.6 Mac 实测：翻卡学习 → 学到第 5 张 → ← 回到第 3 张 → 卡片正面 → 翻看 → → 回到第 4 张 ✓
- [x] 8.7 Mac 实测：学习测验答完第 3 题 → ← 回第 2 题 → 看到原选项 → 改选 → → 继续 → 提交后成绩按改后计算 ✓
- [x] 8.8 Mac 实测：正式测试（test 模式）听力题 → ← 回退 → 不自动重播 → 主动点 🔊 仍能播 ✓
- [ ] 8.9 用户 Win 实测：双向流转在打包环境下行为一致 ✓
