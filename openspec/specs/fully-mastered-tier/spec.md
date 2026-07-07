# fully-mastered-tier Specification

## Purpose
TBD - created by archiving change add-fully-mastered-tier. Update Purpose after archive.

## Requirements
### Requirement: 单词状态引入「完全掌握」第三档

`words.status` 字段 SHALL 支持三个枚举值：
- `'unmastered'`：默认，未掌握
- `'mastered'`：学习通关后升级；测试模式的题库
- `'fully_mastered'`：用户主动确认"彻底会了"；不再进入任何学习/测试

状态跃迁规则：
- `unmastered → mastered`：普通学习通关（`quiz_submit` 100% 通关）；同义词学习通关
- `mastered → fully_mastered`：用户在测试完成页 / 通关页勾选并点击「加入完全掌握」；或词库管理页手动切换
- `fully_mastered → mastered`：只能通过词库管理页手动切回（无自动降级）
- 任意状态可通过词库管理页手动切换（三态循环）

#### Scenario: 现有 mastered 词保持不变

- **GIVEN** 应用升级前用户已有若干 mastered 词
- **WHEN** 应用升级到本 change 版本
- **THEN** 这些词的 status SHALL 仍是 mastered
- **AND** SHALL 不自动升级为 fully_mastered

#### Scenario: fully_mastered 词不再参与测试

- **GIVEN** 词库有 20 个 mastered + 5 个 fully_mastered 词
- **WHEN** 用户进入测试模式
- **THEN** 题库池 SHALL 是 20 个 mastered 词
- **AND** SHALL 不含任何 fully_mastered 词

### Requirement: 测试完成页支持"加入完全掌握"

`test_result.html`（测试模式结果页）SHALL 展示本次测试的所有题目单词，每个词旁边有 checkbox（默认**未勾选**），用户可勾选想升级的词，点击「加入完全掌握」按钮后一次性提交。

#### Scenario: 展示题目单词列表

- **GIVEN** 用户完成一次 10 题测试
- **WHEN** 结果页渲染
- **THEN** 页面 SHALL 展示本次 10 个词的列表
- **AND** 每行 SHALL 展示：英文 / 中文释义（或同义词，取决词库 type）/ 答题结果（✓/✗）/ 复选框
- **AND** 所有复选框 SHALL 默认为未勾选

#### Scenario: 勾选并提交

- **GIVEN** 用户勾选了其中 3 个词
- **WHEN** 用户点击「加入完全掌握」按钮
- **THEN** 前端 SHALL POST `/mastery/promote` with `{"word_ids": [3个id]}`
- **AND** 后端 SHALL 对这 3 个词执行 `UPDATE words SET status='fully_mastered'`（仅当当前 status='mastered' 时）
- **AND** 页面 SHALL 展示成功反馈（如"已加入 3 个词到完全掌握"）

#### Scenario: 未勾选任何词不提交

- **GIVEN** 用户未勾选任何词，直接点「返回首页」
- **WHEN** 用户离开页面
- **THEN** 所有词 status SHALL 保持不变

### Requirement: 学习通关页支持"加入完全掌握"

`quiz_result.html`（learn 模式通关分支，含普通流 + 同义词流）SHALL 展示与测试完成页相同的单词列表 + checkbox + 提交按钮。

行为语义与测试完成页一致。

#### Scenario: 通关页展示单词列表

- **GIVEN** 用户学习 5 词通关（普通流或同义词流）
- **WHEN** 通关页渲染
- **THEN** 页面 SHALL 展示本次 5 个词的列表
- **AND** 每行有 checkbox（默认未勾选）
- **AND** 底部有「加入完全掌握」按钮

### Requirement: POST /mastery/promote 端点

系统 SHALL 提供新路由 `POST /mastery/promote`，接收 `{"word_ids": [...]}`，把这些词 status 从 `'mastered'` 升级为 `'fully_mastered'`。

#### Scenario: 正常升级

- **GIVEN** word_ids=[1, 2, 3]，这 3 个词当前 status='mastered'
- **WHEN** POST `/mastery/promote`
- **THEN** 系统 SHALL 对这 3 个词 UPDATE status='fully_mastered'
- **AND** 返回 `{"ok": true, "promoted": 3}`

#### Scenario: 状态不满足条件跳过

- **GIVEN** word_ids=[1, 2, 5]，其中词 5 当前 status='unmastered'
- **WHEN** POST `/mastery/promote`
- **THEN** 系统 SHALL 只升级 status='mastered' 的词（1、2）
- **AND** 词 5 状态 SHALL 保持 unmastered
- **AND** 返回 `{"ok": true, "promoted": 2}`

#### Scenario: 空列表安全返回

- **GIVEN** word_ids=[]
- **WHEN** POST `/mastery/promote`
- **THEN** 返回 `{"ok": true, "promoted": 0}`，不执行 UPDATE
