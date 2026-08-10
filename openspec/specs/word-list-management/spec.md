# word-list-management Specification

## Purpose
词库管理 capability：负责词库切换、学习/测试中的词库切换保护、单词状态管理、以及关联的 UI 组件。

## Requirements

### Requirement: 词库切换组件全站可见

应用顶部导航栏 SHALL 在所有页面显示"当前词库 ▼"切换组件。

#### Scenario: 多词库场景

- **GIVEN** 系统中存在 2 个或以上词库
- **WHEN** 用户访问任意页面
- **THEN** 顶部导航条 SHALL 显示当前词库名称和下拉箭头
- **AND** 用户点击后 SHALL 展开所有词库列表供选择

#### Scenario: 单词库场景

- **GIVEN** 系统中只有 1 个词库
- **WHEN** 用户访问任意页面
- **THEN** 切换组件 SHALL 显示当前词库名称但不可展开（无切换意义）

#### Scenario: 无词库场景

- **GIVEN** 系统中没有词库
- **WHEN** 用户访问任意页面
- **THEN** 切换组件 SHALL 不显示

### Requirement: 学习/测试中切换词库的保护机制

当用户在学习卡片或测试答题中途切换词库时，系统 SHALL 弹出确认框告知"将放弃当前进度"。

#### Scenario: 学习进行中切换

- **GIVEN** 用户位于 `/learn/card` 页面，存在进行中的 `learn_session`
- **WHEN** 用户在顶部切换组件中选择另一个词库
- **THEN** 浏览器 SHALL 弹出 `confirm("将放弃当前学习进度，确认切换词库？")`
- **AND** 用户确认后，当前 learn_session 状态 SHALL 被更新为 `abandoned`
- **AND** session 中的 `learn_session_id`、`learn_total` SHALL 被清除
- **AND** session 中的 `list_id` SHALL 被设置为新词库 ID
- **AND** 页面 SHALL 跳转到首页

#### Scenario: 测试进行中切换

- **GIVEN** 用户位于 `/quiz/question` 页面（mode=`test_text` 或 `test_audio`）
- **WHEN** 用户切换词库
- **THEN** 浏览器 SHALL 弹出确认框
- **AND** 用户确认后，quiz_token 临时文件 SHALL 被删除
- **AND** session 中 quiz 相关字段（`quiz_token`、`quiz_index`、`quiz_answers`、`quiz_mode`、`quiz_test_type`、`test_count`）SHALL 被清除

#### Scenario: 非进行中切换

- **GIVEN** 用户位于首页、词库管理、设置等非进行中页面
- **WHEN** 用户切换词库
- **THEN** 系统 SHALL 直接切换不弹确认框

### Requirement: 学习/测试入口词库选择浮层

当用户进入学习或测试页面，且当前 session 未明确选择过词库时，系统 SHALL 弹出词库选择浮层。

#### Scenario: 多词库首次进入

- **GIVEN** 系统存在 2 个或以上词库
- **AND** session 中 `list_picked` 为 False 或不存在
- **WHEN** 用户访问 `/learn/setup` 或 `/test/setup`
- **THEN** 页面 SHALL 渲染遮罩浮层，列出所有词库供单选
- **AND** 用户选择一个词库并确认后，`session['list_id']` SHALL 设为该词库 ID
- **AND** `session['list_picked']` SHALL 设为 True
- **AND** 浮层关闭，用户停留在原 setup 页

#### Scenario: 已选择过的会话

- **GIVEN** session 中 `list_picked=True`
- **WHEN** 用户访问 `/learn/setup` 或 `/test/setup`
- **THEN** 系统 SHALL 不弹浮层，使用 `session['list_id']` 直接渲染 setup 页

#### Scenario: 单词库场景

- **GIVEN** 系统中只有 1 个词库
- **WHEN** 用户访问学习/测试入口
- **THEN** 系统 SHALL 不弹浮层（无选择意义）

#### Scenario: 通过浏览器关闭再打开

- **GIVEN** 用户已在某次会话中选过词库
- **WHEN** 用户关闭浏览器并重新打开
- **THEN** Flask session 失效，`list_picked` 重置
- **AND** 再次进入学习/测试时浮层 SHALL 重新弹出

### Requirement: 词库管理页新建词库入口

词库管理页 SHALL 在右上角提供"+ 新建词库"按钮，点击跳转到 PDF 导入流程。

#### Scenario: 用户点击新建词库

