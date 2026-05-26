## ADDED Requirements

### Requirement: PDF 解析完整提取音标和词性
解析器 SHALL 从 PDF 词条行中提取英式音标（phonetic）和词性标记（pos），随 english 和 chinese 一起返回。

#### Scenario: 标准格式词条
- **WHEN** PDF 行为 `1. ABANDON 英[ə'bændən] v. 放弃；遗弃`
- **THEN** 返回 `english="ABANDON"`, `phonetic="[ə'bændən]"`, `pos="v."`, `chinese="放弃；遗弃"`

#### Scenario: 无音标的词条
- **WHEN** PDF 行为 `1. HELLO n. 你好`
- **THEN** phonetic 为空字符串，`pos="n."`, chinese 正常提取

#### Scenario: 解析失败时保留空值
- **WHEN** 正则无法匹配标准格式
- **THEN** phonetic 和 pos 均为空字符串，回退逻辑不变

### Requirement: 数据库存储音标和词性
words 表 SHALL 新增 `phonetic TEXT DEFAULT ''` 和 `pos TEXT DEFAULT ''` 列。

#### Scenario: 导入时写入新字段
- **WHEN** 确认导入含音标/词性的词条
- **THEN** INSERT 语句包含 phonetic 和 pos 字段

#### Scenario: 已有数据兼容
- **WHEN** ALTER TABLE 后查询旧记录
- **THEN** phonetic 和 pos 返回 NULL 或空字符串，前端正常显示

### Requirement: 翻卡展示音标和词性
学习卡片背面 SHALL 在中文释义上方展示音标和词性。

#### Scenario: 有音标词性的单词卡片
- **WHEN** 单词记录包含 phonetic 和 pos
- **THEN** 卡片背面显示：`[音标]` 小字 + 词性标签 + 中文释义

### Requirement: 导入预览支持编辑音标词性
导入预览表 SHALL 展示音标/词性列，用户可手动修改。

#### Scenario: 预览页面显示完整信息
- **WHEN** 解析结果包含音标和词性
- **THEN** 预览表每行额外显示 phonetic 和 pos 列

### Requirement: 词库管理列表展示音标词性
词库管理页的单词列表 SHALL 显示每条单词的音标和词性。

#### Scenario: 查看词库详情
- **WHEN** 进入词库管理页
- **THEN** 单词列表中每个英文下方以灰色小字显示 `[音标] pos.`
