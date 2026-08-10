## Why

当前应用支持标准词库（standard）和同义词词库（synonym）两种类型，但缺少"默写"训练场景——用户看中文释义、凭记忆写出英文单词。这对于需要加强拼写和记忆深度（如雅思写作备考）的用户是高频需求。默写词库作为新的词库类型，可复用现有词库管理、学习流和掌握度追踪体系。

## What Changes

- `word_lists.type` 新增 `'dictation'` 类型，作为第三种词库类型
- 导入流程（Excel/CSV）支持选择"默写词库"类型，设置词库 `type='dictation'`
- 新增默写学习模式（`/learn/dictation/*` 系列路由）：
  - 翻卡正面显示中文释义，用户凭记忆默写英文
  - 翻卡背面显示英文单词、音标、词性
  - 支持前进/后退翻卡浏览
  - 学完最后一张后自动进入测验（复用现有测验框架）
- 测验通关后更新词状态为 `mastered`，写 `study_log`，对齐现有学习流
- 首页 stats 和导航栏自动适配默写词库（复用现有词库切换和统计机制）
- 默写词库的管理（编辑单词、删除、三态切换）与标准词库一致

## Capabilities

### New Capabilities

- `dictation-vocabulary`: 默写词库类型的定义、识别和导入支持
- `dictation-flashcard`: 默写学习模式的核心交互——中文正面默写英文翻卡、前进/后退、学完自动进入测验

### Modified Capabilities

- `word-list-management`: 词库类型枚举从 `('standard', 'synonym')` 扩展为 `('standard', 'synonym', 'dictation')`，`_get_list_type` 函数支持 `'dictation'` 返回值

## Impact

- **数据库**: `word_lists.type` 字段新增 `'dictation'` 值（无 schema 变更，复用现有列）
- **后端**: `app.py` 新增 `/learn/dictation/*` 路由（约 6 个）、`_get_list_type` 扩展、`import_confirm` 支持默写词库类型
- **前端**: 新增 `learn_dictation_setup.html`、`flashcard_dictation.html` 模板；`import_excel_mapping.html` 新增默写词库选项
- **测试**: 新增默写学习流的集成测试
