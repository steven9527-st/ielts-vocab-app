## MODIFIED Requirements

### Requirement: 列映射页 - 英文与中文列选择

Excel/CSV 列映射页 SHALL 要求用户指定英文列和中文列，并提供智能预选。当所有列的中文字符占比都低于阈值时，系统 SHALL 退化为按"非英文列"挑选释义列，以兼容英文-英文对照的同义词词库。英文列识别 SHALL 加入"列内容必须像英文单词"的过滤，避免误选纯数字+标点的序号列。

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

#### Scenario: 排除序号列（重点修复场景）

- **GIVEN** 上传的文件含有一列纯序号（如 `"1."` / `"2."` / `"1000."`）
- **AND** 该序号列的 ASCII 占比 = 100%
- **WHEN** 列映射页加载并执行英文列识别
- **THEN** 序号列 SHALL 不被选为英文列
- **AND** 系统 SHALL 从"内容像英文单词"的候选列中选择英文列
- **AND** "像英文单词"判定为：至少 50% 非空 cell 含有 ≥2 字母的连续字母串

#### Scenario: 所有候选列都不像英文单词（兜底）

- **GIVEN** 所有列都被 `_looks_like_word_column` 判定为不像英文单词
- **WHEN** 列映射页加载
- **THEN** 系统 SHALL 回退到原有"ASCII 占比最高"的规则
- **AND** 不破坏既有的同义词词库样本识别行为

#### Scenario: 用户手动改变映射

- **GIVEN** 列映射页已渲染
- **WHEN** 用户从下拉菜单中选择不同的列作为英文/中文列
- **THEN** 预览表格 SHALL 高亮显示对应列
