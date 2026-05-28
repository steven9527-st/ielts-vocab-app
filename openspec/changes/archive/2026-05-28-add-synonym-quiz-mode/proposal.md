## Why

同义词词库（如雅思 C19 配对题表）的学习重点是「英文 ↔ 英文同义词」之间的双向映射，但现在测验出题逻辑是写死的「英文词 → 4 个中文释义」结构。这意味着：

- 用户刚导入了同义词词库，进测验时却被迫做"中英对译"的题，与同义词学习目标错位
- `chinese` 字段在双英文列展开后只有半段释义（如 `keep sth off → 保持某事关闭`），干扰项也是其他词的半段中文，组成的题目语义混乱

让测验在**同义词词库**下自动切换为「英文词 → 4 个英文同义词」结构，是真正贴合同义词配对学习目标的体验。

## What Changes

- **词库表新增 `type` 字段**：`'standard'`（默认）/ `'synonym'`（同义词词库），用于持久化导入时的语义意图
- **导入流程**：标准模式导入 → `type='standard'`；同义词模式导入 → `type='synonym'`
- **旧词库自动迁移**：首次启动时扫描既有 `word_lists`，按 `synonyms` 字段填充率 ≥ 80% 自动标记 `type='synonym'`，否则保持 `'standard'`
- **测验出题逻辑**：`generate_quiz_questions()` 根据 `list.type` 分支——
  - `'standard'`：现有逻辑（英文 → 4 个中文释义）
  - `'synonym'`：新逻辑（英文 → 4 个英文同义词，正确答案为本词的 synonyms，干扰项从同词库其他词的 synonyms 中随机选 3 个）
- **范围限定**：仅影响**学习测验**与**正式文字测试**；**听力测试不动**（听力题语义本身要求"听英文 → 选释义"，改成英文同义词反而不自然）
- **错题循环、回退改答案、卡片回填等流程**：完全复用既有机制，不做任何改动（出题逻辑变化对这些路径透明）

## Capabilities

### New Capabilities

- `synonym-quiz`: 同义词词库下的测验出题规则——4 选 1 选项均为英文同义词，干扰项策略，触发条件，听力测试豁免

### Modified Capabilities

- `import-excel`: 列映射应用阶段记录词库 type 字段；标准模式记 `'standard'`，同义词模式记 `'synonym'`

## Impact

**数据库**：
- `word_lists` 表新增 `type TEXT NOT NULL DEFAULT 'standard'`（带幂等 ALTER 迁移）
- 启动时执行 lazy 迁移：扫描既有词库 synonyms 填充率，自动设置 type

**后端**：
- `database.py` `init_db()`：加 ALTER + 自动迁移函数
- `app.py` `/import/excel_apply` 路由：apply_mapping 完成后，按 import_mode 写入词库 type
- `app.py` `generate_quiz_questions()`：增加 `list_type` 分支逻辑
- 同义词词库测验出题需新增干扰项采集：从同词库其他词的 synonyms 中随机抽 3 个、去重、避免与正确答案同义

**前端**：
- 无变更（quiz.html 只渲染 `question.options`，对选项是中文还是英文透明）
- 可选 nice-to-have：词库管理页显示词库 type 标签（如 `[同义词]`），但本次不做

**测试**：
- 新增 `tests/test_synonym_quiz.py`：覆盖
  - 词库 type 字段导入时正确写入
  - 旧词库自动迁移逻辑（填充率 80% 阈值）
  - generate_quiz_questions 在 type='synonym' 时输出英文选项
  - 干扰项不与正确答案重复
  - type='standard' 时维持原中文选项行为（向后兼容）
  - 听力测试模式即使在 'synonym' 词库下仍出中文选项（豁免）

**风险**：
- 中等。涉及数据库迁移与出题核心逻辑分支，需要测试覆盖充分
- 干扰项可能不足（同词库其他词也是同义词配对，可用的英文同义词总数 ≥ 4 是前提）—— 不足时降级为中文选项 + 警告
