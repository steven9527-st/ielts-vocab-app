## Context

现有逻辑在 `learn_start()` 中通过 `WHERE status='unmastered'` 筛选学习词汇。当词库全部掌握后，`unmastered` 结果为空 → `word_ids` 为空 → 直接 `redirect(url_for('index'))`。首页再配合 `stats.unmastered == 0` 条件将按钮设为 disabled，形成双重阻断。

## Goals / Non-Goals

**Goals:**
- 全部掌握后，首页学习按钮依旧可用
- 学习模式仍优先从未掌握词中选取
- 未掌握词不足需求数量时，用全词库补齐（允许回顾已掌握词）
- 学习 setup 页在全部掌握时也能正常设置学习数量并开始

**Non-Goals:**
- 不改变测试模式的选词逻辑（仍从 mastered 池选）
- 不改变 learn_continue（继续上一次学习）的逻辑
- 不新增"重置掌握状态"功能

## Decisions

### 1. 选词补齐策略
**选择**: 先查未掌握词，不足时用全词库补齐（`ORDER BY RANDOM() LIMIT n`）。
**理由**: 优先消化未掌握词，仅在不够时允许回顾已掌握词。避免让已掌握词挤占未掌握词的位置。
**替代方案**: 直接改为全词库随机——简单但不符合"学习优先级"的直觉。

### 2. 补齐时的去重
**选择**: 使用 `UNION` + `NOT IN` 去重。
**理由**: 避免已掌握词和未掌握词出现重复（如果后面改了逻辑导致重叠）。
具体：`(SELECT id FROM words WHERE list_id=? AND status='unmastered' LIMIT n) UNION (SELECT id FROM words WHERE list_id=? AND status!='unmastered' LIMIT n)`。
**替代方案**: Python 层面 `set` 去重——简单但多一次往返查询。

## Risks / Trade-offs

- **Risk**: 用户反复学习全部掌握的单词，容易产生"无聊"感 → 旧行为已有此问题（学完即无法再学），本次不改动学习模式本身
- **Trade-off**: 已掌握词再次被学 → 测验通过后状态不变（已 mastered 保持不变），不会回退到 unmastered
