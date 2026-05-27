## MODIFIED Requirements

### Requirement: 列映射页 - 英文与中文列选择

Excel/CSV 列映射页 SHALL 要求用户指定英文列和中文列，并提供智能预选。当所有列的中文字符占比都低于阈值时，系统 SHALL 退化为按"非英文列"挑选释义列，以兼容英文-英文对照的同义词词库。

#### Scenario: 智能预选英文列

- **GIVEN** 上传的文件首行包含 "Word"、"English"、"单词" 或 "英文" 之一的列名
- **WHEN** 列映射页加载
- **THEN** 该列 SHALL 被预选为英文列

#### Scenario: 智能预选中文列

- **GIVEN** 上传的文件首行包含 "Meaning"、"Chinese"、"释义"、"中文" 或 "解释" 之一的列名
- **WHEN** 列映射页加载
- **THEN** 该列 SHALL 被预选为中文列

#### Scenario: 无规范列名时按内容预选

- **GIVEN** 文件首行不含规范列名
- **WHEN** 列映射页加载
- **THEN** 系统 SHALL 扫描各列前 5 行的内容
- **AND** 主要为 ASCII 字符的列 SHALL 被预选为英文列
- **AND** 主要含中文字符的列 SHALL 被预选为中文列

#### Scenario: 英文-英文对照表格的退化预选

- **GIVEN** 所有列的中文字符占比都 < 0.2
- **AND** 至少有两列的 ASCII 占比 > 0.5（典型同义词词库形态）
- **WHEN** 列映射页加载
- **THEN** 系统 SHALL 选 ASCII 占比最高的列作为英文列
- **AND** 系统 SHALL 选剩余列中 ASCII 占比次高的列作为释义/中文列
- **AND** `chinese_col` SHALL 不再返回 -1

#### Scenario: 用户手动改变映射

- **GIVEN** 列映射页已渲染
- **WHEN** 用户从下拉菜单中选择不同的列作为英文/中文列
- **THEN** 预览表格 SHALL 高亮显示对应列

## ADDED Requirements

### Requirement: 列映射页 - 导入模式开关

列映射页 SHALL 提供「导入模式」单选，控制释义列内容写入数据库的字段策略。

#### Scenario: 标准模式

- **GIVEN** 用户在列映射页选择「标准模式」
- **WHEN** 应用映射
- **THEN** 释义列内容 SHALL 仅写入 `chinese` 字段
- **AND** `synonyms` 字段 SHALL 保持为空（除非另有同义词列）

#### Scenario: 同义词模式

- **GIVEN** 用户在列映射页选择「同义词模式」
- **WHEN** 应用映射
- **THEN** 释义列内容 SHALL 同时写入 `chinese` 和 `synonyms` 两个字段
- **AND** 导入完成后该词库的所有词条 SHALL 立即可用于同义词学习模式
- **AND** 翻卡学习与 4 选 1 测试 SHALL 仍可正常工作（因 `chinese` 已填充）

#### Scenario: 智能默认模式

- **GIVEN** 释义列的中文字符占比 < 10%
- **WHEN** 列映射页加载
- **THEN** 「同义词模式」单选 SHALL 默认选中

#### Scenario: 智能默认为标准模式

- **GIVEN** 释义列的中文字符占比 ≥ 10%
- **WHEN** 列映射页加载
- **THEN** 「标准模式」单选 SHALL 默认选中

#### Scenario: 用户手动切换模式

- **GIVEN** 列映射页已渲染
- **WHEN** 用户切换导入模式单选
- **THEN** 选中状态 SHALL 在提交时随 `import_mode` 参数发送给后端
- **AND** 后端 SHALL 使用用户最终选择的模式应用映射
