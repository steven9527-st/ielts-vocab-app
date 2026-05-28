## MODIFIED Requirements

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
- **AND** Toast 内容 SHALL 包含：
  - 标题"⚠ 无法发音"
  - 简要原因（"当前系统未安装英文语音包"）
  - Windows 安装步骤（设置 → 时间和语言 → 语言和区域 → 添加首选语言 → English (United States) → 选项 → 下载语音）
  - 微软支持文档链接（在外部浏览器打开）
  - 「我知道了」关闭按钮

#### Scenario: Toast 同会话不重复弹出

- **GIVEN** 用户在同一会话内已经看过一次 Toast
- **AND** sessionStorage 已记录 `tts_warning_shown=1`
- **WHEN** 用户再次点击 🔊 按钮
- **THEN** Toast SHALL 不再弹出
- **AND** 按钮的点击 SHALL 静默无操作（不报错）

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
- **AND** 同时同步调用一次 `getVoices()` 作为兜底（覆盖偶尔同步返回的浏览器）

#### Scenario: 已有英文语音的系统不受影响

- **GIVEN** 用户系统已有英文语音（如 macOS 默认 Samantha / Windows 已装英文语音包）
- **WHEN** 用户点击 🔊 按钮
- **THEN** 系统 SHALL 直接调用 `speechSynthesis.speak()` 朗读
- **AND** 不显示 Toast
