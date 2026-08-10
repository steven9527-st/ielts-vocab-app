## ADDED Requirements

### Requirement: 默写词库类型定义

`word_lists.type` 字段 SHALL 支持 `'dictation'` 作为合法类型值，标识默写词库。默写词库的词条结构与标准词库相同（`english`、`chinese`、`phonetic`、`pos`、`synonyms`），但学习模式为"看中文默写英文"。

#### Scenario: 默写词库类型识别

- **GIVEN** 词库的 `word_lists.type` 为 `'dictation'`
- **WHEN** 调用 `_get_list_type(list_id)`
- **THEN** 返回 `'dictation'`
- **AND** 该词库在首页 stats、词库管理页正常展示

#### Scenario: 词库类型白名单校验

- **GIVEN** 系统词库类型白名单为 `('standard', 'synonym', 'dictation')`
- **WHEN** `_get_list_type(list_id)` 读取到的 type 不在白名单中
- **THEN** SHALL 返回 `'standard'` 兜底

### Requirement: 导入时选择默写词库类型

Excel/CSV 导入流程的列映射页 SHALL 提供"默写词库"导入选项，与"标准词库"、"同义词词库"并列。选择后 `word_lists.type` 设为 `'dictation'`。

#### Scenario: 用户选择默写词库导入

- **GIVEN** 用户在 `/import/excel_mapping` 页面
- **WHEN** 用户选择"默写词库"导入模式
- **AND** 完成列映射并提交
- **THEN** `import_confirm` SHALL 创建词库时设置 `type='dictation'`
- **AND** 新词库自动设为当前词库

#### Scenario: 默写词库选项展示

- **GIVEN** 用户在 `/import/excel_mapping` 页面
- **WHEN** 页面渲染导入模式选择区域
- **THEN** SHALL 显示三个选项：标准词库、同义词词库、默写词库
- **AND** 默认选中"标准词库"
