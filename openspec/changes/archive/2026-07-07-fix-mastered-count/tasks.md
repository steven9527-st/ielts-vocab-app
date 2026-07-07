## 1. 摸清现状

- [x] 1.1 阅读 `quiz_submit` 通关分支代码（普通流 + is_synonym_flow 分支），确认 word_ids 数据源如何被 quiz_retry 覆盖
- [x] 1.2 阅读 `quiz_retry` 覆盖 quiz_data.word_ids 的具体路径
- [x] 1.3 阅读 `learn_quiz` 中 pending_quiz_word_ids 到 quiz_token 的传递路径

## 2. 后端：修复通关 total & mastered 数据源

- [x] 2.1 在 `learn_quiz` 中把原始 word_ids（无论普通/同义词流）额外写入 `session['quiz_original_word_ids']`
- [x] 2.2 修改 `quiz_submit` 普通流通关分支：total 和 UPDATE mastered 都改用 `learn_session.word_ids`（DB 权威）作为原始全集；study_log 写入的 word_ids 也用原始全集
- [x] 2.3 修改 `quiz_submit` 同义词流通关分支：total 用 `session['quiz_original_word_ids']`；**新增 `UPDATE words SET status='mastered'`**；study_log 的 word_ids 也用原始全集
- [x] 2.4 通关分支结束时清理 `session.pop('quiz_original_word_ids', None)`

## 3. 后端：今日新增掌握统计

- [x] 3.1 新增辅助函数 `today_mastered_count(list_id)`：查询当天 `study_log(list_id=?, mode IN ('learn','learn_synonym'), accuracy=1.0, date=today)` 记录的 word_ids，flatten + 去重后返回长度
- [x] 3.2 首页视图 `index()` 中，若 `completed_today=True` 则计算 `today_mastered = today_mastered_count(list_id)`，注入模板
- [x] 3.3 modify `templates/index.html`：在「今日已通关 ✅」`div` 下方添加「今日新增掌握 **N** 个」文本（仅 `completed_today=True` 时渲染）

## 4. 后端：历史数据回补

- [x] 4.1 在 `database.py` 中新增 `_migrate_synonym_mastered(conn)`：SELECT `word_ids` FROM `study_log` WHERE `mode='learn_synonym' AND accuracy=1.0` → 对每个 wid `UPDATE words SET status='mastered' WHERE id=? AND status='unmastered'`
- [x] 4.2 在 `init_db()` 中调用该迁移函数（幂等）
- [x] 4.3 手动跑一次迁移验证：`python -c "import database; database.init_db()"` → 用 sqlite3 命令行检查 mastered 数量变化

## 5. 测试

- [x] 5.1 新增 `tests/test_mastered_count.py`：
- [x] 5.2 用例：20 词学习含 2 词错题重做，通关后 mastered 计数 +20（而非 +2）
- [x] 5.3 用例：首轮零错误通关，行为退化一致
- [x] 5.4 用例：同义词流 5 词学习通关后，`SELECT COUNT(*) WHERE status='mastered'` +5
- [x] 5.5 用例：`today_mastered_count()` 多会话去重（普通 20 + 同义词 8 + 同义词 5 with 2 重叠 = 31）
- [x] 5.6 用例：`today_mastered_count()` 跨词库隔离（不算别的 list_id）
- [x] 5.7 用例：历史迁移函数扫 `learn_synonym+accuracy=1.0` 记录，unmastered 词升 mastered，已 mastered 或手动降级的不动
- [x] 5.8 用例：首页模板断言「今日已通关」+「今日新增掌握 N 个」共同出现；未通关时后者不出现
- [x] 5.9 更新旧测试（`test_synonym_learn_quiz_flow.py` 中 test_full_flow_writes_both_logs 等），断言 mastered 已更新
- [x] 5.10 跑全量测试 `pytest tests/ -v`，确认全绿

## 6. 验收 & 收尾

- [ ] 6.1 本地手测：20 词学习含错题重做，通关页显示 20（不是 2）
- [ ] 6.2 本地手测：同义词流通关后返回首页，「已掌握」数字增加
- [ ] 6.3 本地手测：首页「今日已通关 ✅」下方显示「今日新增掌握 N 个」
- [x] 6.4 本地手测：清 vocab.db 后重启（模拟老用户升级），观察历史迁移是否触发
- [x] 6.5 `openspec validate fix-mastered-count` 通过
- [ ] 6.6 git commit + push
- [ ] 6.7 OpenSpec archive
- [ ] 6.8 打 Mac 包（等用户确认）
