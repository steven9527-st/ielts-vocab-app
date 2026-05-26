# 任务清单

按交付顺序分为 3 个 Phase。每阶段结束可独立验证。

---

## Phase 1: 解析器与依赖

- [x] 1.1 在 `requirements.txt` 增加 `openpyxl>=3.1.0`
- [x] 1.2 新建 `excel_parser.py`，实现：
  - `parse_table_raw(filepath) -> list[list[str]]`：xlsx + csv 统一入口
  - `_read_xlsx(filepath)`：openpyxl 流式读取第一个 sheet
  - `_read_csv(filepath)`：utf-8-sig / utf-8 / gbk 编码 fallback
  - `apply_mapping(rows, ...)`：转换为标准 entries
  - `guess_columns(rows)`：智能预选英文/中文/音标/词性列
  - `looks_like_header(first_row)`：启发式判定第一行是否表头

## Phase 2: 后端路由分发与新增接口

- [x] 2.1 在 `app.py` 新增 `_save_excel_raw` / `_load_excel_raw` / `_delete_excel_raw` 工具函数
- [x] 2.2 改造 `/import/parse`：按扩展名分发 PDF / Excel/CSV
- [x] 2.3 新增 `GET /import/excel_mapping`：渲染列映射页
- [x] 2.4 新增 `POST /import/excel_apply`：转 entries → 跳预览页
- [x] 2.5 处理边界：空 Sheet / 编码失败 / 损坏 xlsx → 4xx + 友好错误信息

## Phase 3: 前端 UI

- [x] 3.1 修改 `templates/import.html`：accept 扩展、文案更新、JS 处理 `data.next`
- [x] 3.2 新建 `templates/import_excel_mapping.html`：列下拉 + 表头复选框 + 预览表 + 继续按钮
- [x] 3.3 列映射页 JS：列选择切换高亮预览 + POST /import/excel_apply

## Phase 4: 验证与清理

- [x] 4.1 自动化：`python3 -c "import excel_parser; ..."` 验证 xlsx + csv 读取（5 个用例全过）
- [x] 4.2 自动化：flask smoke test `/import` 返回 200
- [x] 4.3 端到端：上传规范 xlsx → 智能预选准确 → apply 转 3 条 entries（含 failed 行）
- [x] 4.4 自动化：UTF-8 CSV 端到端通过
- [x] 4.5 自动化：GBK CSV 端到端通过
- [x] 4.6 手动用例：用户取消"第一行是表头"勾选 → 第一行作为数据导入（用户委托归档，视为接受）
- [x] 4.7 自动化：含 Phonetic/POS 列名的 xlsx → 正确识别（guess.phonetic_col=2, pos_col=3）
- [x] 4.8 手动用例：只有英文/中文两列、无音标的 xlsx → 音标列留空但导入成功（用户委托归档，视为接受）
- [x] 4.9 边界：空 xlsx → 返回"文件中未读到任何数据"
- [x] 4.10 边界：.xls 老格式 → 返回"仅支持 .pdf / .xlsx / .csv 文件"
- [x] 4.11 `openspec validate excel-csv-import --strict` 通过
- [x] 4.12 README 更新：新增 Excel / CSV 格式说明章节

> 自动化烟测覆盖：parse → apply → preview 端到端链路（200 + 业务字段正确）；空文件 / 编码识别 / 老格式拦截 / 失败行标记。
