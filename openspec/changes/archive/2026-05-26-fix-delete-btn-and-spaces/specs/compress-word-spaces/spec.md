## ADDED Requirements

### Requirement: 压缩解析英文中的多余空白
PDF 解析器提取英文单词后，系统 SHALL 将连续空白字符（空格、tab 等）压缩为单个空格。

#### Scenario: 正常单次空格不变
- **WHEN** PDF 行为 `1. ABANDON 英[...]`
- **THEN** 解析结果 english 为 `"ABANDON"`（无变化）

#### Scenario: 多余中间空格被压缩
- **WHEN** PDF 行为 `1. GIVE  UP 英[...]`（双空格）
- **THEN** 解析结果 english 为 `"GIVE UP"`（单空格）

#### Scenario: 多词短语保持正常
- **WHEN** PDF 行为 `1. LOOK AFTER 英[...]`
- **THEN** 解析结果 english 为 `"LOOK AFTER"`（保持原样）

#### Scenario: 解析失败的回退提取也压缩
- **WHEN** 正则匹配失败且回退提取到含多余空格的英文
- **THEN** 回退结果同样经过空格压缩
