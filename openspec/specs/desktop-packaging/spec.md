# Spec: desktop-packaging


## ADDED Requirements

### Requirement: 运行环境路径自适应

应用 SHALL 通过 `paths.py` 统一管理数据与资源路径，根据是否在 PyInstaller 打包环境中自动切换位置。

#### Scenario: 开发模式

- **GIVEN** 应用通过 `python app.py` 直接启动（`sys.frozen` 为 False）
- **WHEN** 代码读取 `paths.db_path()` 与 `paths.tmp_parse_dir()`
- **THEN** SHALL 返回项目根目录下的 `vocab.db` 与 `.tmp_parse/`
- **AND** 行为与未引入 paths.py 之前完全一致

#### Scenario: macOS 打包环境

- **GIVEN** 应用通过 `dist/IELTSVocab.app` 启动（`sys.frozen` 为 True，`sys.platform == 'darwin'`）
- **WHEN** 代码读取数据路径
- **THEN** SHALL 返回 `~/Library/Application Support/IELTSVocab/vocab.db`
- **AND** 临时目录 SHALL 为 `~/Library/Application Support/IELTSVocab/.tmp_parse/`

#### Scenario: Windows 打包环境

- **GIVEN** 应用通过 `dist\IELTSVocab\IELTSVocab.exe` 启动（`sys.platform == 'win32'`）
- **WHEN** 代码读取数据路径
- **THEN** SHALL 返回 `%APPDATA%\IELTSVocab\vocab.db`

#### Scenario: 资源目录定位

- **GIVEN** 应用在打包环境中运行
- **WHEN** Flask 需要 templates / static 目录
- **THEN** `paths.resource_dir()` SHALL 返回 `sys._MEIPASS`（PyInstaller 解压临时目录）
- **AND** Flask 通过 `Flask(template_folder=..., static_folder=...)` 显式指定

### Requirement: 自动选择可用端口

打包环境下，应用启动 SHALL 优先使用 5000 端口，被占用时按 fallback 列表尝试。

#### Scenario: 默认端口可用

- **GIVEN** 5000 端口未被占用
- **WHEN** 打包版应用启动
- **THEN** SHALL 在 5000 端口启动 Flask

#### Scenario: 默认端口被占用

- **GIVEN** 5000 端口被其他程序占用（如 macOS AirPlay Receiver）
- **WHEN** 打包版应用启动
- **THEN** SHALL 按顺序尝试 5001, 5002, 5050, 5500, 8000, 8080
- **AND** 使用第一个可用端口

#### Scenario: 所有 fallback 都被占用

- **GIVEN** 5000 + 所有 fallback 端口都被占用
- **WHEN** 应用启动
- **THEN** SHALL 由系统随机分配一个可用端口

### Requirement: 自动打开浏览器

打包环境下，应用启动 SHALL 在 Flask 就绪后自动调起默认浏览器。

#### Scenario: 正常启动

- **GIVEN** 打包版应用刚启动
- **WHEN** Flask 服务 bind 端口
- **THEN** 系统 SHALL 在 1.5 秒后调用 `webbrowser.open(url)` 打开默认浏览器
- **AND** 浏览器 SHALL 跳转到 `http://127.0.0.1:<port>`

#### Scenario: 浏览器调起失败

- **GIVEN** 用户系统没有可识别的默认浏览器
- **WHEN** `webbrowser.open` 抛异常
- **THEN** 系统 SHALL 静默捕获异常（不让 Flask 主进程崩溃）
- **AND** 用户可手动复制控制台输出的 URL 到任意浏览器

#### Scenario: 开发模式不自动开浏览器

- **GIVEN** 应用通过 `python app.py` 启动
- **WHEN** 服务启动
- **THEN** SHALL 不自动开浏览器（开发时不打扰）

### Requirement: macOS .app 打包

`build_mac.sh` SHALL 通过 PyInstaller 构建可分发的 macOS Bundle 与 DMG。

#### Scenario: 一键构建

