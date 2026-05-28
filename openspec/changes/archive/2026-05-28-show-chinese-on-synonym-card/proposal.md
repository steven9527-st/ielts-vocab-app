## Why

同义词学习的目标是「英文词 ↔ 英文同义词」之间建立联想（提升词汇网络），但现有同义词卡片在**正面只显示英文+音标**——对于刚导入新词库的用户，遇到陌生词组（如 `alarming rate of loss`）时既不认识本词、又看不懂同义词，会陷入"两眼抓瞎"的状态。

虽然背面已经有中文释义，但被以"配角小字"放在最底部（13px 灰色），翻面后用户的注意力还是被同义词主体吸走，中文释义存在感很弱。

让中文以「配角」姿态在正反面**都可见**，能给用户提供持续的语义锚点，不打断同义词学习的主路径。

## What Changes

- **同义词卡片正面**：在英文/音标下方新增一行中文释义（14px 灰色，配角样式），仅当 `word.chinese` 非空时显示
- **同义词卡片背面**：在 `SYNONYMS` 列表中，对夹杂的中文同义词项以灰色显示（与英文同义词的黑色形成轻量区分），不影响主义项排版
- **触发逻辑**：按词级别判断，每张卡片独立——`word.chinese` 为空则该卡片正面不显示中文条；`word.synonyms` 中无中文项则背面无灰色区分
- **保持不变**：背面已有的"底部中文释义块"维持当前 13px 灰色样式与位置；正反面英文同义词主体的字号、颜色、布局完全不变

## Capabilities

### New Capabilities

- `synonym-flashcard`: 同义词翻卡学习的卡片渲染规则——包括正反面布局、中文释义的显示时机与样式、SYNONYMS 列表内中英文项的视觉区分

### Modified Capabilities

（无）

## Impact

**前端**：
- `templates/flashcard_synonym.html`：正面 `<div class="flashcard__front">` 内追加条件渲染的中文行；背面 SYNONYMS 列表加 CJK 字符检测给中文项打 class
- `static/style.css`：新增 `.synonym-front-chinese`（14px 灰色）与 `.synonym-syn--cn`（同义词项中文灰色）两个工具类

**后端**：
- 无变更（`word.chinese` `word.synonyms` 字段已存在；不新增数据模型；不新增路由）

**数据**：
- 无 schema 变更
- 旧数据完全兼容：`word.chinese` 为空字符串的卡片正面无变化

**测试**：
- 新增 `tests/test_synonym_card_render.py`（轻量）：验证模板渲染输出在 `chinese` 非空时包含中文文本与对应 class；空时不渲染
- 验证 SYNONYMS 中文项被打上 `synonym-syn--cn` class

**风险**：
- 极小。纯前端改动，不影响数据流；最坏情况是 CSS 样式对某些屏幕宽度不理想，可微调
