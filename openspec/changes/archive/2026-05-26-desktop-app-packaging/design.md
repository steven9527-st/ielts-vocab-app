# 设计文档

## Context

Flask 应用此前所有路径硬编码 `os.path.dirname(__file__)`（项目目录）。这在开发模式无问题，但 PyInstaller 打包后：
- `__file__` 指向的是 PyInstaller 解压临时目录，**只读**
- 用户数据如果写到这里，重启 app 会丢失（每次解压目录都变）
- 模板/静态资源虽然解压在那里，但 Flask 不会自动发现

必须做"路径运行环境分发"，且改造对开发模式零影响。

## Goals / Non-Goals

### Goals
- 用户拿到 `.app` / `.exe` 双击即用，零环境依赖
- 数据持久化到用户级目录，跨升级保留
- 开发模式行为完全不变（避免我自己开发体验受影响）
- 朋友拿到 zip/dmg 后能自行解决"未签名警告"（说明文档）

### Non-Goals
- 不重写后端为 Electron + Node（成本高 + 违背"尽快"约束）
- 不做应用内自动更新
- 不优化包体积（PyInstaller 默认体积 ~100MB，可接受）
- 不做代码签名（个人项目，证书 $99/年 不值得）

## Key Decisions

### Decision 1: PyInstaller vs Tauri vs Electron

**决定**：PyInstaller。

**理由**：
- 改动 0 行业务代码（spec 只是配置）
- 不需要学新语言/框架
- 1 天能交付双平台
- 缺点（启动稍慢、体积偏大）在"个人 + 朋友"场景下可接受

**未来若不满意**：可升级到 Tauri 套壳（保留 Flask 后端 + Rust webview）。

### Decision 2: 路径分发用 sys.frozen 判定

```python
def is_frozen() -> bool:
    return getattr(sys, 'frozen', False)

def user_data_dir() -> str:
    if is_frozen():
        # ~/Library/Application Support/IELTSVocab (Mac)
        # %APPDATA%/IELTSVocab (Win)
        return platform_specific_path
    return project_root  # 开发模式
```

**理由**：
- `sys.frozen` 是 PyInstaller / cx_Freeze 等打包工具的事实标准
- 单点判定，便于后续扩展（如加 IELTSVOCAB_DATA_DIR 环境变量覆盖）
- 开发模式行为完全不变

### Decision 3: 用户数据位置

| 平台 | 路径 | 理由 |
|------|------|------|
| macOS | `~/Library/Application Support/IELTSVocab/` | Apple HIG 推荐 |
| Windows | `%APPDATA%\IELTSVocab\` | Microsoft 标准 |
| Linux | `~/.local/share/IELTSVocab/` | XDG 标准 |

**不放到**：
- ❌ `~/Documents/`（用户可能误删，且会被 iCloud/OneDrive 同步占空间）
- ❌ `.app` 内部（只读，且升级会丢）
- ❌ `~/`（污染 home）

### Decision 4: 启动端口选择

```python
preferred = 5000
fallbacks = (5001, 5002, 5050, 5500, 8000, 8080)
```

**理由**：
- 5000 是 Flask 默认且文档统一
- macOS 的 AirPlay Receiver 占用 5000，必须有 fallback
- 系统兜底分配作为最后手段

### Decision 5: 浏览器自动打开的延迟

```python
threading.Thread(target=lambda: time.sleep(1.5) or webbrowser.open(url)).start()
```

1.5 秒延迟是必要的：Flask 主进程需要先 bind 端口 + 启动 werkzeug，太快开浏览器会得到"无法连接"。

### Decision 6: .bat 文件编码

**踩坑过程**：
1. 第一版（Mac 默认）：UTF-8 无 BOM + LF → 整段不执行
2. 第二版（加 BOM）：UTF-8 + BOM + CRLF → 能跑但 BOM 字节挡在 `@echo off` 前导致命令被回显
3. 第三版（终态）：**纯 ASCII + CRLF + 无 BOM** → ✓

**决定**：所有 `.bat` 文件只用 ASCII（提示信息也英文），由 `.gitattributes` 强制 CRLF。

### Decision 7: Git 分支与文件分布

```
main 分支：
  paths.py           (通用)
  database.py        (通用)
  app.py             (通用)
  start.bat/command  (通用)
  .gitattributes     (通用)

packaging 分支：
  IELTSVocab.spec
  IELTSVocab_win.spec
  build_mac.sh
  build_win.bat
  build_assets/
  PACKAGING.md
```

**理由**：
- 打包文件改动频繁（试错调优），不应污染 main 的提交历史
- 但 paths.py 等运行时改造对开发模式无害，应在 main（便于本地开发也按"未来打包友好"的方式写代码）
- `packaging` 定期 merge main 同步代码

### Decision 8: 不进 git 的文件

```
build/    PyInstaller 中间产物（每次构建生成）
dist/     最终产物（115MB .app 超过 GitHub 单文件限制）
.DS_Store macOS 系统垃圾
```

`.dmg` / `.zip` 走 GitHub Releases 分发（本次暂不上传，本地保留）。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 未签名 app 首次启动被系统拦 | PACKAGING.md 写清楚解决步骤；朋友能自己搞定 |
| Win Defender 误报 PyInstaller exe | 同上，告知"更多信息→仍要运行" |
| PyInstaller 漏打 hidden import 导致运行时 crash | 用 collect_all 拉全 pdfplumber/openpyxl 等已知大包 |
| 不同 Python 版本（3.10 / 3.14）行为差异 | 仅在 3.14 上验证过，约束 PACKAGING.md 推荐版本 |
| Mac 上写的 .bat 换行符问题 | `.gitattributes` 强制 CRLF，加 Python 转换脚本兜底 |
| 用户数据迁移：从旧版项目目录 vocab.db 到新的 user_data_dir | 开发模式仍用项目目录；打包模式下首次启动建空库（用户用导出/导入 JSON 迁移） |

## Migration Plan

无数据迁移（开发模式数据不动）。

对用户：
1. Mac：双击 `.dmg` → 拖到 Applications → 首次启动允许
2. Win：解压 zip → 双击 `.exe` → 首次允许 Defender 提示
3. 之前用 `start.command/.bat` 的老用户：可继续用（开发模式）；若想迁数据，用 settings 页的"导出 JSON" → 在新 app 内"导入 JSON"

## Open Questions

无。后续若需要：
- 上 GitHub Releases / Actions：另起 change
- 应用内自动更新：另起 change
- 代码签名：另起 change
