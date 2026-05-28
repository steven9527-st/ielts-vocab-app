## 1. 心跳后端

- [x] 1.1 在 `app.py` 顶部添加全局变量 `_last_heartbeat = time.time()` 和锁 `_heartbeat_lock`
- [x] 1.2 新增 `@app.before_request` 钩子：在每个请求处理前更新 `_last_heartbeat = time.time()`（任何用户操作隐式续命）
- [x] 1.3 新增路由 `POST /api/heartbeat`：返回 `{"ok": True}`（before_request 已经更新时间戳，本路由仅作为浏览器持续心跳的目标）
- [x] 1.4 新增 `_start_heartbeat_watchdog()` 函数：spawn 一个 `daemon=True` 线程，每 5 秒检查 `time.time() - _last_heartbeat > 30` 则 `os._exit(0)`
- [x] 1.5 在 `__main__` 分支的 `is_frozen()` 块里调用 `_start_heartbeat_watchdog()`；开发模式不启用

## 2. 心跳前端

- [x] 2.1 修改 `templates/base.html`：在 `<body>` 末尾添加心跳脚本块，每 10 秒发送 `fetch('/api/heartbeat', { method: 'POST' })`，失败静默忽略
- [x] 2.2 心跳仅在打包模式启用——通过 Jinja `{% if is_frozen %}` 条件渲染，开发模式不发心跳
- [x] 2.3 在 `app.py` 的 `inject_nav_data` context_processor 中暴露 `is_frozen` 给模板使用

## 3. 发音 voice 检测

- [x] 3.1 修改 `static/tts.js`：新增 `_hasEnglishVoice` 状态 + `_detectEnglishVoice()` 函数（扫描 `getVoices()` 中是否有 `lang.toLowerCase().startsWith('en')` 的 voice）
- [x] 3.2 在脚本加载时同步调用一次 `_detectEnglishVoice()`；同时监听 `speechSynthesis.onvoiceschanged` 异步刷新
- [x] 3.3 修改 `speakWord` 函数：调用 `speak()` 前检查 `_hasEnglishVoice`；为 false 则调用 `_showTtsToast()` 而不是发声

## 4. 发音 Toast UI

- [x] 4.1 在 `templates/base.html` 添加隐藏的 Toast 容器（id=`ttsToast`），含标题 / 安装步骤 / 微软文档链接 / 关闭按钮
- [x] 4.2 在 `static/style.css` 添加 Toast 样式（fixed 定位、圆角卡片、渐显动画、移动端响应式）
- [x] 4.3 在 `static/tts.js` 实现 `_showTtsToast()`：检查 `sessionStorage.getItem('tts_warning_shown')`，已弹过则 return；否则显示 Toast 并设置 sessionStorage

## 5. 测试

- [x] 5.1 新增 `tests/test_heartbeat.py`：用 Flask test_client POST `/api/heartbeat` 验证返回 `{ok: True}`；验证 `before_request` 钩子刷新时间戳
- [x] 5.2 跑全部既有测试（18 个）确保零回归
- [x] 5.3 Mac 实测：构建后双击 .app → 关浏览器 → 用 `ps aux | grep IELTSVocab` 确认 30 秒后进程消失

## 6. 文档与构建

- [x] 6.1 更新 README.md「发音功能说明」段落：补充"Windows 中文系统需手动安装英文语音包"一句话
- [x] 6.2 在 main 分支提交所有改动
- [x] 6.3 切到 packaging 分支 merge main，重新跑 `bash build_mac.sh` 生成新 .app/.dmg
- [x] 6.4 push packaging 分支到远端，让 Win 虚拟机能 pull 新代码后重新构建

## 7. 验收

- [x] 7.1 Mac App 双击启动 → 关浏览器 → 30 秒后进程自动消失 ✓
- [ ] 7.2 Mac App 30 秒后再次双击 → 浏览器正常打开 ✓（不再"打不开"）
- [x] 7.3 Mac 上有英文语音 → 点 🔊 正常发声 ✓（不应误弹 Toast）
- [x] 7.4 `openspec validate fix-app-lifecycle --strict` 通过
- [x] 7.5 用户 Win 重新打包后实测：关浏览器 30 秒后任务管理器无 IELTSVocab.exe ✓
- [ ] 7.6 用户 Win 实测：点 🔊 弹出 Toast 含安装指引 ✓
