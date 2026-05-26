# Spec: pronunciation


## ADDED Requirements

### Requirement: 单词卡片发音按钮

学习模式的单词卡片（`flashcard.html`）SHALL 在音标行右侧提供 🔊 发音按钮，使用浏览器原生 Web Speech API 朗读单词的英文形式。

#### Scenario: 卡片有音标

- **GIVEN** 当前学习的单词具有 `phonetic` 字段
- **WHEN** 卡片渲染
- **THEN** 音标文本右侧 SHALL 显示 🔊 按钮
- **AND** 用户点击按钮，浏览器 SHALL 调用 `window.speechSynthesis.speak()` 朗读 `word.english`
- **AND** 朗读语言 SHALL 设为 `en-US`，语速 SHALL 设为 0.9

#### Scenario: 卡片无音标

- **GIVEN** 当前学习的单词 `phonetic` 字段为空
- **WHEN** 卡片渲染
- **THEN** 🔊 按钮 SHALL 显示在英文单词右侧（无音标行可挂靠）

#### Scenario: 卡片不自动朗读

- **GIVEN** 用户进入学习卡片页面
- **WHEN** 卡片初次渲染
- **THEN** 系统 SHALL 不自动朗读
- **AND** 仅在用户主动点击 🔊 按钮时朗读

#### Scenario: 重复点击

- **GIVEN** 用户已点击过一次 🔊 按钮
- **WHEN** 用户在朗读完成前再次点击
- **THEN** 系统 SHALL 调用 `speechSynthesis.cancel()` 终止当前朗读
- **AND** 立即开始新的朗读

### Requirement: TTS 浏览器兼容性降级

当用户浏览器不支持 Web Speech API 时，🔊 按钮 SHALL 以禁用态显示并提供文字提示。

#### Scenario: 不支持的浏览器

- **GIVEN** 浏览器 `window.speechSynthesis` 不可用
- **WHEN** 页面渲染含 🔊 按钮的元素
- **THEN** 按钮 SHALL 渲染为 disabled 状态
- **AND** 按钮 SHALL 显示 `title="当前浏览器不支持发音功能"` tooltip
- **AND** 点击按钮 SHALL 无任何行为

#### Scenario: 支持的浏览器

- **GIVEN** 浏览器支持 `window.speechSynthesis`
- **WHEN** 页面渲染
- **THEN** 按钮 SHALL 处于正常可点击状态

### Requirement: 全局 TTS 工具脚本

系统 SHALL 提供 `static/tts.js` 全局脚本，导出 `speakWord(text)` 与 `ttsAvailable()` 两个函数，供 flashcard、quiz 等多个页面复用。

#### Scenario: 脚本加载

- **GIVEN** 任意继承 `base.html` 的页面
- **WHEN** 页面加载完成
- **THEN** `static/tts.js` SHALL 被自动引入
- **AND** 全局作用域 SHALL 暴露 `window.speakWord` 和 `window.ttsAvailable`

#### Scenario: API 调用

- **GIVEN** `tts.js` 已加载
- **WHEN** 调用 `speakWord("apple")`
- **THEN** 浏览器 SHALL 朗读 "apple"，语言 en-US，语速 0.9
