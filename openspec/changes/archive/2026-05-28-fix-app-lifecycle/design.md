## Context

桌面打包的 Flask Web App 共同痛点：服务器进程与"浏览器窗口"两个生命周期解耦。用户关浏览器 ≠ 用户想退出 app，但 Flask 没有任何机制感知"用户已经离开"。

加上两个平台的差异让现象不同：
- **Windows**：每次双击 .exe 启动新进程，旧进程仍占 5000 → 新进程 fallback 到 5001/5002... 多进程并存，SQLite 多写者会偶发卡死
- **macOS**：Launch Services 默认行为是"双击同 .app 激活已有实例而不启动新进程"。但已有实例的浏览器窗口被关闭后没办法重新唤起 → 用户感觉"App 启动失败"

发音功能的问题更隐蔽：`speechSynthesis.speak()` 是 Web Standard，但 voice 是系统层资源——中文 Windows 默认不装英文 TTS 音色，调用时浏览器静默 NoOp，没有任何报错或反馈。

两个问题分开看都是小修，合并看是「桌面打包后 web app 必备的生命周期 + 能力反馈」基础设施。

## Goals / Non-Goals

**Goals:**
- 用户关浏览器 30 秒后，Flask 进程自动退出（Mac/Win 行为一致）
- 用户在无英文 TTS 系统上点 🔊 时，能立刻看到原因 + 解决方案，而不是怀疑应用坏了
- 不引入新的依赖、不增加打包体积
- 开发模式（`python3 app.py`）不受心跳影响（本地开发必须能 Ctrl+C 控制）

**Non-Goals:**
- 不实现"系统托盘 + 右键退出"（pystray 依赖大且 Windows/Mac 体验不一致）
- 不实现"启动时检测端口冲突并 kill 旧进程"（有权限风险，让心跳自然清理更安全）
- 不切换为本地后端 TTS（pyttsx3 依赖 SAPI5 仍受系统音色限制；gTTS / edge-tts 联网破坏隐私卖点）
- 不做"用户主动退出"的按钮（关浏览器 + 心跳超时即可，无需多此一举）

## Decisions

### D1：心跳间隔 10 秒、宽容 30 秒

**决策**：前端 `setInterval(heartbeat, 10000)`；后端 `if now - last_heartbeat > 30: os._exit(0)`。

**取舍空间**：

| 心跳间隔 | 宽容时间 | 优点 | 缺点 |
|---------|---------|------|------|
| 5s | 15s | 关闭后死得快 | 网络抖动易误杀 |
| **10s** | **30s** | **平衡（推荐）** | 关浏览器后等 30 秒才能立即重新启动到 5000 |
| 30s | 90s | 极宽容 | 用户立即重启会一直 fallback 端口 |

**为什么 30 秒不是 60 秒**：用户关浏览器→重新启动 app 的常见间隔是几秒到一分钟。30 秒是个甜蜜点：足以扛住网络抖动，又不至于让用户立即重启时一直滚到新端口。

### D2：心跳仅在打包模式启用

**决策**：`if is_frozen(): _start_heartbeat_watchdog()`，开发模式不启动守护线程。

**理由**：
- 开发模式下 Flask 用 `app.run(debug=False)` 启动，正常通过 Ctrl+C 退出
- 守护线程跑在后台不影响 Ctrl+C，但会让单元测试 / 集成测试每次跑完 30 秒后被 `os._exit(0)`，污染 pytest/unittest 报告
- 仅打包模式启用即可解决用户问题，不做不必要的扩张

### D3：守护线程用 `os._exit(0)` 而非 `sys.exit()`

**决策**：自杀直接调 `os._exit(0)`，不走 Python 解释器的清理流程。

**理由**：
- `sys.exit()` 抛 `SystemExit` 异常，被 Flask 主线程的 server loop 捕获后无效（守护线程的异常无法影响主线程）
- `os._exit(0)` 直接调 POSIX `_exit` 系统调用，立即终止进程
- 风险：跳过 atexit handlers / 不刷 stdio 缓冲——但本应用没有需要清理的资源（SQLite 连接每个请求结束就关了）

### D4：前端心跳容错——失败不退避

