## Context

三种模式的选词 SQL 现状（app.py 已定位）：

```python
# 普通学习 (learn_start, line 911)
"SELECT id FROM words WHERE list_id=? AND status='unmastered' ORDER BY RANDOM() LIMIT ?"

# 同义词学习 (synonym_start, line 1603)
"SELECT id FROM words WHERE list_id=? AND synonyms IS NOT NULL AND synonyms!='' "
"ORDER BY RANDOM() LIMIT ?"

# 测试模式 (test_start, line 1469)
"SELECT id FROM words WHERE list_id=? ORDER BY RANDOM() LIMIT ?"
```

`get_list_stats` 目前返回 `{total, mastered, unmastered, with_synonyms}`——`with_synonyms` 是"含同义词的词数（不管掌握状态）"。

`test_start` 有一处 `total_count < 4` 的门槛检查（用于确保干扰项池够）——改成 mastered 池后，这个校验也要调整。

## Goals / Non-Goals

**Goals:**
- 三种模式的选词条件语义清晰、可预期：
  - 普通学习：未掌握（不变）
  - 同义词学习：未掌握 + 含同义词
  - 测试模式：已掌握
- 边界情况给用户清晰的引导（不 crash、不出空白页）
- `generate_quiz_questions` 的 4 个干扰项要求继续满足

**Non-Goals:**
- 不引入间隔重复/艾宾浩斯（用户已明确暂不做）
- 不改 `words.status` 二元状态模型
- 不改测试模式的题目生成逻辑（listening/text 分支不变）

## Decisions

### Decision 1: 干扰项池边界 —— 测试模式的"已掌握 < 4"

**选择**：`test_setup` 视图渲染前检查，若 `stats.mastered < 4` 则展示引导页（"当前词库已掌握词不足 4 个，请先去学习一些单词再来测试"+ 返回首页按钮）。

**理由**：
- `test_start` 里的 `if total_count < 4` 检查会保留但改为检查 `mastered_count`，防御性双层保护
- 用户在 setup 页就能被提前拦住，比进 quiz_error 页体验好

**替代方案**：降级到全词库出题——被否决（用户明确选了 B 方案：提示 + 跳回首页）

### Decision 2: 干扰项候选池

**问题**：测试模式题目是"英文 → 中文释义 4 选 1"，干扰项来自 `generate_quiz_questions`。改成"只测已掌握"后：
- **题目词**：来自 mastered 池
- **干扰项**：目前 `generate_quiz_questions` 从**全词库**取干扰项——**这个不动**，逻辑正确（干扰项只是随机选项，不涉及掌握状态）

**选择**：干扰项候选池保持全词库不变，`generate_quiz_questions` 无需改动。

### Decision 3: 同义词学习 setup 页展示

**问题**：`synonym_setup` 现在展示"词库中带同义词的单词：X 个"，改成"未掌握"过滤后，X 数值会变小。

**选择**：新增 stats 字段 `unmastered_with_synonyms`（未掌握且含同义词），setup 页 max 与 subtitle 都用它。

**边界**：`unmastered_with_synonyms == 0` 时——已经有 `with_synonyms == 0` 分支处理"该词库没有带同义词的单词"提示，同样思路把提示改为"暂无可学的同义词单词（都已掌握或都无同义词）"。

### Decision 4: 学习流程通关后触发的连锁反应

**问题**：用户学完 20 个词、通关、UPDATE `status='mastered'`。同义词流也一样。此时首页统计立即变化——但学习流内部（`learn_session`、`syn_queue`）不受影响，因为这些都是在会话开始时锁定的 word_ids。

**结论**：不需要额外处理。已有测试覆盖。

## Risks / Trade-offs

- **[风险] 老用户升级后测试模式被禁用**：如果一个新用户没学过任何词就点测试，会被拦住。
  → 这就是期望行为。setup 页会引导他去学习。

- **[风险] 词库 mastered 都 < 4 但 total >= 4 的场景**：例如刚导入词库还没学过，或 mastered 只有 2 个。
  → setup 页拦住并给出明确提示。

- **[风险] 同义词学习完全没有可学的词**：所有含同义词的词都已掌握了。
  → `synonym_setup` 展示"暂无可学的同义词单词"引导用户去测试模式复习。

## Migration Plan

无 schema 变更，无数据迁移。部署后立即生效。
