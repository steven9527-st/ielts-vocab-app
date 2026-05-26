# 桌面 App 封装（macOS .app + Windows .exe）

## Why

应用此前以 Flask 源码形式存在，用户需要：装 Python、装依赖、跑 `start.command/.bat`、自己开浏览器。普通用户（特别是 Windows 上的朋友）这条链路走不通——`start.bat` 闪退率 100%，因为没装 Python。

目标用户从"自己用"扩展到"朋友也用"后，必须让 app 变成"双击即用"的桌面应用。

## What Changes

把单一 Flask 应用打包为两个平台的可分发桌面 app：

### macOS .app
- 用 PyInstaller 把 Flask + Python 解释器 + 所有依赖打进 `.app` Bundle
- 黄色胖星星 kawaii 图标（`build_assets/icon.icns`）
- 自动选可用端口（5000 被占用时 fallback 到 5001/5002/5050 等）
- 自动开默认浏览器到 `http://127.0.0.1:<port>`
- 用 `hdiutil` 打 `.dmg`，含 Applications 拖拽快捷方式

### Windows .exe
- 同样 PyInstaller，onedir 模式（启动更快、运行更稳）
- 同图标转 `.ico`（多分辨率合一）
- `console=False` 隐藏命令行窗口
- PowerShell `Compress-Archive` 打分发 zip

### 通用运行时改造
- 新增 `paths.py`：根据 `sys.frozen` 自动选择数据/资源路径
  - 开发模式：项目根目录（不影响 dev 体验）
  - 打包模式 macOS：`~/Library/Application Support/IELTSVocab/`
  - 打包模式 Windows：`%APPDATA%\IELTSVocab\`
- Flask 在打包模式下指定 `template_folder` / `static_folder` 指向 PyInstaller 解压目录 `sys._MEIPASS`
- `app.py` 启动逻辑：打包模式自动开浏览器 + 关闭 reloader

### 启动脚本加固
- `start.bat` 加 Python 缺失检测 + 友好错误提示
- `.bat` 文件统一改为纯 ASCII + CRLF + 无 BOM（避免 cmd 解析失败导致闪退）
- 新增 `.gitattributes` 强制 EOL 策略（防跨平台 git 克隆时换行符被自动转换）

### 分发支持
- `PACKAGING.md`：完整构建/分发/卸载说明
- 一键构建脚本：`build_mac.sh` / `build_win.bat`
- Git 分支策略：`main` 保持代码精简，`packaging` 长期分支维护打包文件
- 版本 tag：`v1.0.0-mac`

## Impact

- **Affected specs**：新增 1 个 capability spec
  - `desktop-packaging`：桌面 app 封装与分发能力
- **Affected code**：
  - `paths.py`（新增）：运行环境路径分发
  - `database.py`：`DB_PATH` 改用 `paths.db_path()`
  - `app.py`：`_TMP_DIR` 改用 `paths.tmp_parse_dir()`；Flask 适配打包模式；启动逻辑增强
  - `start.bat`：加固 + 编码修复
  - `.gitattributes`（新增）：EOL 策略
  - `requirements.txt`：保持不变（PyInstaller 仅开发时需要，不进运行依赖）
- **Affected files (仅 packaging 分支)**：
  - `IELTSVocab.spec`、`IELTSVocab_win.spec`、`build_mac.sh`、`build_win.bat`
  - `build_assets/icon.icns`、`build_assets/icon.ico`、`build_assets/icon_source.png`
  - `PACKAGING.md`
- **Breaking changes**：无（开发模式行为完全不变）
- **Non-goals**：
  - 不做 Apple Developer 代码签名（首次启动用户需手动允许）
  - 不做 Windows 代码签名（同上，Defender 会有"未识别应用"提示）
  - 不做安装包（NSIS / Inno Setup），Win 直接用 zip 解压
  - 不做自动更新机制
  - 不做 GitHub Actions 自动构建（手动跑 build 脚本足够）
