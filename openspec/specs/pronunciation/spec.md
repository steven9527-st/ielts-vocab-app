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

### Requirement: TTS 不可用时的降级行为

当浏览器或系统层面无法使用 TTS（不支持 Web Speech API、或系统未安装英文语音包）时，系统 SHALL 在用户主动尝试发音时给出明确反馈与解决方案，而不是静默失败。

#### Scenario: 浏览器完全不支持 Web Speech API

- **GIVEN** 用户使用的浏览器不支持 `window.speechSynthesis`（如旧版 IE）
- **WHEN** 卡片渲染
- **THEN** 所有 `.btn-tts` 按钮 SHALL 被禁用（`disabled`）
- **AND** 鼠标悬停 SHALL 显示 tooltip "当前浏览器不支持发音功能"

#### Scenario: 浏览器支持但系统无英文语音包

- **GIVEN** 浏览器支持 `speechSynthesis`
- **AND** `getVoices()` 返回的语音列表中没有任何 `lang` 以 `en` 开头的 voice
- **WHEN** 用户点击 🔊 按钮（首次）
- **THEN** 系统 SHALL 弹出 Toast 卡片
- **AND** Toast 内容 SHALL 包含：标题"⚠ 无法发音"、Windows 安装步骤、微软支持文档链接、「我知道了」关闭按钮

#### Scenario: Toast 同会话不重复弹出

- **GIVEN** 用户在同一会话内已经看过一次 Toast
- **AND** sessionStorage 已记录 `tts_warning_shown=1`
- **WHEN** 用户再次点击 🔊 按钮
- **THEN** Toast SHALL 不再弹出
- **AND** 按钮的点击 SHALL 静默无操作

#### Scenario: 重启浏览器后 Toast 重置

- **GIVEN** 用户关闭浏览器后重新打开
- **WHEN** sessionStorage 自然清空
- **AND** 用户再次点击 🔊 按钮（且仍无英文语音包）
- **THEN** Toast SHALL 重新弹出一次

#### Scenario: 异步加载的 voice 列表

- **GIVEN** 用户使用 Chrome / Firefox 等异步加载 voice 的浏览器
- **WHEN** 页面加载
- **THEN** tts.js SHALL 监听 `speechSynthesis.onvoiceschanged` 事件
- **AND** 在事件触发后重新检测英文语音是否存在
- **AND** 同时同步调用一次 `getVoices()` 作为兜底

#### Scenario: 已有英文语音的系统不受影响

- **GIVEN** 用户系统已有英文语音（如 macOS 默认 Samantha / Windows 已装英文语音包）
- **WHEN** 用户点击 🔊 按钮
- **THEN** 系统 SHALL 直接调用 `speechSynthesis.speak()` 朗读
- **AND** 不显示 Toast

### Requirement: 高品质音色优选

不同浏览器在同一系统上对默认 voice 的选择策略差异巨大（典型问题：Chrome on macOS 默认挑选 `Google US English`，音质明显差于 Safari 调用的系统 Siri 音色）。系统 SHALL 在朗读前主动按优先级挑选高品质本地神经网络音色，并将其绑定到 `SpeechSynthesisUtterance.voice`，使各浏览器的发音体验保持一致。

#### Scenario: macOS 上挑选 Siri 系列音色

- **GIVEN** 用户系统是 macOS 且 `getVoices()` 返回包含 `Samantha` / `Alex` / `Daniel` 等 Siri 音色
- **WHEN** 用户点击 🔊 按钮
- **THEN** `tts.js` SHALL 优先选用名单中靠前的音色（默认 `Samantha`）
- **AND** 将其赋值给 `utterance.voice`
- **AND** Chrome 与 Safari 应朗读出一致的高品质音色

#### Scenario: Windows 上挑选神经网络音色

- **GIVEN** 用户系统是 Windows 且已安装含 `Natural` 或 `Neural` 关键字的微软神经网络语音
- **WHEN** macOS 高品质音色名单未命中
- **THEN** `tts.js` SHALL 退而选用第一个 name 含 `Natural` / `Neural` 的英文 voice

#### Scenario: 仅有云端低质音色时回退

- **GIVEN** 系统只能找到 `Google US English` 等 `localService=false` 的远端 voice
- **WHEN** 优选名单与 Neural 关键字均未命中
- **THEN** `tts.js` SHALL 优先选择任意 `localService=true` 的英文 voice
- **AND** 若所有英文 voice 均为远端，则兜底使用第一个英文 voice 而非中断发音

#### Scenario: voice 列表异步加载后重新挑选

- **GIVEN** Chrome / Edge 等浏览器在页面加载初期 `getVoices()` 返回为空
- **WHEN** `speechSynthesis.onvoiceschanged` 触发
- **THEN** `tts.js` SHALL 重新调用挑选逻辑并刷新缓存
- **AND** 后续点击 🔊 SHALL 使用刷新后的高品质 voice

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
