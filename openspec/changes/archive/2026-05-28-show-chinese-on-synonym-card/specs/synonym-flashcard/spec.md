## ADDED Requirements

### Requirement: 同义词卡片正面显示中文释义

同义词翻卡（`flashcard_synonym.html`）的正面 SHALL 在英文/音标下方根据 `word.chinese` 字段是否非空，条件渲染一行中文释义。中文释义的视觉地位是「配角」——字号小于英文主体、灰色，作为提示性存在，不喧宾夺主。

#### Scenario: 词条有中文释义

- **GIVEN** 用户进入同义词翻卡页面
- **AND** 当前展示的词条 `word.chinese` 字段非空（如 `"令人警觉的损失速度"`）
- **WHEN** 卡片正面渲染
- **THEN** 系统 SHALL 在音标行下方插入一行中文文本
- **AND** 该行 SHALL 应用 `.synonym-front-chinese` class
- **AND** 字号 SHALL 为 14px、颜色 SHALL 为 `var(--clr-text-muted)`、居中对齐
- **AND** 该行 SHALL 位于 `.flashcard__hint`（"点击查看同义词"提示）之上

#### Scenario: 词条无中文释义

- **GIVEN** 当前词条 `word.chinese` 字段为空字符串或仅含空白字符
- **WHEN** 卡片正面渲染
- **THEN** 系统 SHALL 不渲染中文释义行
- **AND** 正面布局 SHALL 与改造前完全一致（英文 → 音标+🔊 → 提示文字）

#### Scenario: 多义项中文释义

- **GIVEN** 词条 `word.chinese` 字段含多个义项，以 ` | ` 分隔（如 `"减轻 | 失效"`）
- **WHEN** 卡片正面渲染
- **THEN** 系统 SHALL 按 ` | ` 切分并逐行展示每个义项
- **AND** 每个义项 SHALL 独立成行，应用相同 `.synonym-front-chinese` 样式

### Requirement: SYNONYMS 列表内中英文项视觉区分

同义词卡片背面 `SYNONYMS` 列表 SHALL 自动检测每个项是否包含 CJK 字符（Unicode 范围 `U+4E00` 到 `U+9FFF`），含 CJK 字符的项以「灰色配角」样式呈现，纯英文项以「黑色主角」样式呈现。

#### Scenario: 同义词列表全为英文

- **GIVEN** 词条 `word.synonyms = "plight, catastrophe, distress"`
- **WHEN** 卡片背面渲染
- **THEN** 三个同义词 SHALL 全部以默认黑色 24px 加粗（`font-weight: 500`）样式展示
- **AND** 不应用 `.synonym-syn--cn` class

#### Scenario: 同义词列表含中文项

- **GIVEN** 词条 `word.synonyms = "plight, 折磨, catastrophe"`
- **WHEN** 卡片背面渲染
- **THEN** `plight` 与 `catastrophe` SHALL 保持默认黑色加粗样式
- **AND** `折磨` SHALL 应用 `.synonym-syn--cn` class，颜色 SHALL 改为 `var(--clr-text-muted)`、字重 SHALL 改为 400
- **AND** 三项 SHALL 保持相同字号（24px）与位置对齐，不破坏列表布局

#### Scenario: 中英混合项

- **GIVEN** 同义词列表中某项形如 `"plight 折磨"`（中英混排在同一项）
- **WHEN** 卡片背面渲染
- **THEN** 由于该项含 CJK 字符，整项 SHALL 应用 `.synonym-syn--cn` class（灰色）
- **AND** 不再做更细粒度拆分

### Requirement: 背面已有中文释义块保持不变

为保证既有用户体验稳定，同义词卡片背面**底部**已存在的中文释义块（13px 灰色，与 SYNONYMS 列表用横线分隔）的位置、字号、颜色、容器布局 SHALL 维持现状不变。

#### Scenario: 背面底部中文块不动

- **GIVEN** 词条 `word.chinese` 非空
- **WHEN** 卡片背面渲染
- **THEN** 背面 SHALL 同时显示：
  - 顶部 SYNONYMS 列表（含中英区分样式）
  - 中部分隔线（`border-top: 1px solid var(--clr-border)`）
  - 底部中文释义（13px、灰色、与既有版本完全一致）

### Requirement: CJK 字符检测能力

应用 SHALL 提供一个 Jinja 模板可用的 `has_cjk` 测试函数，用于判断字符串是否包含中日韩统一表意文字（CJK Unified Ideographs，`U+4E00` 到 `U+9FFF`）。

#### Scenario: 注册为 Jinja test

- **GIVEN** Flask 应用启动
- **WHEN** Jinja 环境初始化完成
- **THEN** 模板内 SHALL 可用 `{% if some_string is has_cjk %}` 形式调用该测试

#### Scenario: 含 CJK 字符返回 true

- **GIVEN** 输入字符串 `"plight 折磨"`、`"中文"`、`"折磨"`、`"a折b"` 任一
- **WHEN** 调用 `has_cjk(s)`
- **THEN** SHALL 返回 `True`

#### Scenario: 纯非中文字符返回 false

- **GIVEN** 输入字符串 `"plight"`、`""`、`"   "`、`"abc, def"`、`"123 + 456"` 任一
- **WHEN** 调用 `has_cjk(s)`
- **THEN** SHALL 返回 `False`
