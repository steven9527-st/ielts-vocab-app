## 1. 修复英文大写显示

- [x] 1.1 移除 `static/style.css` 中 `.flashcard__word` 的 `text-transform: uppercase`
- [x] 1.2 移除 `static/style.css` 中 `.quiz-english` 的 `text-transform: uppercase`
- [x] 1.3 移除 `static/style.css` 中 `.wrong-item__english` 的 `text-transform: uppercase`

## 2. 删除词库功能

- [x] 2.1 在 `app.py` 中添加 `DELETE /api/list/<list_id>` 路由（删除词库 + 外键级联清理）
- [x] 2.2 在 `templates/library.html` 页面头部添加"删除此词库"按钮（红色危险样式）
- [x] 2.3 添加删除确认 JS 逻辑，删除成功后清除 session list_id 并跳转首页

> 全部已实现并在线上正常运行。
