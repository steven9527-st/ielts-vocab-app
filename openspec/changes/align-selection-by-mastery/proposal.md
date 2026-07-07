## Why

当前三种学习/测试模式的**选词条件不一致**，违背用户直觉：

| 模式 | 现状 SQL | 语义问题 |
|---|---|---|
| 普通学习 | `WHERE list_id=? AND status='unmastered'` | ✅ 只学未掌握（合理） |
| 同义词学习 | `WHERE list_id=? AND synonyms!=''` | ❌ **不管 status**，已掌握也可能被抽中重复学 |
| 测试模式 | `WHERE list_id=?` | ❌ 全词库随机，无法专门巩固"自认为已掌握"的词 |

用户诉求："学习模式应该只学没学会的、测试模式应该专门考已经掌握的（用来复习验证是否真掌握）"。

## What Changes

- **同义词学习选词**：`synonym_start` SQL 增加 `AND status='unmastered'` 条件，对齐普通学习流
- **测试模式选词**：`test_start` SQL 增加 `AND status='mastered'` 条件，测试只考已掌握的词
- **测试模式门槛校验**：已掌握词 < 4 时（干扰项要求 ≥4），SHALL 提示"当前词库已掌握词不足 4 个，请先学习一些单词再来测试"并跳回首页
- **UI 文案适配**：
  - `test_setup.html` 的"从全词库（X 个单词）随机出题"→ 改为"从已掌握的 **X** 个单词中随机出题"
  - 题数输入的 `max` 从 `stats.total` 改为 `stats.mastered`
  - `synonym_setup` 已有的 `with_synonyms` 展示逻辑更新为"未掌握且有同义词"数量

## Capabilities

### New Capabilities
<!-- 无新增 capability -->

### Modified Capabilities
- `synonym-flashcard`: 选词范围收窄为"未掌握 + 含同义词"
- `word-list-management`: `get_list_stats` 需补充"未掌握且含同义词"的统计字段（synonym_setup 页面 max 依赖）

## Impact

- 代码：`app.py`
  - `synonym_start` SQL 增加 status 条件
  - `test_start` SQL 增加 status 条件 + 门槛校验
  - `test_setup` 视图传 `mastered_count` 用于模板 max
  - `get_list_stats` 增加 `unmastered_with_synonyms` 字段
  - `synonym_setup` 视图使用新字段
- 模板：`test_setup.html`、`learn_synonym_setup.html` 文案 + max 属性调整
- DB：无 schema 变更
- 测试：新增 6-8 个测试覆盖三种选词条件、边界（已掌握不足 4）、干扰项池等
