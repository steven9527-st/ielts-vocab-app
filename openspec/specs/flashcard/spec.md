# Spec: flashcard


## ADDED Requirements

### Requirement: 翻卡反复翻转

学习卡片 SHALL 支持用户在正反面之间反复切换，不限次数。

#### Scenario: 多次点击翻转

- **GIVEN** 用户位于学习卡片页面，卡片处于正面
- **WHEN** 用户点击卡片
- **THEN** 卡片 SHALL 翻转到背面（显示中文释义）
- **AND** 用户再次点击卡片
- **AND** 卡片 SHALL 翻回正面（显示英文 + 音标）
- **AND** 重复上述切换不限次数

#### Scenario: Space 键反复翻转

- **GIVEN** 用户位于学习卡片页面
- **WHEN** 用户按下 Space 键
- **THEN** 卡片 SHALL 切换正反面（与点击效果相同）
- **AND** 多次按 Space SHALL 持续切换

### Requirement: 提示文案随状态切换

卡片正面的提示文案 SHALL 根据当前显示的面动态变化。

#### Scenario: 正面状态

- **GIVEN** 卡片当前显示正面（英文 + 音标）
- **WHEN** 用户查看
- **THEN** 提示区域 SHALL 显示文本 "点击查看释义"

#### Scenario: 背面状态

- **GIVEN** 卡片当前显示背面（中文释义）
- **WHEN** 用户查看
- **THEN** 提示区域 SHALL 显示文本 "点击返回正面"

### Requirement: "下一张"按钮首次出现后常驻

"下一张"按钮 SHALL 在用户首次翻到背面后出现，且之后无论卡片在哪一面，按钮 SHALL 持续可见。

#### Scenario: 首次翻到背面

- **GIVEN** 卡片刚渲染，从未翻过
- **WHEN** 用户首次将卡片翻到背面
- **THEN** "下一张"按钮 SHALL 从隐藏变为可见

#### Scenario: 翻回正面按钮保留

- **GIVEN** 用户已翻到背面，"下一张"按钮已出现
- **WHEN** 用户再次点击卡片翻回正面
- **THEN** "下一张"按钮 SHALL 仍然可见
- **AND** 用户 SHALL 仍可点击"下一张"进入下一题

#### Scenario: 切换到下一题后状态重置

- **GIVEN** 用户在某张卡片上点击"下一张"
- **WHEN** 页面渲染新卡片
- **THEN** "下一张"按钮 SHALL 重新隐藏
- **AND** 卡片 SHALL 重置为正面
- **AND** 提示文案 SHALL 重置为"点击查看释义"

### Requirement: ArrowRight 进入下一题的触发条件

ArrowRight 键 SHALL 在用户曾经翻到过背面后即可触发"下一题"提交，不论卡片当前是正面还是背面。

#### Scenario: 从未翻过

- **GIVEN** 卡片刚渲染，从未翻过
- **WHEN** 用户按 ArrowRight
- **THEN** 系统 SHALL 不响应（强制用户先看一遍释义）

#### Scenario: 翻到背面后按 ArrowRight

- **GIVEN** 用户已将卡片翻到背面
- **WHEN** 用户按 ArrowRight
- **THEN** 系统 SHALL 提交"下一张"表单，进入下一题

#### Scenario: 翻回正面后按 ArrowRight

- **GIVEN** 用户已翻到背面并翻回正面
- **WHEN** 用户按 ArrowRight
- **THEN** 系统 SHALL 提交"下一张"表单（因为用户已翻过）

### Requirement: 发音按钮不触发翻转

卡片上的 🔊 发音按钮 SHALL 不会触发卡片翻转。

#### Scenario: 点击音标旁 🔊 按钮

- **GIVEN** 卡片处于正面，音标右侧有 🔊 按钮
- **WHEN** 用户点击 🔊 按钮
- **THEN** 浏览器 SHALL 播放发音
- **AND** 卡片 SHALL 不翻转（事件冒泡被阻止）
