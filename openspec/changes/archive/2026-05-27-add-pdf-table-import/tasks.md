## 1. PDF 解析层 — 表格抽取与文字层探测

- [x] 1.1 在 `pdf_parser.py` 新增 `has_text_layer(filepath) -> bool`：用 `pdfplumber.open` 打开 PDF，统计所有页 `chars` 总数，< 10 返回 False
- [x] 1.2 在 `pdf_parser.py` 新增 `extract_pdf_tables(filepath) -> list[list[str]] | None`：调用每页 `extract_tables()`，flatten 所有页所有表格的所有行；按"列数最常见值"对齐结构，剔除列数异常行；剔除单 cell 标题行；返回合并后的 rows，未抽到任何有效表格时返回 None
- [x] 1.3 编写单元测试：构造一个含 C4 Test 1 标题 + 文章/题目表头 + 6 行同义词数据的样例 PDF（用 reportlab 或预置 fixture），验证 `extract_pdf_tables` 正确返回 rows 且非数据行被剔除
- [x] 1.4 编写单元测试：传入扫描图 PDF（无文字层）让 `has_text_layer` 返回 False
- [x] 1.5 编写单元测试：传入现有的编号词表 PDF（reading list 风格），让 `extract_pdf_tables` 返回 None（确保不误命中）

## 2. Excel 解析层 — 同义词模式 + 中文列识别放宽

- [x] 2.1 在 `excel_parser.py` 的 `apply_mapping` 增加参数 `import_mode: str = 'standard'`，仅接受 `'standard'` 或 `'synonym'`；当 `'synonym'` 时，每条 entry 的 `synonyms` 字段 = `chinese` 字段；保留对原有 `synonym_col` 显式映射的优先级（显式列优先于模式推断）
- [x] 2.2 在 `guess_columns` 中放宽中文列识别：当所有列中文占比都 < 0.2 但有 ≥2 列 ASCII 占比 > 0.5 时，挑 ASCII 第二高的列作为 chinese_col 候选
- [x] 2.3 在 `guess_columns` 返回值新增 `suggested_mode: 'standard'|'synonym'` 字段：释义列中文字符占比 < 10% 时返回 `'synonym'`，否则 `'standard'`
- [x] 2.4 编写单元测试：英文-英文双列输入（如本变更 design 中的 alarming rate of loss 样例），断言 `guess_columns` 返回 `english_col=0, chinese_col=1, suggested_mode='synonym'`
- [x] 2.5 编写单元测试：调 `apply_mapping(..., import_mode='synonym')`，断言每条 entry 的 `chinese == synonyms`
- [x] 2.6 编写单元测试：现有标准 Excel 词表（含中文释义列），断言 `suggested_mode='standard'` 且行为完全不变

## 3. 路由层 — PDF 双路径分发

- [x] 3.1 修改 `app.py` 的 `/import/parse` 路由：上传 PDF 后先调用 `has_text_layer`，False 则返回 400 错误（文案：扫描图 PDF 引导提示）
- [x] 3.2 在 PDF 分支中先调用 `extract_pdf_tables`：若返回非 None，写入 `_save_excel_raw`（与 Excel 路径完全一致）并返回 `{next: '/import/excel_mapping'}`；若返回 None，降级到现有 `parse_pdf` 编号词表流程（保持现状不变）
- [x] 3.3 修改 `/import/excel_apply` 路由：从请求体读取 `import_mode` 字段（默认 `'standard'`），透传给 `apply_mapping`
- [x] 3.4 手工冒烟测试：上传一份你的实际同义词 PDF，验证能走通到列映射页 → 预览页 → 入库 → 同义词学习入口出现

## 4. 前端 — 列映射页导入模式开关

- [x] 4.1 在 `templates/import_excel_mapping.html` 增加导入模式单选 UI（两个 radio：标准模式 / 同义词模式），放在"第一行是表头"复选框旁边
- [x] 4.2 用 Jinja `{% if guess.suggested_mode == 'synonym' %}` 让单选默认勾选合理项；在 UI 旁标注"已根据内容自动判断，可手动调整"
- [x] 4.3 修改 `continueBtn` 的 fetch 调用，把 `import_mode` 加入 JSON body
- [x] 4.4 视觉一致性：复用现有 radio 组件样式（参考 `test_setup.html` 的 test_type radio 写法）

## 5. 错误处理与边界

- [x] 5.1 扫描图 PDF 错误提示文案在 `app.py` 集中定义（避免重复字符串）
- [x] 5.2 在 `templates/import.html` 的常见错误提示区补充一条"如果是扫描图 PDF，请先用 WPS / Adobe 转换为可选中文字的 PDF"
- [x] 5.3 处理 `extract_tables()` 抛异常的情况：捕获后视为"未抽到表格"，降级到 `_ENTRY_RE` 路径，不向用户暴露 pdfplumber 内部错误

## 6. 文档与回归

- [x] 6.1 更新 `README.md` 的"PDF 格式说明"章节：增加"双列表格 PDF（含同义词词库）"支持说明
- [x] 6.2 整体冒烟回归：①传统编号词表 PDF 导入 ②表格 PDF 标准模式 ③表格 PDF 同义词模式 ④Excel 导入 ⑤CSV 导入，确认五条路径都正常
- [x] 6.3 验证桌面打包路径不受影响（`paths.py` 中 PyInstaller 资源路径未变更）

## 7. 验收

- [x] 7.1 用户实际 PDF（C4-Test1 风格同义词词库）能成功导入并出现在同义词学习入口
- [x] 7.2 现有编号词表 PDF（如 IELTS 3500）解析覆盖率维持在变更前水平（≥98%）
- [x] 7.3 扫描图 PDF 返回明确错误提示而非空预览页
- [x] 7.4 `openspec validate add-pdf-table-import --strict` 通过
