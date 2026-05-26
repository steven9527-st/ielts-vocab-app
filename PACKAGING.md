# 桌面 App 打包说明

本分支（`packaging`）维护将 Flask 应用打包为桌面 .app / .exe 的脚本和资源，主分支（`main`）保持代码精简不引入打包文件。

---

## 当前状态

| 平台 | 状态 | 产物 |
|------|------|------|
| macOS | ✅ 已就绪 | `dist/IELTSVocab.app` + `dist/IELTSVocab.dmg` |
| Windows | ⏳ TODO | 需在 Windows 机器上跑（脚本待补） |

---

## 目录结构

```
ielts-vocab-app/
├── IELTSVocab.spec          # PyInstaller 配置（macOS .app 定义）
├── build_mac.sh             # 一键构建脚本
├── build_assets/
│   ├── icon.icns            # macOS 应用图标（多分辨率合一）
│   └── *.png                # 图标源文件
├── paths.py                 # 运行环境路径分发（主分支）
└── dist/                    # 构建产物（.gitignore，本地存在）
    ├── IELTSVocab.app
    └── IELTSVocab.dmg
```

---

## macOS 构建

### 前置要求
- macOS 系统
- Python 3.10+（项目当前用 3.14）
- 项目依赖（`pip install -r requirements.txt`）

### 一键构建
```bash
bash build_mac.sh
```

脚本自动完成：
1. 检查并安装 PyInstaller / Pillow
2. 清理旧 `build/` `dist/`
3. 用 `IELTSVocab.spec` 构建 `IELTSVocab.app`
4. 用 `hdiutil` 打包成 `IELTSVocab.dmg`（带"拖到 Applications"快捷方式）

预计耗时：1-2 分钟
产物大小：.app ~115MB / .dmg ~62MB

### 测试
```bash
open dist/IELTSVocab.app
```
应自动打开浏览器到 `http://127.0.0.1:<auto-port>`，启动端口优先 5000，被占用时 fallback 至 5001/5002/5050/5500/8000/8080。

### 用户数据位置
应用启动后会在用户目录创建数据文件：
```
~/Library/Application Support/IELTSVocab/
├── vocab.db          # SQLite 主数据库
└── .tmp_parse/       # 临时解析数据
```

卸载方式：拖 `IELTSVocab.app` 到废纸篓 + 删除上述目录。

---

## Windows 构建（TODO）

预期方案：
- 文件：`IELTSVocab_win.spec` + `build_win.bat`
- 在 Windows 机器上跑（PyInstaller 不能跨平台编译）
- 产物：`dist/IELTSVocab.exe`（单文件）或文件夹 + 安装包

实现细节：
- `BUNDLE` 段不适用（macOS 专用），改用 `EXE` + `COLLECT`
- 图标转 `.ico` 格式（`build_assets/icon.ico`）
- 用 NSIS 或 Inno Setup 做安装包（可选）

---

## 分发说明

由于未做 Apple 开发者签名，首次启动时 macOS 会提示：
> 无法打开"IELTSVocab"，因为 Apple 无法检查它是否包含恶意软件

**朋友的解决方法**：
1. 把 `IELTSVocab.app` 拖到 `Applications`
2. 首次双击如被拦截 → 打开 `系统设置 → 隐私与安全性`
3. 滚到底部，会看到「已阻止 IELTSVocab 启动」→ 点「仍要打开」
4. 之后双击即可正常使用

如果未来要免去这一步，需要：
- 加入 Apple Developer Program（$99/年）
- 签名 + 公证（codesign + notarytool）

---

## 版本规范

- 主版本号更新：`IELTSVocab.spec` 中的 `version='1.0.0'` 和 `CFBundleShortVersionString`
- 同时打 git tag：`git tag -a v1.0.0-mac -m "..."`

---

## 主分支同步

`packaging` 分支应定期合并 `main` 上的代码更新：

```bash
git checkout packaging
git merge main
# 解决冲突（通常不会有，因为 packaging 只多加文件）
bash build_mac.sh   # 重新构建验证
```
