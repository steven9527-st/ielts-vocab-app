## 1. PDF 解析空格压缩

- [x] 1.1 pdf_parser.py 成功匹配后 english 增加 `re.sub(r'\s+', ' ', ...)` 压缩空格
- [x] 1.2 pdf_parser.py 失败回退提取的 english_guess 同样压缩空格

> 已在 pdf_parser.py 中实现 (`re.sub(r'\s+', ' ', ...)`)。
