# Spec: audio-test


## ADDED Requirements

### Requirement: 测试类型选择

测试设置页（`test_setup.html`）SHALL 提供"测试类型"单选组，允许用户选择文字测试或听力测试。

#### Scenario: 默认选项

- **GIVEN** 用户首次进入 `/test/setup`
- **WHEN** 页面渲染
- **THEN** "文字测试" SHALL 默认选中
- **AND** 表单 `name=test_type` 默认值 SHALL 为 `"text"`

#### Scenario: 用户选择听力测试

- **GIVEN** 用户位于 `/test/setup`
- **WHEN** 用户选中"听力测试"并点击"开始测试"
- **THEN** 表单 SHALL 提交 `test_type=audio` 到 `/test/start`
- **AND** 后端 SHALL 在 quiz_data 中存入 `question_type="audio"`
- **AND** 后端 SHALL 在 session 中存入 `quiz_test_type="audio"`

### Requirement: 听力测试题目渲染

当 quiz_data 中 `question_type=audio` 时，题目页 SHALL 用 🔊 播放按钮替代英文文本展示，并在进入题目时自动朗读一次。

#### Scenario: 进入听力测试题目

- **GIVEN** 用户处于听力测试模式（`quiz_test_type="audio"`）
- **WHEN** 用户进入 `/quiz/question` 渲染第 N 题
- **THEN** 题目区域 SHALL 显示一个大型 🔊 播放按钮（不显示英文单词文本）
- **AND** 页面加载完成后 SHALL 自动调用 `speakWord(question.english)` 朗读一次
- **AND** 用户 SHALL 能多次点击按钮重复朗读
- **AND** 4 个中文选项 SHALL 与文字测试相同方式渲染

#### Scenario: 文字测试模式不受影响

- **GIVEN** 用户处于文字测试模式（`quiz_test_type="text"` 或未设置）
- **WHEN** 用户进入题目页
- **THEN** 题目 SHALL 渲染英文单词大字（保留现状）
- **AND** SHALL 不调用 TTS

#### Scenario: 学习模式不受影响

- **GIVEN** 用户处于学习收尾测验（`quiz_mode="learn"`）
- **WHEN** 用户进入题目页
- **THEN** 题目 SHALL 始终按文字模式渲染（学习收尾测验不分类型）

### Requirement: study_log mode 字段扩展

`study_log.mode` 字段值 SHALL 从原 `"learn" | "test"` 扩展为 `"learn" | "test_text" | "test_audio"`。

#### Scenario: 文字测试完成

- **GIVEN** 用户完成一次文字测试（`quiz_test_type="text"`）
- **WHEN** `quiz_submit` 写入 study_log
- **THEN** 该条记录 `mode` 字段 SHALL 为 `"test_text"`

#### Scenario: 听力测试完成

- **GIVEN** 用户完成一次听力测试（`quiz_test_type="audio"`）
- **WHEN** `quiz_submit` 写入 study_log
- **THEN** 该条记录 `mode` 字段 SHALL 为 `"test_audio"`

#### Scenario: 历史 'test' 记录兼容

- **GIVEN** study_log 中存在历史 `mode="test"` 的记录
- **WHEN** 任何统计/展示查询读取
- **THEN** 系统 SHALL 将其视为 `test_text` 处理（即统计文字测试时 `WHERE mode IN ('test', 'test_text')`）

#### Scenario: streak 计算不受影响

- **GIVEN** study_log 中包含 learn / test_text / test_audio 三类记录
- **WHEN** `calc_streak` 计算连续打卡天数
- **THEN** SHALL 仅统计 `mode="learn"` 且 `accuracy=1.0` 的记录（保持现有逻辑不变）

### Requirement: 测试结果页区分类型

`test_result.html` SHALL 在标题区显示当前测试类型的徽标（"文字测试" / "听力测试"）。

#### Scenario: 文字测试结果

- **GIVEN** 用户刚完成文字测试
- **WHEN** 渲染 `test_result.html`
- **THEN** 标题区 SHALL 显示"文字测试"徽标

#### Scenario: 听力测试结果

- **GIVEN** 用户刚完成听力测试
- **WHEN** 渲染 `test_result.html`
- **THEN** 标题区 SHALL 显示"听力测试"徽标
