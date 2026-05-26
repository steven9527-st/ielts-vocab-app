# 任务清单

本 change 为已落地的桌面封装工程，任务清单作为补登记 + 完整流程留底。

---

## Phase 1: 运行环境路径分发（main 分支）

- [x] 1.1 新增 `paths.py`：`is_frozen()` / `user_data_dir()` / `resource_dir()` / `db_path()` / `tmp_parse_dir()`
- [x] 1.2 修改 `database.py`：`DB_PATH` 改用 `paths.db_path()`
- [x] 1.3 修改 `app.py`：`_TMP_DIR` 改用 `paths.tmp_parse_dir()`；Flask 在打包模式下指定 templates/static
- [x] 1.4 修改 `app.py` 启动逻辑：打包模式自动选可用端口 + 延迟开浏览器
- [x] 1.5 验证开发模式行为不变（DB_PATH 仍指向项目根目录）

## Phase 2: macOS 打包（packaging 分支）

- [x] 2.1 用 AI 生成黄色胖星星图标（`build_assets/icon_source.png`，1024x1024）
- [x] 2.2 转 `.icns` 多分辨率合一（16/32/64/128/256/512/1024 + @2x 套）
- [x] 2.3 写 `IELTSVocab.spec`：含 BUNDLE 段、bundle_identifier、Info.plist、collect_all pdfplumber/openpyxl
- [x] 2.4 写 `build_mac.sh`：PyInstaller 构建 + hdiutil 打 DMG（带 Applications 拖拽快捷方式）
- [x] 2.5 跑构建：产出 `dist/IELTSVocab.app`（115MB）+ `dist/IELTSVocab.dmg`（62MB）
- [x] 2.6 烟测：启动成功 / 端口 fallback 生效 / 浏览器自动打开 / 数据写入用户目录

## Phase 3: Windows 打包（packaging 分支）

- [x] 3.1 用 Pillow 把 PNG 转 `.ico`（16/24/32/48/64/128/256 多分辨率）
- [x] 3.2 写 `IELTSVocab_win.spec`：onedir 模式 + console=False + 图标
- [x] 3.3 写 `build_win.bat`：Python 检测 + 依赖安装 + PyInstaller + PowerShell 打 zip
- [x] 3.4 在 Windows 虚拟机上验证：脚本执行成功，产出 `dist\IELTSVocab\IELTSVocab.exe` + `dist\IELTSVocab-win.zip`
- [x] 3.5 双击 `.exe` 验证：浏览器自动打开 + 应用可用

## Phase 4: 启动脚本加固与编码修复

- [x] 4.1 修改 `start.bat`：加 Python 缺失检测 + 友好提示 + 替代方案
- [x] 4.2 修复 `.bat` 编码：纯 ASCII + CRLF + 无 BOM（踩坑两次后定稿）
- [x] 4.3 新增 `.gitattributes`：强制 `*.bat=crlf` / `*.sh=lf` / `*.py=lf`
- [x] 4.4 更新 `.gitignore`：排除 build/ dist/ .DS_Store *.iconset

## Phase 5: 文档与 Git 工作流

- [x] 5.1 写 `PACKAGING.md`：构建流程 / 用户数据位置 / 卸载 / 朋友使用说明
- [x] 5.2 Git 分支策略：`main`（精简）+ `packaging`（打包文件长期分支）
- [x] 5.3 打 tag `v1.0.0-mac`（首个 macOS 封装版本）
- [x] 5.4 推送 main + packaging + tag 到 GitHub

## Phase 6: 归档与 spec 同步

- [x] 6.1 `openspec validate desktop-app-packaging --strict` 通过
- [x] 6.2 同步 spec 到 `openspec/specs/desktop-packaging/`
- [x] 6.3 归档 change 到 `openspec/changes/archive/2026-05-26-desktop-app-packaging/`
- [x] 6.4 提交并推送
