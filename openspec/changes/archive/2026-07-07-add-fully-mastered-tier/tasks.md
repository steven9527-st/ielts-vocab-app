## 1. 后端 - 数据层与选词

- [x] 1.1 `get_list_stats`：新增 `fully_mastered` 字段；`mastered` 字段口径改为**仅 status='mastered'**（不含 fully_mastered）
- [x] 1.2 `test_start` 选词 SQL：`AND status='mastered'` 保持不变（已经天然排除 fully_mastered）
- [x] 1.3 `test_setup`：门槛校验 `stats['mastered'] < 4` 语义不变（因为 mastered 现在不含 fully_mastered，如果全升 fully_mastered 会拦截）
- [x] 1.4 `PATCH /library/word/<id>` API：status 白名单加入 `'fully_mastered'`

## 2. 后端 - 新端点

- [x] 2.1 新增路由 `POST /mastery/promote`：接收 `{word_ids: [...]}`，UPDATE 每个词 status='fully_mastered' WHERE status='mastered'；返回 `{ok, promoted}`
- [x] 2.2 端点校验：word_ids 必须是数组；单个词非 mastered 时跳过；空列表返回 promoted=0

## 3. 结果页数据准备

- [x] 3.1 `quiz_submit` learn 模式通关分支：把本次原始 word_ids 对应的 `{english, chinese/synonyms, correct/user_answer}` 组装成列表传给模板
- [x] 3.2 test 模式分支同样组装列表

## 4. 模板

- [x] 4.1 `templates/quiz_result.html` passed 分支：加单词列表 + checkbox + 「加入完全掌握」按钮 + 提交 JS（fetch POST）
- [x] 4.2 `templates/test_result.html`：加同样的单词列表 + checkbox + 提交按钮
- [x] 4.3 `templates/index.html`：metric grid 改为 4 张卡「词库总数 / 已掌握 / 完全掌握 / 未掌握」
- [x] 4.4 `templates/library.html`：徽章展示扩展三态（badge--gold）+ 点击循环切换 JS 改造
- [x] 4.5 `static/style.css`（如需）：新增 `.badge--gold` 或 `.metric-card__number--gold` 颜色变量

## 5. 测试

- [x] 5.1 新增 `tests/test_fully_mastered_tier.py`
- [x] 5.2 用例：`get_list_stats` 三态计数正确（50/30/20 → mastered=30, fully_mastered=20）
- [x] 5.3 用例：test_start 只选 mastered（不含 fully_mastered）
- [x] 5.4 用例：POST /mastery/promote 正常升级 mastered → fully_mastered
- [x] 5.5 用例：POST /mastery/promote 跳过 unmastered 词
- [x] 5.6 用例：POST /mastery/promote 空列表 promoted=0
- [x] 5.7 用例：PATCH /library/word/<id> 接受 fully_mastered 状态
- [x] 5.8 用例：quiz_result 通关页展示单词列表 + checkbox
- [x] 5.9 用例：test_result 完成页展示单词列表 + checkbox
- [x] 5.10 用例：index 首页展示 4 个 metric（含完全掌握）
- [x] 5.11 更新受影响的旧测试（如断言"3 张 metric 卡"的用例）
- [x] 5.12 跑全量测试全绿

## 6. 验收 & 收尾

- [ ] 6.1 本地手测：测试模式完成后勾选 2 个词 → 加入完全掌握 → 首页看到"完全掌握 2"
- [ ] 6.2 本地手测：学习通关后勾选 → 生效
- [ ] 6.3 本地手测：词库管理页点击徽章循环三态
- [ ] 6.4 本地手测：全部 mastered 升级为 fully_mastered 后，测试模式应显示"已掌握 < 4"拦截页
- [x] 6.5 `openspec validate add-fully-mastered-tier` 通过
- [ ] 6.6 git commit + push（等用户测完）
- [ ] 6.7 OpenSpec archive（等用户测完）
- [ ] 6.8 打 Mac 包（等用户测完）
