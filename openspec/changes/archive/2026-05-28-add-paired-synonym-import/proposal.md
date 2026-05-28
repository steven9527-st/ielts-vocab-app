## Why

当前 Excel 同义词词库导入只支持「单英文列 + 单中文列」结构，但典型的雅思同义词配对词库（如 C19 章节练习表）是「双英文列（B + C）+ 一个中文翻译列（D）」格式：

```
| 章节        | 文章 (英文)        | 题目 (英文)              | 中文翻译                |
| C19 Test 1  | keep sth off       | prevent sth from appearing | 保持某事关闭 / 防止某事出现 |
| C19 Test 1  | routine            | frequent exposure         | 常规 / 频繁接触           |
```

D 列的中文是 **B↔前半 / C↔后半** 的对应结构（用 `/` 分隔）。

现有列映射 UI 只允许选 1 个英文列，用户被迫：

- 要么只导入 B 列（丢失 C 列同义词）
- 要么把 D 列整体作为 chinese（中文与英文不对应、显示混乱）

这次让导入流程理解「双英文列 + 拆分中文」语义，把每行展开成两条对应词条。

## What Changes

- **列映射页（`import_excel_mapping.html`）**：在「同义词模式」激活时显示新增「英文列 2」下拉，让用户显式指定第二个英文列
- **后端 `apply_mapping()`**：支持新参数 `english_col_2`；为 `synonym` 模式下提供「双列展开」逻辑——每行 Excel 输出两条 entries，互为同义词
- **中文拆分策略**：D 列按第一个 `/` 拆成两半（前半归 B 列对应词，后半归 C 列对应词）；若 D 列无 `/`，则 B 列拿到完整中文，C 列 chinese 为空
- **保持向后兼容**：标准模式与"单英文列同义词模式"路径不变，只在「同义词模式 + 指定 english_col_2」时启用展开逻辑
- **预览页**：自动显示展开后的双倍行数，让用户在 confirm 前直观看到拆分结果

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `import-excel`: 列映射规则扩展——新增「英文列 2」（仅同义词模式）；apply_mapping 支持双列展开 + 中文按 `/` 拆分

## Impact

**前端**：
- `templates/import_excel_mapping.html`：同义词模式下新增「英文列 2」下拉；表单提交携带 `english_col_2`
- 列名标签自动识别（如 `B: 文章 (英文)` `C: 题目 (英文)` 中"英文"可作为提示）

**后端**：
- `excel_parser.py` `apply_mapping()`：新增 `english_col_2` 参数；在 synonym 模式下若 `english_col_2 >= 0`，每行展开成两条 entries
- `excel_parser.py` `_split_chinese_pair(text)` 新工具函数：处理 `/` 拆分逻辑
- `app.py` `/import/excel_apply` 路由：接收 `english_col_2` 字段并透传

**数据**：
- 无 schema 变更
- 输出的 entries 结构一致（每条仍为 `{english, chinese, phonetic, pos, synonyms, failed}`）
- 入库后由现有 UNIQUE(list_id, english) 自然去重；不同 english 的两条独立存储

**测试**：
- 新增 `tests/test_paired_synonym_import.py`：覆盖单元逻辑（`apply_mapping` 双列展开、中文拆分边界）+ 端到端（API `/import/excel_apply` 接收双列参数）

**风险**：
- 极小。新参数与新逻辑都用 `english_col_2 >= 0` 作为开关，不影响既有路径
- 已导入的旧词库不受影响（导入时即写入 DB，本次仅改导入侧）
