# 多词库选择 + 单词发音 + 听力测试

## Why

当前应用在三个方面体验不足，影响使用效率与学习场景覆盖：

1. **多词库管理割裂**：词库管理页只能查看单一词库，无法直接新建；词库切换仅能在首页 dropdown 完成，进入学习/测试后无法切换。
2. **缺少发音能力**：单词卡片只显示音标文本，用户无法听到读音，对于 IELTS 这类强听说要求场景属于明显短板。
3. **测试单一**：只有"看英文选中文"一种形式，缺少听力测试，无法训练听辨能力。

## What Changes

本提案合并交付三组相互独立但 UI 互通的能力：

### A. 多词库选择体验升级
- 词库管理页右上角新增"+ 新建词库"按钮，点击跳转 `/import`
- 全站顶部导航条新增"当前词库 ▼"切换按钮，在所有页面均可见
- 学习/测试入口拦截：当词库数量 ≥ 2 且 session 中无 `list_picked` 标记时，弹出"选择词库"浮层
- 学习/测试**进行中**点击切换词库 → 弹出确认框"将放弃当前进度"，确认后 abandon 当前 session/quiz

### B. 单词发音
- 卡片（`flashcard.html`）音标旁新增 🔊 按钮
- 使用浏览器原生 Web Speech API（`speechSynthesis`），单一发音（en-US）
- 进入卡片**不**自动播放，仅在用户点击按钮时朗读 `word.english`

### C. 听力测试
- `test_setup.html` 新增"测试类型"单选：○ 文字测试 ○ 听力测试
- 听力测试题目页：英文区域替换为 🔊 按钮，**进入题目自动朗读一次** + 用户可重复点击
- `study_log.mode` 字段从 `'test'` 拆分为 `'test_text'` / `'test_audio'`，历史 `'test'` 记录视为 `test_text`
- streak 计算逻辑保持不变（仍只看 `learn` 模式 accuracy=1.0）

## Impact

- **Affected specs**：新增 3 个 capability spec
  - `word-list-management`：多词库选择与切换
  - `pronunciation`：单词朗读
  - `audio-test`：听力测试模式
- **Affected code**：
  - `app.py`：新增 `/api/lists`、`/api/pick_list`、`/api/switch_list_safe`；`test_start` 接收 `test_type` 参数
  - `database.py`：注释更新 `study_log.mode` 枚举（schema 不变）
  - `templates/base.html`：顶部导航加词库切换组件
  - `templates/library.html`：右上角加"+ 新建词库"
  - `templates/test_setup.html`：加测试类型单选
  - `templates/flashcard.html`：音标旁加 🔊 按钮
  - `templates/quiz.html`：根据 `question_type` 渲染文字/音频两种形态
  - `templates/_list_picker.html`（新增）：词库选择浮层 partial
  - `templates/test_result.html`：显示测试类型徽标
  - `static/style.css`：浮层、按钮、徽标样式
- **Breaking changes**：无。`study_log` 中历史 `'test'` 记录通过查询时归一化为 `test_text`，不做物理迁移。
- **风险**：Web Speech API 在不同操作系统/浏览器音色差异较大；提供 graceful degradation——若 `speechSynthesis` 不可用，🔊 按钮显示禁用态并 tooltip 提示。
