## 1. 后端选词逻辑

- [x] 1.1 `synonym_start`：SQL 增加 `AND status='unmastered'` 条件
- [x] 1.2 `test_start`：SQL 增加 `AND status='mastered'`；`total_count < 4` 检查改为 `mastered_count < 4`

## 2. 统计字段补充

- [x] 2.1 `get_list_stats`：新增 `unmastered_with_synonyms` 字段（SQL：`status='unmastered' AND synonyms非空`）

## 3. Setup 页视图 & 模板

- [x] 3.1 `test_setup` 视图：mastered < 4 时渲染引导页（新模板 `test_setup_empty.html` 或复用 quiz_error 模板）
- [x] 3.2 `test_setup.html`：subtitle 改为"从已掌握的 X 个单词中随机出题"；`max` 属性从 `stats.total` 改为 `stats.mastered`；JS 中 `const max = ...` 同步
- [x] 3.3 `synonym_setup`：`default_n` 用 `stats.unmastered_with_synonyms`；stats.with_synonyms == 0 分支扩展为 `unmastered_with_synonyms == 0` 时也提示
- [x] 3.4 `learn_synonym_setup.html`：subtitle & max 用新字段

## 4. 测试

- [x] 4.1 新增 `tests/test_selection_by_mastery.py`
- [x] 4.2 用例：同义词学习只从未掌握词中选（20 词 5 mastered → 抽 15，全部 unmastered）
- [x] 4.3 用例：同义词学习未掌握不足时按实际数选（unmastered=2, request=15 → 抽 2）
- [x] 4.4 用例：所有含同义词都掌握时 synonym_setup 展示引导
- [x] 4.5 用例：test_start 只从 mastered 池选（30 词 12 mastered → 抽 10 全 mastered）
- [x] 4.6 用例：test_setup 遇 mastered < 4 → 渲染引导页
- [x] 4.7 用例：`get_list_stats` 新字段 `unmastered_with_synonyms` 计算正确
- [x] 4.8 更新受影响的旧测试（若有断言"全词库"选词的用例）
- [x] 4.9 跑全量 `pytest tests/ -v` 全绿

## 5. 验收 & 收尾

- [ ] 5.1 本地手测：同义词词库学 5 词通关 → 再点开始学习 → 不会再抽到那 5 个词
- [ ] 5.2 本地手测：mastered 词 < 4 的词库点测试模式 → 引导页提示 + 返回首页按钮可用
- [ ] 5.3 本地手测：mastered ≥ 4 的词库点测试 → subtitle 显示"从已掌握的 X 个单词中随机出题"
- [x] 5.4 `openspec validate align-selection-by-mastery` 通过
- [ ] 5.5 git commit + push
- [ ] 5.6 OpenSpec archive（等用户测完再做）
- [ ] 5.7 打 Mac 包（等用户测完再做）
