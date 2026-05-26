## ADDED Requirements

### Requirement: Delete word list
系统 SHALL 提供删除整个词库的能力，删除时自动清理所有关联数据（单词、学习会话），学习记录保留但解除词库关联。

#### Scenario: 成功删除词库
- **WHEN** 用户在词库管理页点击"删除此词库"并确认
- **THEN** 系统删除该词库及其所有单词和进行中的学习会话，返回成功并跳转到首页

#### Scenario: 删除后自动切换词库
- **WHEN** 用户删除了当前选中的词库
- **THEN** 系统清除 session 中的 list_id 并重定向到首页，首页自动选择剩余词库

### Requirement: Display English words in lowercase
系统 SHALL 在所有显示英文单词的界面（翻卡学习、测验题目、错题详情）中以小写形式展示。

#### Scenario: 翻卡学习卡片显示小写
- **WHEN** 用户进入翻卡学习模式
- **THEN** 卡片正面的英文单词以小写显示

#### Scenario: 测验题目显示小写
- **WHEN** 用户进行测验（学习测验或测试模式）
- **THEN** 题目区域的英文单词以小写显示

#### Scenario: 错题详情显示小写
- **WHEN** 测验完成后查看错题列表
- **THEN** 错题中的英文单词以小写显示
