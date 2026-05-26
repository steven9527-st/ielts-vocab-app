## Context

当前项目是本地运行的 Flask + SQLite 雅思词汇学习应用。两个独立问题需要修复：
1. CSS 中 3 处 `text-transform: uppercase` 覆盖了模板层的小写转换，导致单词卡片、测验题目、错题列表的英文全部大写显示
2. 词库管理页面只有"导入新词库"按钮，缺少删除整个词库的功能；数据库外键级联已配置好（words/learn_session CASCADE, study_log SET NULL）

## Goals / Non-Goals

**Goals:**
- 英文单词在所有页面统一小写显示
- 用户可以从词库管理页面删除整个词库（含关联数据）

**Non-Goals:**
- 不修改数据库中存储的英文大小写（只改显示层）
- 不做批量删除多个词库
- 不做回收站/恢复机制

## Decisions

**1. CSS 修复方式：直接移除 `text-transform: uppercase`**
- 替代方案：改为 `text-transform: lowercase` — 不需要，模板已有 `| lower`
- 选择直接删除，让模板层的 `| lower` 控制显示，职责更清晰

**2. 删除词库 API 设计：`DELETE /api/list/<list_id>`**
- 与现有 `DELETE /api/word/<id>` 风格一致
- 返回 `{ok: true}` JSON
- 删除前校验 list_id 存在性

**3. 删除后导航策略**
- 若删除的是当前 session 中的词库 → 清除 session 的 list_id → 重定向到首页（首页会自动选取第一个可用词库）
- 若还有其他词库存在，用户可在首页切换

## Risks / Trade-offs

- [误删词库数据丢失] → 前端加 `confirm()` 二次确认弹窗，按钮用红色危险样式区分
- [删除正在进行中的 learn_session] → 外键 CASCADE 自动清理，session 中残留的 learn_session_id 在下次请求时会被重定向到首页处理
