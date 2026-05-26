# 雅思词汇记忆 App

本地运行的单词记忆 Web 应用，支持从 PDF 词表导入单词，通过翻卡学习和选择题测验系统化记忆雅思词汇。

## 功能

- **PDF 导入** — 解析「序号. 单词 英[音标] 词性+释义」格式词表，预览校对后一键导入
- **Excel / CSV 导入** — 支持 `.xlsx` 与 `.csv`（UTF-8 / UTF-8-BOM / GBK 自动识别），通过列映射页选择英文/中文列，音标/词性按列名自动识别
- **多词库管理** — 支持多个词库共存，全站顶部一键切换，学习/测试入口智能弹出词库选择浮层
- **翻卡学习** — 每日自定义学习量，极简翻卡交互，支持断点续传
- **单词发音** — 卡片音标旁 🔊 按钮，使用浏览器原生 Web Speech API 朗读（en-US）
- **学习测验** — 翻卡结束后立即测验，4 选 1，错题循环重做直到 100% 通关
- **测试模式** — 支持**文字测试**与**听力测试**两种类型，从全词库随机出题
- **词库管理** — 搜索、编辑、删除单词，手动修改掌握状态
- **打卡 Streak** — 记录连续学习天数
- **数据备份** — 导出/导入 JSON 文件，换电脑不丢数据

> **发音功能说明**：朗读使用浏览器原生 `window.speechSynthesis` API，无需联网，无需额外安装。
> macOS Safari/Chrome、Windows 10+ Chrome/Edge 均支持；少数老旧浏览器（如老版 IE）不支持时，🔊 按钮会自动禁用并提示。

## 快速开始

### macOS

```bash
git clone https://github.com/steven9527-st/ielts-vocab-app.git
cd ielts-vocab-app
双击 start.command
```

浏览器会自动打开 `http://127.0.0.1:5000`。

### Windows

```bat
git clone https://github.com/steven9527-st/ielts-vocab-app.git
cd ielts-vocab-app
双击 start.bat
```

### 手动启动

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python3 app.py
# 访问 http://127.0.0.1:5000
```

> 依赖：Python 3.9+，无需安装数据库，数据存储在本地 `vocab.db`。

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3 + Flask |
| 数据库 | SQLite（本地文件） |
| PDF 解析 | pdfplumber |
| 前端 | 原生 HTML / CSS / JS（无框架） |
| UI 风格 | Vercel Design System（Geist 字体，shadow-as-border） |

## 项目结构

```
ielts-vocab-app/
├── app.py              # Flask 主应用（路由、业务逻辑）
├── database.py         # SQLite 初始化与连接
├── pdf_parser.py       # PDF 词表解析
├── excel_parser.py     # Excel / CSV 词表解析
├── requirements.txt    # Python 依赖
├── start.command       # macOS 一键启动脚本
├── start.bat           # Windows 一键启动脚本
├── static/
│   └── style.css       # Vercel 风格 UI 组件库
└── templates/          # Jinja2 HTML 模板
    ├── base.html
    ├── index.html           # Dashboard
    ├── import.html          # PDF 上传
    ├── import_preview.html  # 预览校对
    ├── flashcard.html       # 翻卡学习
    ├── quiz.html            # 4选1 答题
    ├── quiz_result.html     # 批改页
    ├── test_setup.html      # 测试设置
    ├── test_result.html     # 成绩页
    ├── library.html         # 词库管理
    └── settings.html        # 数据备份
```

## PDF 格式说明

支持以下格式的词表：

```
1. aback   英 [ə'bæk]   adv. 大吃一惊
2. abate   英 [əˈbeɪt]  v. 减轻; 失效
691. labour intensive 英 [...] 劳动力密集
```

解析覆盖率约 98%，无法自动解析的行在预览页高亮显示，可手动填写或批量忽略。

## Excel / CSV 格式说明

任意列结构均可——上传后在"列映射"页选择哪列是英文、哪列是中文即可。

- **xlsx**：只读取第一个 Sheet；行/列顺序任意
- **csv**：自动识别 UTF-8 / UTF-8-BOM / GBK 编码（Excel 导出的中文 CSV 通常是 GBK）
- **音标 / 词性列**：根据列名（`phonetic / pronunciation / IPA / 音标 / pos / 词性` 等）自动识别，未命中则导入后这两列为空
- **第一行是否表头**：系统启发式判定并默认勾选，可手动取消

## 数据库表结构

```sql
word_lists    -- 词库（支持多词库）
words         -- 单词（list_id, english, chinese, status）
study_log     -- 学习记录（日期、模式、正确率、用时）
learn_session -- 学习会话（支持断点续传）
```

## 开发说明

- 本地数据文件 `vocab.db` 已加入 `.gitignore`，不会随代码提交
- 启动脚本会自动创建 `venv` 虚拟环境并安装依赖，无需手动配置
- Flask 仅监听 `127.0.0.1`，数据不出本机

## 相关文档

- [`BRANCHES.md`](BRANCHES.md) — 分支使用守则（main vs packaging）
- [`PACKAGING.md`](PACKAGING.md) — 桌面 app 打包流程（需切到 `packaging` 分支查看）
- [`openspec/`](openspec/) — 完整规格文档与设计决策归档
