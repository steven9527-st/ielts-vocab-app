## Why

Windows 新版用户实测发现两个独立但都很影响体验的问题：

1. **进程不退出**：用户关闭浏览器窗口后 Flask 进程仍在跑。Windows 上每次双击 .exe 都会启动新进程（旧的还活着），任务管理器里堆积多个 IELTSVocab.exe，必须手动 Kill；macOS 上更糟——第二次双击 .app 会被 Launch Services 当成"激活已有实例"，但已有实例的浏览器窗口已经关了，结果浏览器打不开，看起来像启动失败。
2. **发音功能在中文 Windows 系统上静默失败**：`speechSynthesis.speak()` 在系统未安装英文语音包时不报错也不发声，用户以为按钮坏了。

两个问题都源于"桌面打包后 Web 应用的生命周期/能力检测"层面的疏漏，应一起修。

## What Changes

- **新增进程心跳自杀机制**（仅 `is_frozen()` 时启用）：
  - 后端：新增 `POST /api/heartbeat` 路由 + 后台守护线程；30 秒未收到心跳 → `os._exit(0)` 自杀
  - 前端：`base.html` 加 `setInterval` 每 10 秒发送心跳；浏览器关闭后自然停止
- **发音功能加入英文语音包检测 + 友好引导**：
  - `tts.js` 启动时扫描 `speechSynthesis.getVoices()`，标记是否存在 `lang.startsWith('en')` 的 voice
  - 用户点击 🔊 时，若无英文语音 → 弹出 Toast 卡片，告知原因 + 提供 Windows 语音包安装步骤 + 微软支持文档链接
  - 同会话内仅弹一次（`sessionStorage` 记忆），避免烦扰
- **不变更**数据库 Schema、UI 主流程、PDF/Excel 导入、学习/测试模式

## Capabilities

### New Capabilities
（无）

### Modified Capabilities
- `desktop-packaging`：新增"打包模式心跳自杀"要求，规范化 Mac/Win 桌面 app 的关闭行为
- `pronunciation`：发音失败时的用户引导从"按钮静默禁用"升级为"按下后弹出 Toast 解释原因 + 安装指引"

## Impact

**代码：**
- `app.py`：新增 `_last_heartbeat` 全局状态、`/api/heartbeat` 路由、`_start_heartbeat_watchdog()` 后台线程；仅在 `is_frozen()` 时启用
- `static/tts.js`：新增 voice 检测、Toast 渲染、sessionStorage 去重逻辑
- `templates/base.html`：新增心跳 setInterval（仅 PROD 模式）+ Toast 容器节点

**测试：**
- `tests/test_heartbeat.py`：新增——验证 `/api/heartbeat` 路由更新时间戳；用 monkey patch 测试守护线程触发自杀
- 现有 e2e / 单元测试不受影响

**依赖 / 打包：** 无新增依赖，重新打包即可

**用户数据：** 无变更

**显式不做（Out of Scope）：**
- 不引入系统托盘图标（pystray 等）
- 不替换 Web Speech API 为后端 TTS（避免引入额外依赖与网络要求）
- 不解决"Mac 双击 .app 激活已有实例"的 Launch Services 行为（心跳自杀已经间接解决——下次双击时旧实例已死）
