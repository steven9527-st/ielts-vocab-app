## Context

**当前 status 枚举**（`words.status`）：
- `'unmastered'`：默认，未学过或未通关
- `'mastered'`：学习通关后升级；测试模式从此池选词

**mastered 引用点全面梳理**（`app.py` + templates）：

| 位置 | 用途 | 需改动？ |
|---|---|---|
| `get_list_stats` L250-260 | 统计 mastered / unmastered 数 | 是（分离 fully_mastered） |
| `learn_start` L917 | 普通学习选词（`AND status='unmastered'`） | 否 |
| `synonym_start` L1623 | 同义词学习选词（`AND status='unmastered'`） | 否 |
| `quiz_submit` L1290, 1336 | 通关时 `UPDATE ... SET status='mastered'` | 否（学习通关只升到 mastered） |
| `test_setup` L1453 | 门槛校验 `stats['mastered'] < 4` | 是（改判定语义） |
| `test_start` L1473, 1486 | 测试选词（`AND status='mastered'`） | 是（额外排除 fully_mastered） |
| `PATCH /library/word/<id>` L1826 | status 白名单 `('mastered', 'unmastered')` | 是（加 fully_mastered） |
| `templates/library.html` | 徽章展示 + 点击切换 | 是（三态循环） |
| `templates/index.html` | metric 卡片 | 是（加一张卡） |
| 通关页/测试结果页 | 展示 | 是（加勾选区） |

## Goals / Non-Goals

**Goals:**
- `fully_mastered` 词彻底"毕业"，不再出现在**任何**学习/测试选词中
- 用户在测试完成 + 学习通关后有清晰的入口把当次单词升级为 fully_mastered
- 用户可通过词库管理页手动切回 mastered（回退机制）
- 首页 metric 清晰反映三种状态词数
- 老数据兼容：现有 mastered 词保持 mastered，用户主动勾选才升级

**Non-Goals:**
- 不引入间隔重复（艾宾浩斯）
- 不引入自动降级（例如"30 天未复习自动降回 mastered"）
- 不改 `study_log` 表结构
- 不改「今日新增掌握」的统计口径（study_log 的 learn/learn_synonym+accuracy=1.0 仍是数据源；fully_mastered 升级不写 study_log）

## Decisions

### Decision 1: 数据模型 —— 三值枚举 vs 布尔字段

**选择**：扩展 `words.status` 枚举，加入 `'fully_mastered'`（用户确认 3A）。

**理由**：
- 单一字段真值单一来源，不会出现"status=mastered 但 fully_mastered=true"的不一致
- SQLite TEXT 字段扩容无需 ALTER，向下兼容
- 大多数选词逻辑本来就是 `WHERE status IN (...)` 或等值判断，改动小

**替代方案 B**：加布尔 `fully_mastered` 字段。被否决——两个字段易冲突。

### Decision 2: 首页 metric 卡片布局

**选择**：4 张等宽卡片 `[词库总数] [已掌握] [完全掌握] [未掌握]`（用户 1B）。

**关键**：
- "已掌握" 数字只算 `status='mastered'`（**从 fully_mastered 中分离**）
- 三者关系：`mastered + fully_mastered + unmastered == total`

**替代**：只加"完全掌握"角标到已掌握卡片。被否决——用户明确要独立卡。

### Decision 3: 交互流 —— 勾选提交模型（3C 用户明选）

**选择**：默认全部**不勾选**（避免用户误升级 + 保守），用户手动勾选想升级的词 + 底部「加入完全掌握」按钮统一提交。

**流程细节**：
1. 用户完成测试/通关 → 展示结果页
2. 页面下方展示本次题目单词列表（表格：英文 / 释义 / 你的答题 ✓/✗）
3. 每行左侧 checkbox（`unchecked`）
4. 底部按钮「加入完全掌握（0/10）」——动态显示已勾选数
5. 用户点击 → POST `/mastery/promote` with word_ids → 后端 UPDATE status='fully_mastered'
6. 成功后 button 变"已加入 X 个" + 页面停留（用户可看到反馈），提供「返回首页」入口

**边界**：一个词都不勾选也 OK，直接返回首页；后端 `word_ids=[]` 时 no-op 返回 success。

### Decision 4: 词库管理页三态切换 UI

**选择**：点击徽章循环切换 `未掌握 → 已掌握 → 完全掌握 → 未掌握`。

**颜色**：
- 未掌握：蓝色（保持现状）
- 已掌握：绿色（保持现状）
- 完全掌握：金色/紫色（新增，用 `--clr-orange` 或 `--clr-purple`，看 CSS 变量有哪个）

**替代**：下拉框。被否决——单个词一次点击不方便。

### Decision 5: fully_mastered 升级路径 —— 是否只走通关/测试完成后？

**选择**：三条路径都可以：
- **测试完成页勾选**（主路径，用户预期）
- **学习通关页勾选**（对齐体验）
- **词库管理页手动切换**（回退/纠错机制）

不允许"完全掌握"的词再次通过学习通关升级（因为学习模式选词已排除 mastered/fully_mastered），只能靠词库管理页手动切回 mastered。

### Decision 6: 数据兼容性

**问题**：现有 `mastered` 词升级到 `fully_mastered` 需要用户主动操作，还是自动？

**选择**：**不自动升级**。老数据全部保持 mastered，用户主动勾选才升级。避免破坏现有用户预期。

## Risks / Trade-offs

- **[风险] 用户勾选后误操作 fully_mastered，想撤回**：通过词库管理页手动切回 mastered（Decision 4 支持）。
- **[风险] 测试模式全 fully_mastered，无题可考**：与"mastered < 4"同样门槛校验兜底，setup 页拦截 + 引导。
- **[风险] 首页 4 张卡片布局在小屏（手机）挤**：CSS grid 自适应，超 3 张自动换行——本 App 目前已用 `.metric-grid`，样式微调即可。
- **[UI 变更] 现有 metric 卡片测试断言可能失败**：全量测试跑一遍，更新。

## Migration Plan

- 部署即生效，无 schema 变更
- 现有 mastered 词保持不变（不自动升级）
- 用户可在测试完成后 / 词库管理页主动升级
