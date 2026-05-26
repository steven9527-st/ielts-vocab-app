## 1. 数据层

- [x] 1.1 database.py: words 表新增 `phonetic TEXT DEFAULT ''` 和 `pos TEXT DEFAULT ''` 列
- [x] 1.2 pdf_parser.py: 正则改造，提取 phonetic 和 pos；返回字典新增两个字段

## 2. 后端 API

- [x] 2.1 app.py import_confirm: 写入 phonetic/pos 字段
- [x] 2.2 app.py 导入预览和词库查询：确保新字段透传到前端

## 3. 前端 UI

- [x] 3.1 import_preview.html: 预览表增加音标/词性列
- [x] 3.2 library.html: 单词列表显示音标和词性
- [x] 3.3 flashcard.html: 翻卡背面展示音标+词性+中文释义（已升级为正面显示音标 + 反面显示按词性分行的释义）
- [x] 3.4 style.css: 音标/词性的样式（小字、灰色、等宽）

> 注：所有任务已在持续迭代中完成。最终视觉布局比原计划更优。
