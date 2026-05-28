## ADDED Requirements

### Requirement: 双英文列同义词导入

当 Excel/CSV 词库使用「双英文列 + 单中文列」结构（典型如雅思同义词配对题词库）时，列映射页 SHALL 在「同义词模式」下提供「英文列 2」下拉选项；用户指定第二英文列后，每行 SHALL 展开为两条互为同义词的词条 entries。

#### Scenario: 同义词模式下显示英文列 2 下拉

- **GIVEN** 用户上传 Excel 文件并进入列映射页
- **AND** 选择「同义词模式」单选框
- **WHEN** 模式切换完成
- **THEN** UI SHALL 显示「英文列 2」下拉框
- **AND** 该下拉框选项 SHALL 与「英文列」「中文列」相同（A/B/C/D... + 表头标签）
- **AND** 默认值 SHALL 为「未指定」（-1）

#### Scenario: 切回标准模式时隐藏英文列 2

- **GIVEN** 用户当前处于同义词模式且「英文列 2」下拉可见
- **WHEN** 用户切换到「标准模式」
- **THEN** 「英文列 2」下拉 SHALL 被隐藏
- **AND** 切换不应清空「英文列」「中文列」「英文列 2」的已选值（保持用户输入）

#### Scenario: 双英文列导入展开为两条 entries

- **GIVEN** Excel 一行：`B="keep sth off"  C="prevent sth from appearing"  D="保持某事关闭 / 防止某事出现"`
- **AND** 用户在列映射页选择：英文列=B、英文列 2=C、中文列=D、导入模式=同义词模式
- **WHEN** 后端 `apply_mapping(english_col=B, english_col_2=C, chinese_col=D, import_mode='synonym')` 执行
- **THEN** 该行 SHALL 输出两条 entries：
  - entry1: `english="keep sth off"`, `chinese="保持某事关闭"`, `synonyms="prevent sth from appearing"`
  - entry2: `english="prevent sth from appearing"`, `chinese="防止某事出现"`, `synonyms="keep sth off"`

#### Scenario: 中文按第一个 / 拆分

- **GIVEN** D 列中文文本为 `"前半 / 中半 / 后半"`（多个分隔符）
- **WHEN** 后端调用 `_split_chinese_pair(text)`
- **THEN** SHALL 返回 `("前半", "中半 / 后半")`
- **AND** 仅以第一个 `/` 作分隔点；其后的内容全部归第二段

#### Scenario: 中文无分隔符时归前半

- **GIVEN** D 列中文文本为 `"损失率惊人"`（无 `/` 分隔符）
- **WHEN** 后端调用 `_split_chinese_pair(text)`
- **THEN** SHALL 返回 `("损失率惊人", "")`
- **AND** entry1 chinese 非空（保持原样），entry2 chinese 为空

#### Scenario: 中文为空字符串

- **GIVEN** D 列中文文本为空字符串或仅含空白字符
- **WHEN** 后端调用 `_split_chinese_pair(text)`
- **THEN** SHALL 返回 `("", "")`
- **AND** 两条 entries 的 chinese 均为空，`failed=True`，预览页高亮显示

#### Scenario: 英文列 2 未指定时回退到原逻辑

- **GIVEN** 用户在同义词模式下未选择「英文列 2」（保持默认 -1）
- **WHEN** `apply_mapping` 执行
- **THEN** SHALL 走既有「单英文列同义词模式」逻辑（一行 → 一条 entry）
- **AND** 不触发展开，与改造前行为完全一致

#### Scenario: 列冲突校验

- **GIVEN** 用户提交映射时，`english_col == english_col_2` 或 `english_col_2 == chinese_col`
- **WHEN** `/import/excel_apply` 路由处理请求
- **THEN** SHALL 返回 HTTP 400 与错误信息「英文列 2 不能与英文列 / 中文列相同」
- **AND** 不进行任何映射或入库

#### Scenario: 标准模式不受影响

- **GIVEN** 用户选择「标准模式」（B 列是中文释义）
- **WHEN** 提交映射
- **THEN** `english_col_2` 参数即使被前端误传也 SHALL 被忽略
- **AND** 走原始单列单行映射逻辑

#### Scenario: 预览页展示展开后的双倍行数

- **GIVEN** 原始 Excel 共 100 行（去除表头），双英文列同义词模式
- **WHEN** 提交映射后跳转到预览页
- **THEN** 预览页 SHALL 显示 200 个 entries（每行展开为 2 条）
- **AND** 失败项（entry chinese 为空）SHALL 与既有规则一致地高亮
