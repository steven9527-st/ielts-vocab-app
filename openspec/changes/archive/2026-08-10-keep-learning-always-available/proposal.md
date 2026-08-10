## Why

当前学习模式存在阻断：当词库中所有单词均标记为"已掌握"（`status='mastered'`）后，首页的"开始学习"按钮被禁用，仅保留"测试模式"。用户反馈需要持续保留学习功能，即使全部掌握也可以重新翻卡回顾。

## What Changes

- `index.html`：移除 `stats.unmastered == 0` 时禁用按钮的条件，学习按钮始终可用
- `app.py` `learn_start()`：选词逻辑改为——先查未掌握词，未掌握词不足时用全词库补齐到 n 个（允许重复学习已掌握词）
- `learn_setup.html`：`max` 和 `default_n` 的计算改为基于 `max(stats.unmastered, 1)` 或 `stats.total` 兜底，确保全部掌握时 setup 页仍可正常使用

## Capabilities

### Modified Capabilities

- `word-list-management`：学习功能的选词逻辑不受已掌握词数限制

## Impact

- **首页**: 学习按钮永不 disabled
- **学习流程**: setup → start（自动补全词汇池）→ card → quiz → done，流程不变
- **测试**: 不影响，测试仍从 mastered 池选词
- **数据库**: 无 schema 变更
