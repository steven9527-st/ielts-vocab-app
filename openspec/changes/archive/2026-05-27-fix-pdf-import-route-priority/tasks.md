## 1. 解析层加固

- [x] 1.1 在 `excel_parser.py` 新增 `_looks_like_word_column(col_cells: list[str]) -> bool` 辅助函数：返回某列是否「至少 50% 非空 cell 含有 ≥2 字母连续字母串」
- [x] 1.2 修改 `guess_columns` 英文列识别：候选列必须先通过 `_looks_like_word_column`；若过滤后无候选则回退到原有"ASCII 占比最高"规则（保护同义词词库样本）

## 2. 路由层调整分发顺序

- [x] 2.1 修改 `app.py` 的 `/import/parse` 路由 PDF 分支：先调 `parse_pdf`，统计命中率（非 failed entries / 总 entries 数）
- [x] 2.2 当命中率 ≥ 30% 且总 entries ≥ 5 → 直接采用 `parse_pdf` 结果，跳预览页（保持现有去重逻辑）
- [x] 2.3 当命中率不足 → 尝试 `extract_pdf_tables`，命中则走列映射页
- [x] 2.4 当表格路径也未命中 → 返回 `parse_pdf` 的原始结果（即使较空），让用户在预览页看到现状

## 3. 单元测试 / 回归测试

- [x] 3.1 新增 `tests/test_pdf_route_priority.py`：用 reportlab 构造一个**带表格线 + 编号格式**的 PDF（4 列：序号/单词/音标/释义），验证走的是 `_ENTRY_RE` 而不是 `extract_pdf_tables`
- [x] 3.2 在 `tests/test_excel_synonym_mode.py` 新增用例：包含序号列的 rows 输入，断言序号列不会被选为 `english_col`
- [x] 3.3 跑全部既有测试（13 个）确保零回归

## 4. 实际样本端到端验证

- [x] 4.1 用用户提供的 `雅思阅读高分词汇.pdf`（项目根目录）做端到端测试：清空开发 vocab.db 中的同名词库 → 通过 HTTP 接口模拟上传 → 验证入库后英文列是 `aback` / `abate` 而非 `1.` / `2.`
- [x] 4.2 用 `add-pdf-table-import` 时期的同义词词库样本（测试代码构造）验证：表格 PDF 仍能正确回退到表格路径并走列映射

## 5. 文档与发布

- [x] 5.1 更新 README.md「PDF 格式说明」章节：补充"带表格线的编号词表也支持"说明
- [x] 5.2 在归档时记录修复历史（commit message + change archive）

## 6. 重新打包（构建后步骤）

- [ ] 6.1 切到 packaging 分支，merge main，重新跑 `bash build_mac.sh` 生成新 .dmg
- [ ] 6.2 在 Windows 虚拟机重新跑 `build_win.bat` 生成新 zip
- [ ] 6.3 Windows 用户操作指引：删除错误的「雅思阅读高分词汇」词库 → 重新导入

## 7. 验收

- [ ] 7.1 `雅思阅读高分词汇.pdf` 在新 Mac App 中导入后，词库管理页显示 english=aback 等正确数据
- [ ] 7.2 同义词词库 PDF（add-pdf-table-import 时期的样本）继续走表格路径，e2e 测试不退化
- [ ] 7.3 Windows 新构建产物中同一 PDF 同样得到正确结果
- [ ] 7.4 `openspec validate fix-pdf-import-route-priority --strict` 通过
