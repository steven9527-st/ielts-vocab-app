# 分支使用守则

本仓库使用 **双分支并行** 策略：

| 分支 | 定位 | 谁用 |
|------|------|------|
| `main` | 应用源码 + 文档 + 规格 | 开发者、想看代码的人 |
| `packaging` | main + 桌面 app 打包工具（spec / 构建脚本 / 图标） | 需要构建 `.dmg` / `.exe` 时切过去 |

---

## 一图看懂

```
                        ┌─────────────────────────┐
                        │   GitHub Repository     │
                        └──────────┬──────────────┘
                                   │
                ┌──────────────────┴──────────────────┐
                ▼                                     ▼
        ┌───────────────┐                    ┌──────────────────┐
        │  main 分支     │                    │  packaging 分支   │
        ├───────────────┤                    ├──────────────────┤
        │  app.py       │                    │  ⬆ (含 main 全部) │
        │  paths.py     │                    │  ─────────────   │
        │  database.py  │   定期 merge →     │  IELTSVocab.spec │
        │  templates/   │                    │  IELTSVocab_win  │
        │  static/      │                    │  .spec           │
        │  excel/pdf    │                    │  build_mac.sh    │
        │  parser.py    │                    │  build_win.bat   │
        │  openspec/    │                    │  build_assets/   │
        │  start.bat    │                    │  PACKAGING.md    │
        │  start.command│                    │                  │
        └───────────────┘                    └──────────────────┘
              ↑                                       ↑
              │                                       │
        开发新功能/                            构建桌面 app
        修 bug 在这里                          发布给朋友在这里
```

---

## 分支详情

### `main` — 应用主线

**包含**：
- 完整应用源代码（`app.py` / `database.py` / `excel_parser.py` / `pdf_parser.py` / `paths.py`）
- 前端资源（`templates/` / `static/`）
- 开发启动脚本（`start.bat` / `start.command`）
- 用户文档（`README.md`）
- 规格文档（`openspec/`）
- 仓库配置（`.gitignore` / `.gitattributes`）

**不包含**：
- PyInstaller 配置文件
- 构建脚本
- 应用图标的二进制资源
- 打包说明文档

**适用场景**：
- 平时开发新功能、修 bug
- 别人 clone 仓库只想看代码
- 写测试、改文档、补 spec

### `packaging` — 桌面封装

**额外包含**（共 8 个文件 ~503 行）：
- `IELTSVocab.spec` — macOS PyInstaller 配置
- `IELTSVocab_win.spec` — Windows PyInstaller 配置
- `build_mac.sh` — macOS 一键构建（出 `.dmg`）
- `build_win.bat` — Windows 一键构建（出 `.zip`）
- `build_assets/icon.icns` — macOS 应用图标
- `build_assets/icon.ico` — Windows 应用图标
- `build_assets/icon_source.png` — 图标原图（1024×1024）
- `PACKAGING.md` — 完整打包流程文档

**适用场景**：
- 给朋友 / 用户准备可分发的 `.app` / `.exe`
- 调整图标、应用名、版本号
- 排查打包相关问题（依赖打不进、运行时 crash 等）

---

## 日常工作流

### 1. 平时开发新功能 / 修 bug

```bash
git checkout main
# ... 改代码 ...
git add .
git commit -m "feat: ..."
git push origin main
```

**简单原则**：只在 main 上做日常开发，不切到 packaging。

### 2. 改完代码，想出新版本 .app / .exe

```bash
# Step 1: 切到 packaging，同步 main 的最新代码
git checkout packaging
git merge main          # 把 main 的代码改动合过来

# Step 2: 构建
bash build_mac.sh       # macOS 上跑 → 出 dist/IELTSVocab.dmg
# 或在 Windows 虚拟机上：
build_win.bat           # → 出 dist/IELTSVocab-win.zip

# Step 3: 测试无误后，回到 main
git checkout main
```

> ⚠️ 不要在 packaging 分支上写业务代码。如果在 packaging 上发现需要改业务，请切回 main 改、commit、push，再回 packaging merge。

