## Why

用户反馈：当前"已掌握"是二元状态——一个词只要学习通关一次就被标 `mastered` 永久保持，测试模式一直会重复考它，即使这个词用户已经很熟。缺少"这个词我彻底会了，不用再考"的表达机制。

期望：测试完成后，用户可从本次题目中挑选真正掌握的词，标为「完全掌握」（`fully_mastered`），这些词后续**不再进入测试**，让测试专注在还需要巩固的词上。

## What Changes

- **DB 状态枚举扩展**：`words.status` 从 `'unmastered' | 'mastered'` 扩展为 `'unmastered' | 'mastered' | 'fully_mastered'`
- **测试模式选词收窄**：`test_start` SHALL 只从 `status='mastered'` 中选（**排除 fully_mastered**）
- **门槛校验收窄**：test_setup 的"已掌握 < 4"判定改为"仅 mastered（不含 fully_mastered）< 4"
- **首页 metric 卡新增「完全掌握」**：4 张卡片布局 `[词库总数] [已掌握] [完全掌握] [未掌握]`，三者相加 = total
- **测试完成页新增单词回顾 + 完全掌握勾选区**：
  - 展示本次测试所有题目（英文 + 中文/同义词 + 用户答题结果 ✓/✗）
  - 每个词旁边有 checkbox（默认不勾选）
  - 「加入完全掌握」按钮提交勾选的 word_ids，UPDATE 为 fully_mastered
- **学习通关页同样机制**：`quiz_result.html`（passed=True 分支）加入相同的单词列表 + checkbox + 提交按钮
- **词库管理页支持三态切换**：`w.status` 展示改为三色徽章（`未掌握` 蓝 / `已掌握` 绿 / `完全掌握` 金/紫）；点击徽章循环切换三个状态；PATCH API `status` 白名单扩展

## Capabilities

### New Capabilities
- `fully-mastered-tier`: 定义"完全掌握"层级的语义、生效路径（测试后勾选/学习后勾选/词库管理页手动）、以及对测试模式选词的影响

### Modified Capabilities
- `word-list-management`: `get_list_stats` 新增 `fully_mastered` 字段；已掌握统计口径变化（不再含 fully_mastered）；PATCH API 状态白名单扩展
- `mastery-tracking`: 「今日新增掌握」统计仍然基于 study_log，不受影响；`today_mastered_count` 语义不变

## Impact

- 代码：
  - `app.py`：`get_list_stats`（新增 `fully_mastered` 字段）、`test_start`（选词 SQL 排除 fully_mastered）、`test_setup`（门槛校验）、`quiz_submit`（结果页数据）、新增 `promote_to_fully_mastered` 路由
  - `templates/index.html`：4 张 metric 卡片布局
  - `templates/quiz_result.html`：passed 分支加单词列表 + checkbox + 提交按钮
  - `templates/test_result.html`：加同样的单词列表 + checkbox + 提交按钮
  - `templates/library.html`：三态徽章 + 循环切换 JS
  - `app.py` PATCH word API：status 白名单加入 `'fully_mastered'`
- DB：无 schema 变更（status 是 TEXT 字段，扩容不需要 ALTER）
- 测试：新增 8-10 个覆盖新枚举、选词、勾选提交、词库管理三态切换、首页 metric
