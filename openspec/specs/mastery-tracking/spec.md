# mastery-tracking Specification

## Purpose
TBD - created by archiving change fix-mastered-count. Update Purpose after archive.

## Requirements
### Requirement: 通关时以学习会话原始全集为准更新 mastered

学习通关流程（`quiz_submit`, mode='learn', accuracy=1.0）SHALL 使用「本次学习会话的原始 word_ids 全集」作为 UPDATE mastered、写入 study_log、以及通关页展示 total 的数据源，而非错题重做后被覆盖的子集。

数据源规则：
- 普通学习流：从 `learn_session.word_ids` 读取（DB 权威来源，不受 quiz_retry 影响）
- 同义词学习流：从 `session['quiz_original_word_ids']` 读取（learn_quiz 入口保存的原始副本）

#### Scenario: 20 词学习含错题重做通关

- **GIVEN** 用户开始一次「学习 20 个词」的普通学习流
- **AND** 首轮测验答对 18 个 / 答错 2 个
- **AND** 点击「还有 2 题需要重做」重做后通关（accuracy=100%）
- **WHEN** `quiz_submit` 处理通关
- **THEN** 系统 SHALL 从 `learn_session.word_ids` 读取原始 20 个词 ID
- **AND** SHALL 对全部 20 个词执行 `UPDATE words SET status='mastered'`
- **AND** SHALL 写入 `study_log` 记录 `word_ids=原始20个`, `accuracy=1.0`
- **AND** 通关页 SHALL 显示「本次学习的 **20** 个单词已全部标记为已掌握」

#### Scenario: 首轮零错误直接通关

- **GIVEN** 用户学 5 个词，首轮全对通关
- **WHEN** `quiz_submit` 处理通关
- **THEN** total SHALL 为 5，mastered SHALL 更新 5 个词
- **AND** 与走重做流程的语义完全一致（无退化）

#### Scenario: 同义词流通关也标 mastered

- **GIVEN** 用户开始一次「同义词学习 8 个词」流
- **AND** 学完 8 张卡片进入测验
- **AND** 通关（accuracy=100%）
- **WHEN** `quiz_submit` 的 `is_synonym_flow` 分支处理通关
- **THEN** 系统 SHALL 对全部 8 个词执行 `UPDATE words SET status='mastered'`
- **AND** SHALL 写入 `study_log` 记录 `mode='quiz'`（保持既有语义）
- **AND** 通关页 SHALL 显示「本次共测验了 **8** 个同义词，全部答对」

### Requirement: 首页显示"今日新增掌握"数量

首页在「今日已通关 ✅」提示的正下方 SHALL 显示一行「今日新增掌握 **N** 个」文本，N 是当前词库当天所有通关会话（含普通学习 + 同义词学习）合并去重后的单词总数。

未通关（`completed_today=False`）时 SHALL 不显示此行。

#### Scenario: 单次通关后显示 20

- **GIVEN** 用户当天完成 1 次普通学习通关，本次 20 个词
- **WHEN** 用户返回首页
- **THEN** SHALL 显示「今日已通关 ✅」
- **AND** 下方 SHALL 显示「今日新增掌握 **20** 个」

#### Scenario: 多次通关合并去重

- **GIVEN** 用户当天完成 3 次会话
  - 会话 A：普通学习 20 词
  - 会话 B：同义词学习 8 词
  - 会话 C：同义词学习 5 词，其中 2 个词与 A 重复
- **WHEN** 用户返回首页
- **THEN** SHALL 显示「今日新增掌握 **31** 个」（20+8+5-2 = 31）

#### Scenario: 跨词库不混算

- **GIVEN** 用户当天在词库 X 通关 10 词、词库 Y 通关 5 词
- **WHEN** 用户在词库 X 首页
- **THEN** SHALL 显示「今日新增掌握 **10** 个」（不含词库 Y 的 5 个）

#### Scenario: 未通关不显示

- **GIVEN** 用户当天未完成任何学习通关
- **WHEN** 用户访问首页
- **THEN** 页面 SHALL 不出现「今日新增掌握」文案

### Requirement: 历史遗留同义词学习数据回补

应用启动时 SHALL 一次性扫描 `study_log` 中所有 `mode='learn_synonym' AND accuracy=1.0` 的记录，把其 `word_ids` 中当前 `status='unmastered'` 的词更新为 `mastered`，以修正 `add-synonym-learn-quiz` 引入的历史数据缺陷。

#### Scenario: 首次启动执行迁移

- **GIVEN** 数据库中存在 `mode='learn_synonym' AND accuracy=1.0` 的历史记录
- **AND** 记录中的部分词当前 `status='unmastered'`
- **WHEN** 应用启动调用 `init_db()`
- **THEN** 系统 SHALL 把这些词 UPDATE 为 `status='mastered'`
- **AND** 已经是 `mastered` 的词 SHALL 不变

#### Scenario: 保护手动降级

- **GIVEN** 用户在词库管理页把某个曾经 mastered 的词手动改回 unmastered
- **AND** 该词在 study_log 中有 `learn_synonym+accuracy=1.0` 历史记录
- **WHEN** 应用启动执行迁移
- **THEN** 系统 SHALL 不动这个词（用户意图优先）
- **AND** 迁移 SQL SHALL 用 `WHERE id=? AND status='unmastered'` 语义确保幂等

#### Scenario: 迁移幂等

- **GIVEN** 迁移已执行过一次
- **WHEN** 应用再次启动
- **THEN** 迁移 SHALL 可再次执行，结果与前一次一致，不产生错误