- **GIVEN** 开发者在 macOS 上跑 `bash build_mac.sh`
- **WHEN** 脚本执行
- **THEN** SHALL 依次完成：依赖检查 → 清理旧产物 → PyInstaller 构建 → hdiutil 打 DMG
- **AND** 产物 SHALL 输出到 `dist/IELTSVocab.app` 与 `dist/IELTSVocab.dmg`
- **AND** `.app` 内的 Info.plist SHALL 包含 bundle identifier、版本号、显示名

#### Scenario: DMG 含安装快捷方式

- **GIVEN** 用户双击挂载 `IELTSVocab.dmg`
- **WHEN** Finder 打开挂载卷
- **THEN** 卷内 SHALL 显示 `IELTSVocab` 图标与 `Applications` 文件夹快捷方式
- **AND** 用户拖前者到后者即完成安装

#### Scenario: 应用图标

- **GIVEN** 应用在 Finder / Dock 中显示
- **WHEN** 系统渲染图标
- **THEN** SHALL 显示 `build_assets/icon.icns` 中的黄色胖星星图案
- **AND** 图标 SHALL 包含 16x16 到 1024x1024 多分辨率

### Requirement: Windows .exe 打包

`build_win.bat` SHALL 在 Windows 环境下通过 PyInstaller 构建可分发的 EXE 与 ZIP。

#### Scenario: 一键构建

- **GIVEN** 开发者在 Windows 上双击 `build_win.bat`
- **WHEN** 脚本执行
- **THEN** SHALL 依次完成：Python 检测 → 依赖安装 → PyInstaller 构建 → PowerShell 打 zip
- **AND** 产物 SHALL 输出到 `dist\IELTSVocab\IELTSVocab.exe` 与 `dist\IELTSVocab-win.zip`

#### Scenario: 隐藏控制台

- **GIVEN** 用户双击 `IELTSVocab.exe`
- **WHEN** 应用启动
- **THEN** SHALL 不显示黑色命令行窗口
- **AND** 仅浏览器窗口可见

#### Scenario: 应用图标

- **GIVEN** `.exe` 文件在文件管理器中显示
- **WHEN** Windows 渲染图标
- **THEN** SHALL 显示 `build_assets/icon.ico` 中的黄色胖星星
- **AND** 图标 SHALL 包含 16/24/32/48/64/128/256 多分辨率

### Requirement: 启动脚本编码与兼容性

所有 `.bat` 文件 SHALL 使用纯 ASCII + CRLF + 无 BOM，确保 Windows cmd 正常解析。

#### Scenario: .bat 在 Windows cmd 中正常执行

- **GIVEN** 用户在 Windows 上双击 `start.bat` 或 `build_win.bat`
- **WHEN** cmd 解析脚本
- **THEN** `@echo off` SHALL 生效，命令本身不被回显
- **AND** 所有 echo 提示信息 SHALL 正常显示（无乱码）

#### Scenario: git 跨平台克隆保持 EOL

- **GIVEN** 仓库根目录有 `.gitattributes`
- **WHEN** 用户在 Windows 上 `git clone`
- **THEN** `.bat` 文件 SHALL 自动转为 CRLF（即使源仓库存的是 LF）
- **AND** `.sh` 文件 SHALL 保持 LF

#### Scenario: 未装 Python 的友好提示

- **GIVEN** 用户在没装 Python 的 Windows 上双击 `start.bat`
- **WHEN** 脚本检测到 `where python` 失败
- **THEN** SHALL 显示英文提示：缺失 Python、下载链接、安装时勾选 "Add to PATH"
- **AND** SHALL 提示替代方案：使用打包好的 IELTSVocab.exe（无需 Python）
- **AND** SHALL `pause` 等待用户确认，不闪退

### Requirement: 分发产物排除

构建中间产物与最终产物 SHALL 不进入 git 仓库。

#### Scenario: build 与 dist 不入仓

- **GIVEN** 开发者跑 `build_mac.sh` / `build_win.bat`
- **WHEN** 检查 `git status`
- **THEN** `build/` 与 `dist/` SHALL 被 `.gitignore` 忽略
- **AND** `.DS_Store`、`*.spec.bak`、`*.iconset/` SHALL 同样被忽略
