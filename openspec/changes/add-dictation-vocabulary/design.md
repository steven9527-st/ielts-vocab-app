## Context

应用当前支持两种词库类型：`standard`（标准英中词库）和 `synonym`（同义词词库）。`word_lists.type` 字段驱动测验出题方式（中文释义 vs 英文同义词）。默写词库是第三种类型——用户看中文默写英文——需要新的学习流程但可复用现有测验、词库管理和统计体系。

**现有架构参考：**
- 学习流：`learn_setup → learn_start → learn_card → learn_next/prev → learn_quiz → quiz_question → quiz_answer → quiz_submit`
- 同义词学习流（独立模式）：`synonym_setup → synonym_start → synonym_card → synonym_next/prev → _synonym_enter_quiz_or_done → learn_quiz → quiz_submit → synonym_done`
- 默写学习流采用与同义词类似的独立模式（基于 session 而非 learn_session），但卡片正反面互换

## Goals / Non-Goals

**Goals:**
- 新增 `dictation` 词库类型，支持导入时选择
- 默写翻卡正面显示中文释义（大字），背面显示英文 + 音标 + 词性
- 支持前进/后退翻卡（游标模型，复用同义词的 `syn_index` 模式）
- 学完最后一张自动进入测验（复用 `learn_quiz` + `generate_quiz_questions`）
- 测验通关后写 `study_log(mode='learn_dictation')` + 更新 `words.status='mastered'`
- 默写词库在首页 stats、词库管理页正常工作（复用现有机制）

**Non-Goals:**
- 默写模式的拼写检查（用户手动翻卡对照，不做自动判分）
- 默写词库的自动识别/迁移（新导入时手动选择类型）
- 手机端适配（沿用现有响应式布局）

## Decisions

### 1. 词库类型扩展方式
**选择**: `word_lists.type` 新增 `'dictation'` 值，`_get_list_type()` 返回 `'dictation'` 时走标准出题逻辑（中文选项）。
**理由**: 默写词库本身不需要特殊出题方式——测验时和标准词库一样出"英文 → 选中文释义"。默写的核心是"翻卡学习"环节（正面中文默写英文），不是测验方式。
**替代方案**: 为默写测验新增一种出题方式（给中文写英文）——过度复杂，且翻卡本身已经是默写训练。

### 2. 默写学习流架构
**选择**: 复用同义词学习的独立模式（基于 Flask session 的游标模型），不创建 `learn_session` 表记录。
**理由**: 同义词学习流已验证此模式可行（`_synonym_enter_quiz_or_done`、`syn_index` 游标、`pending_quiz_word_ids` 机制）。默写只需将正反面互换。
**替代方案**: 复用普通学习的 `learn_session` 表——会增加 `current_index` 迁移复杂度，且默写不需要"继续学习"的 DB 持久化。

### 3. 翻卡模板复用 vs 新建
**选择**: 新建 `flashcard_dictation.html` 模板。
**理由**: 默写卡片的正面/反面与标准卡片完全相反（正面中文 vs 正面英文），且需要额外的"默写提示"交互（如显示单词长度）。硬复用标准模板会导致条件分支爆炸。

### 4. 导入类型选择位置
**选择**: 在 Excel 列映射页（`import_excel_mapping.html`）的"导入模式"选项中新增"默写词库"单选框。
**理由**: 与现有"标准词库/同义词词库"选择位置一致，用户操作路径熟悉。PDF 导入路径暂不涉及（默写词库数据格式简单，Excel 足够）。

## Risks / Trade-offs

- **Risk**: 用户混淆默写词库和标准词库的学习入口 → 在 setup 页明确标注"默写模式：看中文默写英文"
- **Risk**: 默写词库被误用于测验模式（`test_setup`）→ 允许但无特殊处理，按标准出题逻辑
- **Trade-off**: 默写不做自动拼写检查 → 降低复杂度，翻卡对照即足够