**决策**：fetch 心跳如失败（如服务器已经被杀），不做指数退避或停止；继续按 10 秒间隔尝试。

**理由**：
- 服务器已死的情况下浏览器其实也会很快遇到其他请求失败，用户自己会关
- 简单的代码胜过精巧的容错——心跳是最低优先级的"keep-alive 信号"，任何失败都不需要特殊处理

### D5：Voice 检测的异步性

**决策**：`speechSynthesis.getVoices()` 在大多数浏览器是异步加载的。tts.js 启动时：

```javascript
function detectEnglishVoice() {
  var voices = speechSynthesis.getVoices();
  _hasEnglishVoice = voices.some(v => v.lang.startsWith('en'));
}

speechSynthesis.onvoiceschanged = detectEnglishVoice;
detectEnglishVoice();  // 同步调一次（Chrome 偶尔同步返回）
```

**为什么双重保险**：Chrome 偶尔同步返回 voices，Firefox/Edge 必须等 `onvoiceschanged` 事件。两者都监听确保能拿到最新结果。

### D6：Toast 仅同会话弹一次

**决策**：用 `sessionStorage.setItem('tts_warning_shown', '1')` 记忆。

**为什么不是 localStorage**：用户跨会话状态可能变化（装了语音包后），sessionStorage 自然在重启浏览器时清空，让用户能再次得到反馈。

### D7：Toast 用纯 HTML+CSS 实现，不引依赖

**决策**：在 base.html 添加一个隐藏 Toast 容器，tts.js 控制显示/隐藏。不引入 toast 库。

**理由**：
- 整个 app 没有 UI 框架，引入 toast 库不协调
- 纯 CSS 渐显 + position fixed 已经够用
- 内容固定（语音包安装指引）不需要复杂的 toast queue 系统

## Risks / Trade-offs

**[R1] 30 秒宽容期内重启 app**
- 用户关浏览器立即重启 → 新进程 fallback 到 5001
- 30 秒后旧进程死，但新进程仍在 5001
- → Mitigation：可接受。下次启动会回到 5000。极端用户可手动等 30 秒再重启。

**[R2] 守护线程在 `os._exit` 前的"最后请求"会被中断**
- 用户在 30 秒边缘提交了一个 confirm 请求，但服务器在处理中被杀
- → Mitigation：实际上心跳一旦在飞，证明用户在交互；交互行为本身就会刷新 last_heartbeat（虽然这次只针对 /api/heartbeat 单一路由，可以扩展为所有路由）

**[R2 改进版]**：让所有路由都隐式更新 last_heartbeat（用 `@app.before_request`），而不是只有 `/api/heartbeat`。这样用户主动操作时也算"活着"，更加鲁棒。**采纳为最终方案。**

**[R3] Toast 弹出时如果用户在播放某个学习卡片**
- 用户点了 🔊 → 没声 → 突然弹 Toast → 学习被打断
- → Mitigation：可以接受，因为这是首次发现"没声"的瞬间，告知用户是必要的。后续同会话不再弹。

**[R4] 误把"无英文语音"判为"英文已具备"**
- `voice.lang` 在某些浏览器返回类似 `en` / `en-US` / `en_US` / `en-001` 各种格式
- → Mitigation：用 `lang.toLowerCase().startsWith('en')` 宽松匹配。已知 Chrome/Edge/Firefox 都返回 `en-XX` 形态。

**[R5] 守护线程被 PyInstaller bundle 影响**
- PyInstaller 偶尔对线程有 quirk
- → Mitigation：用 `daemon=True` thread + `os._exit` 是最简单组合，已在多个 PyInstaller 项目验证可行；构建后实测一遍

## Migration Plan

1. 实施 app.py / tts.js / base.html 三处改动
2. 单元测试：心跳路由 + voice 检测逻辑
3. 跑全部既有测试确保零回归
4. 构建 Mac App 实测：
   - 双击启动 → 关浏览器 → 30 秒后 `ps` 看进程是否消失 ✓
   - 30 秒后再双击 → 浏览器正常打开 ✓
5. Win 由用户在虚拟机重新构建测试
6. 归档 change
