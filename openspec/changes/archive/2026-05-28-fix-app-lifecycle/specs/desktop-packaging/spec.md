## ADDED Requirements

### Requirement: 打包模式心跳自杀

桌面打包后的 app（`is_frozen()` 为 True）SHALL 通过浏览器心跳机制感知用户已离开并自动退出进程，避免进程残留导致下次启动冲突。

#### Scenario: 用户关闭浏览器后进程自动退出

- **GIVEN** 用户双击 .app / .exe 启动后台 Flask 进程
- **AND** 浏览器自动打开并连接到该进程
- **WHEN** 用户关闭浏览器窗口
- **AND** 经过约 30 秒
- **THEN** 后台 Flask 进程 SHALL 自动调用 `os._exit(0)` 退出
- **AND** 任务管理器 / `ps` 命令 SHALL 不再显示该进程

#### Scenario: 用户保持浏览器打开

- **GIVEN** 后台 Flask 进程已启动
- **AND** 浏览器窗口处于打开状态（任意词库相关页面）
- **WHEN** 时间持续推进
- **THEN** 浏览器 SHALL 每 10 秒发送一次 `POST /api/heartbeat`
- **AND** 后台进程 SHALL 持续保持运行

#### Scenario: 用户主动操作刷新心跳

- **GIVEN** 后台 Flask 进程已启动
- **WHEN** 用户在浏览器中执行任意操作（导入、学习、测试等任何 HTTP 请求）
- **THEN** 该请求 SHALL 隐式更新心跳时间戳
- **AND** 进程 SHALL 不会因为期间没有显式 `/api/heartbeat` 调用而误杀

#### Scenario: 网络抖动期间不误杀

- **GIVEN** 浏览器与本地服务器之间发生 5-15 秒的短暂网络抖动
- **WHEN** 单次心跳请求失败
- **THEN** 进程 SHALL 不立即退出
- **AND** 下一次心跳成功时 SHALL 恢复正常

#### Scenario: 开发模式不启用心跳

- **GIVEN** 开发者用 `python3 app.py` 启动（`is_frozen()` 为 False）
- **WHEN** 检查进程行为
- **THEN** 心跳守护线程 SHALL 不被启动
- **AND** 进程 SHALL 持续运行直到开发者手动 Ctrl+C

#### Scenario: 多次启动不导致进程堆积

- **GIVEN** 用户已经启动过一次 app（旧进程占据 5000 端口）
- **AND** 关闭浏览器后未到 30 秒
- **WHEN** 用户再次双击启动 app
- **THEN** 新进程 SHALL 自动 fallback 到下一个可用端口（5001/5002...）
- **AND** 30 秒后旧进程 SHALL 自动退出，5000 端口被释放
- **AND** 用户的下次启动 SHALL 能回到 5000 端口
