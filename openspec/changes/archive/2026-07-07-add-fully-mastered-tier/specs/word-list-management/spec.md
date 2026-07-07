## ADDED Requirements

### Requirement: get_list_stats 补充 fully_mastered 字段

`get_list_stats(list_id)` 返回值 SHALL 新增字段 `fully_mastered`，并明确 `mastered` 字段口径为**仅 status='mastered'（不含 fully_mastered）**。

#### Scenario: 三态计数正确

- **GIVEN** 词库有 100 词：50 unmastered / 30 mastered / 20 fully_mastered
- **WHEN** 调用 `get_list_stats(list_id)`
- **THEN** 返回 SHALL 包含
  - `total: 100`
  - `unmastered: 50`
  - `mastered: 30`（**不含 fully_mastered**）
  - `fully_mastered: 20`
- **AND** `unmastered + mastered + fully_mastered == total`

### Requirement: 首页 metric 卡片新增「完全掌握」

首页 `index.html` metric 区 SHALL 展示 4 张卡片：`[词库总数] [已掌握 X] [完全掌握 Y] [未掌握 Z]`。

#### Scenario: 4 卡片展示

- **GIVEN** 当前词库统计 stats={total:100, mastered:30, fully_mastered:20, unmastered:50}
- **WHEN** 首页渲染
- **THEN** 页面 SHALL 展示：
  - "词库总数 100"
  - "已掌握 30"（不再含 fully_mastered）
  - "完全掌握 20"（新增）
  - "未掌握 50"

### Requirement: 词库管理页支持三态徽章循环切换

`library.html` 中每行单词的 status 徽章 SHALL 支持点击循环切换：`未掌握 → 已掌握 → 完全掌握 → 未掌握`。

三态样式区分：
- 未掌握：蓝色（`badge--blue`）
- 已掌握：绿色（`badge--green`）
- 完全掌握：金色（`badge--gold` 或复用 orange 变量）

`PATCH /library/word/<id>` API 的 `status` 白名单 SHALL 扩展为 `('unmastered', 'mastered', 'fully_mastered')`。

#### Scenario: 徽章循环切换

- **GIVEN** 某词当前 status='unmastered'
- **WHEN** 用户点击徽章 3 次
- **THEN** 徽章依次显示"已掌握 → 完全掌握 → 未掌握"
- **AND** DB 中 status 依次为 `mastered → fully_mastered → unmastered`

#### Scenario: PATCH API 接受新状态

- **GIVEN** POST `/library/word/123` with `{"status": "fully_mastered"}`
- **WHEN** 后端处理
- **THEN** 系统 SHALL UPDATE 该词 status='fully_mastered'
- **AND** 返回成功响应
