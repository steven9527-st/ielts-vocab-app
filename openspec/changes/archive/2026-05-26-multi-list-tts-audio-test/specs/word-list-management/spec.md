# word-list-management Specification

## ADDED Requirements

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
