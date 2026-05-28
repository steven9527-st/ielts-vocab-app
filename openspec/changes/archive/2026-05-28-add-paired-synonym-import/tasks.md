## 1. 后端：拆分函数与 apply_mapping 改造

- [x] 1.1 在 `excel_parser.py` 新增 `_split_chinese_pair(text: str) -> tuple[str, str]`：按第一个 `/` 拆分；处理无分隔符、空字符串、None、多分隔符等边界
- [x] 1.2 修改 `apply_mapping()`：函数签名增加 `english_col_2: int = -1` 参数；docstring 补充说明
- [x] 1.3 在 `apply_mapping()` 主循环里加分支：当 `import_mode == 'synonym'` 且 `english_col_2 >= 0` 时，每行展开为两条 entries（互为同义词，中文按 `_split_chinese_pair` 拆分对应给两条）
- [x] 1.4 单元自测：`python3 -c "from excel_parser import _split_chinese_pair; assert _split_chinese_pair('A / B') == ('A','B'); assert _split_chinese_pair('A') == ('A',''); assert _split_chinese_pair('') == ('',''); assert _split_chinese_pair(None) == ('',''); print('OK')"`

## 2. 后端：路由层适配

- [x] 2.1 修改 `app.py` `/import/excel_apply` 路由：从 JSON body 读取 `english_col_2`（默认 -1）
- [x] 2.2 加列冲突校验：`english_col_2 >= 0 and (english_col_2 == english_col or english_col_2 == chinese_col)` 返回 400
- [x] 2.3 调用 `apply_mapping()` 时透传 `english_col_2` 参数

## 3. 前端：列映射页 UI

- [x] 3.1 修改 `templates/import_excel_mapping.html`：在「英文列」「中文列」下拉旁新增「英文列 2」下拉（含 ID `englishCol2`），默认隐藏（`style="display:none"`）
- [x] 3.2 「英文列 2」下拉的 options 与既有英文列下拉相同，包含「-- 未指定 --」（value=-1）选项作为默认
- [x] 3.3 加 JS：监听 `import_mode` radio 变化；切到 `synonym` 显示英文列 2，切到 `standard` 隐藏
- [x] 3.4 表单提交时把 `englishCol2.value` 包到 fetch JSON body 里发给后端
- [x] 3.5 加文案提示：英文列 2 旁边小字「适用于雅思同义词配对题词库（双英文列结构）」
- [x] 3.6 英文列 2 在预览表格上以略深蓝色高亮（COLOR_EN2）便于区分主英文列

## 4. 测试

- [x] 4.1 新增 `tests/test_paired_synonym_import.py`：覆盖 `_split_chinese_pair` 所有边界（含 `/`、不含、空、None、多个 `/`、前后空白）
- [x] 4.2 测试 `apply_mapping` 双列展开：构造截图中 C19 词库样本（多行），验证输出 entries 数量为 N×2，每对 entries 互为同义词
- [x] 4.3 测试 `apply_mapping` 在 `english_col_2=-1` 时走原路径（向后兼容）
- [x] 4.4 测试 `/import/excel_apply` 路由列冲突校验：`english_col == english_col_2` → 400
- [x] 4.5 测试 D 列无 `/` 时 entry2.chinese 为空且 failed=True
- [x] 4.6 跑全部既有测试（≥ 41 个）确保零回归：**56 测试全绿**（41 既有 + 15 新增）

## 5. 文档与验收

- [x] 5.1 更新 `README.md`「Excel / CSV 格式说明」段落，新增「双英文列同义词词库」子段，说明列结构与中文拆分规则
- [ ] 5.2 在 main 分支提交所有改动；commit message: "feat(import): 支持双英文列同义词词库导入（Excel/CSV）"
- [ ] 5.3 切到 packaging 分支 merge main，跑 `bash build_mac.sh` 生成新 .app/.dmg
- [ ] 5.4 push packaging 到远端，提示用户在 Win 虚拟机 pull 后 `build_win.bat`
- [x] 5.5 `openspec validate add-paired-synonym-import --strict` 通过
- [ ] 5.6 用户用截图中的 C19 同义词词库实测：选英文列=B、英文列 2=C、中文列=D、同义词模式 → 预览页显示双倍行数 + 中文已拆分对应 ✓
- [ ] 5.7 实测进入「同义词学习」：每个词正面显示自己的中文（半段），背面显示自己的英文同义词 ✓
- [ ] 5.8 用户 Win 实测：跨平台行为一致 ✓