### 3. 调整打包配置（图标、版本号、spec 改动等）

```bash
git checkout packaging
# ... 改 IELTSVocab.spec / build_mac.sh / icon 等 ...
git add .
git commit -m "build(packaging): 调整..."
git push origin packaging
```

打包文件改动不需要同步回 main（main 不关心这些）。

### 4. 发布一个稳定版本

```bash
git checkout packaging
git merge main
bash build_mac.sh                     # 构建
# 测试 dist/IELTSVocab.app 一切正常后

git tag -a v1.1.0-mac -m "v1.1.0 macOS"
git push origin v1.1.0-mac

# 把 dist/IELTSVocab.dmg 手动分发或上传 GitHub Releases
```

---

## 决策原则

### 文件该放哪个分支？

```
                        ┌────────────────────────────┐
                        │   要新增/修改一个文件了    │
                        └────────────┬───────────────┘
                                     │
              ┌──────────────────────┴───────────────────────┐
              │                                              │
              ▼                                              ▼
    ┌────────────────────┐                        ┌─────────────────────┐
    │ 业务代码 / 模板 / │                        │ PyInstaller spec / │
    │ 静态资源 / 文档  /│                        │ 构建脚本 / 应用图  │
    │ 测试 / 规格      │                        │ 标 / 打包文档       │
    └────────┬───────────┘                        └─────────┬───────────┘
             │                                              │
             ▼                                              ▼
       放 main                                        放 packaging
   （packaging 通过 merge 自动获得）           （main 永远看不到）
```

### 边界案例

- **`paths.py`**：虽然是为打包服务的，但放 main——因为它对开发模式无害，让代码"天然就为打包做好准备"
- **`.gitattributes`**：放 main——所有人都需要正确的 EOL 策略
- **`start.bat` 加固**：放 main——开发者也能用到
- **`build_assets/icon_source.png`**：放 packaging——main 不需要图标资源

---

## 常见问题

### Q: 我能在 packaging 上写业务代码吗？

**不要**。一旦在 packaging 上写业务代码，main 就不会自动得到，长此以往两条分支会"功能分歧"。

正确做法：切回 main 改，commit、push，再回 packaging merge。

### Q: packaging 和 main 哪个更新？

理论上**两者代码部分应该完全一样**（packaging 通过定期 merge main 保持同步）。如果出现 main 比 packaging 新，做一次 `git merge main` 即可。

### Q: 朋友拿到 `.dmg` 后我又改了 main 代码，需要做什么？

```bash
git checkout packaging
git merge main
bash build_mac.sh       # 重新构建
# 发新的 .dmg 给朋友
```

### Q: 别人 clone 仓库默认是 main 还是 packaging？

默认 main。要切 packaging：
```bash
git clone https://github.com/steven9527-st/ielts-vocab-app.git
cd ielts-vocab-app
git checkout packaging
```

### Q: 为什么不直接合并成一个分支？

参考 `openspec/specs/desktop-packaging/spec.md` 与归档的 `desktop-app-packaging/design.md`，简短答：
1. 打包文件改动频繁（试错调优），不该污染 main 的提交历史
2. 打包文件对纯阅读代码的人是噪音
3. 减少 clone 体积（icon 资源 ~1.4MB + 脚本）
4. 未来加 CI/CD 或换打包方案时，main 不受影响

---

## 标签（Tag）使用

发布稳定版本时打 tag：

```bash
git tag -a v<MAJOR>.<MINOR>.<PATCH>-<platform> -m "说明"
git push origin v<MAJOR>.<MINOR>.<PATCH>-<platform>
```

示例：
- `v1.0.0-mac` — macOS 首个封装版本
- `v1.0.0-win` — Windows 首个封装版本（如发布）
- `v1.1.0` — 跨平台版本（如同时出 Mac + Win）

tag 通常打在 `packaging` 分支上（因为 `packaging = main 全部 + 打包工具`，等于一个完整的"发布快照"）。