- **GIVEN** 用户位于 `/library` 页面
- **WHEN** 用户点击右上角"+ 新建词库"按钮
- **THEN** 浏览器 SHALL 跳转到 `/import` 页面
- **AND** 用户完成 PDF 导入并确认后，新词库 SHALL 自动设为当前词库
- **AND** `session['list_picked']` SHALL 被设为 True（防止后续学习/测试再次弹浮层）

### Requirement: 测试模式只从已掌握词中选取

测试模式（`test_start`，含文字测试和听力测试）SHALL 只从当前词库中「已掌握（`status='mastered'`）」的词里随机抽题，让测试专注于验证/巩固既有记忆。

#### Scenario: 只测已掌握词

- **GIVEN** 词库有 30 个词，其中 12 个 mastered / 18 个 unmastered
- **AND** 用户在测试 setup 页选择"测 10 题"
- **WHEN** `test_start` 执行
- **THEN** 系统 SHALL 只从 12 个 mastered 词中随机抽 10 个作为题目
- **AND** 10 个题目对应的 word_id 全部对应 `status='mastered'` 的词

#### Scenario: 已掌握词不足 4 个时拦截

- **GIVEN** 词库总 30 词，但 mastered 只有 3 个
- **WHEN** 用户访问 `test_setup`
- **THEN** setup 页 SHALL 显示引导文案「当前词库已掌握词不足 4 个，请先去学习一些单词再来测试」
- **AND** SHALL 提供"返回首页"或"去学习"按钮
- **AND** 不显示题数输入和"开始测试"按钮

#### Scenario: 干扰项来自全词库不变

- **GIVEN** 测试题目本身从 mastered 池选取
- **WHEN** `generate_quiz_questions` 生成题目的 4 选 1
- **THEN** 干扰项 SHALL 仍从全词库随机选取（保留既有行为）
- **AND** 不受 status 限制，保证选项池充足

### Requirement: get_list_stats 补充"未掌握且含同义词"字段

`get_list_stats(list_id)` 返回值 SHALL 新增字段 `unmastered_with_synonyms`（`status='unmastered' AND synonyms 非空` 的词数），供同义词学习 setup 页作为题数上限和文案数据源。

#### Scenario: 新字段计算

- **GIVEN** 词库有 100 个词
  - 其中 60 个 mastered
  - 40 个 unmastered
  - 60 个含 synonyms（其中 40 个 mastered、20 个 unmastered）
- **WHEN** 调用 `get_list_stats(list_id)`
- **THEN** 返回 dict SHALL 包含
  - `total: 100`
  - `mastered: 60`
  - `unmastered: 40`
  - `with_synonyms: 60`
  - `unmastered_with_synonyms: 20`（新增字段）

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

### Requirement: 学习功能始终可用

学习功能 SHALL 在所有情况下保持可用，包括词库全部单词已被掌握时。选词逻辑 SHALL 优先从未掌握词中选取，未掌握词数量不足时用全词库补齐。

#### Scenario: 全部掌握后学习按钮仍可用

- **GIVEN** 当前词库全部单词 `status='mastered'`（`unmastered==0`）
- **WHEN** 首页渲染
- **THEN** "开始学习"按钮 SHALL 保持可用（非 disabled）
- **AND** 不显示"词库已全部掌握，去测试模式巩固吧"文案

#### Scenario: 全部掌握后 setup 页正常

- **GIVEN** 当前词库全部单词 `status='mastered'`（`unmastered==0`）
- **AND** 用户点击首页"开始学习"
- **WHEN** `/learn/setup` 渲染
- **THEN** 输入框 `max` SHALL 设为 `stats.total`（全词库数量）
- **AND** `default_n` SHALL 为 `min(20, stats.total)`
- **AND** 不显示"剩余仅 0 个"之类的误导提示

#### Scenario: 选词优先未掌握再补齐

- **GIVEN** 词库有 30 个词，其中 5 个 unmastered / 25 个 mastered
- **AND** 用户在 setup 选择"学 20 个"
- **WHEN** `learn_start` 执行
- **THEN** 选词池 SHALL 包含全部 5 个 unmastered 词
- **AND** 再从 25 个 mastered 词中补齐 15 个
- **AND** 去重后刚好 20 个词

#### Scenario: 全部掌握后选词来自全词库

- **GIVEN** 词库有 30 个词，全部 `status='mastered'`（`unmastered==0`）
- **AND** 用户在 setup 选择"学 10 个"
- **WHEN** `learn_start` 执行
- **THEN** 选词池 SHALL 从全词库 30 个词中随机抽取 10 个
- **AND** 正常创建 `learn_session`
- **AND** 正常进入学习翻卡流程

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
