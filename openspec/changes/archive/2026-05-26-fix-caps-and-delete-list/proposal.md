## Why

两个用户体验问题：1) 单词卡片和测验页面的英文单词全大写显示（CSS `text-transform: uppercase` 覆盖了模板层的 `| lower` 过滤器），用户要求改为小写；2) 词库管理页面缺少删除整个词库的功能，目前只能逐个删除单词。

## What Changes

- **修复英文大写显示**：移除 CSS 中 3 处 `text-transform: uppercase` 规则（`.flashcard__word`、`.quiz-english`、`.wrong-item__english`），使模板层 `| lower` 生效
- **新增删除词库功能**：
  - 后端 API：`DELETE /api/list/<list_id>` 路由，删除词库记录（外键 CASCADE 自动清理关联的 words、learn_session）
  - 前端 UI：词库管理页面 (`library.html`) 添加"删除此词库"按钮，带二次确认弹窗
  - 删除后处理：若删除的是当前选中词库，自动切换到剩余词库或跳转首页

## Capabilities

### New Capabilities
- `delete-word-list`: 删除整个词库及其关联数据的能力

### Modified Capabilities

## Impact

- **文件修改**：`static/style.css`（3 处 CSS）、`app.py`（新增路由）、`templates/library.html`（新增 UI）
- **数据库**：依赖已有外键级联（`words ON DELETE CASCADE`, `learn_session ON DELETE CASCADE`, `study_log ON DELETE SET NULL`）
- **API 新增**：`DELETE /api/list/<list_id>` 返回 `{ok: true}`
