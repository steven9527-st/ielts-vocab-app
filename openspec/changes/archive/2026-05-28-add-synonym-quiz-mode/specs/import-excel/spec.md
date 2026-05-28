## ADDED Requirements

### Requirement: 导入时持久化词库类型

`/import/excel_apply` 路由在创建新词库时 SHALL 根据 `import_mode` 字段写入对应的 `word_lists.type`，作为后续测验出题方式判断的权威依据。

#### Scenario: 标准模式映射为 type='standard'

- **GIVEN** 用户在列映射页提交时 `import_mode == 'standard'`
- **WHEN** 路由创建新词库记录
- **THEN** SHALL 在 `INSERT INTO word_lists` 语句中显式写入 `type='standard'`

#### Scenario: 同义词模式映射为 type='synonym'

- **GIVEN** 用户在列映射页提交时 `import_mode == 'synonym'`（无论是否启用 `english_col_2` 双英文列展开）
- **WHEN** 路由创建新词库记录
- **THEN** SHALL 在 `INSERT INTO word_lists` 语句中显式写入 `type='synonym'`

#### Scenario: 默认值兜底

- **GIVEN** 路由因任何原因无法确定 `import_mode`
- **WHEN** 创建词库
- **THEN** `type` SHALL 取数据库默认值 `'standard'`，避免 NULL
