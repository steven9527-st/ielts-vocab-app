# Spec: import-excel

## Purpose

定义 Excel (.xlsx) 与 CSV (.csv) 词库导入的端到端流程：文件入口分发、多 Sheet 处理、列映射页交互（英文列 / 中文列 / 音标 / 词性 / 同义词 / 双英文列同义词配对）、导入模式开关（标准 / 同义词）、表头识别、映射应用、错误处理。
## Requirements
### Requirement: 多文件格式导入入口

导入页 (`/import`) SHALL 接受 PDF、Excel (.xlsx) 与 CSV (.csv) 三种文件格式，并根据扩展名分发到对应解析器。

#### Scenario: 上传 PDF

- **GIVEN** 用户在 `/import` 页选择一个 `.pdf` 文件
- **WHEN** 提交解析
- **THEN** 后端 SHALL 调用 PDF 解析器并跳转到 `/import/preview` 预览页（保持现有行为）

#### Scenario: 上传 xlsx

- **GIVEN** 用户在 `/import` 页选择一个 `.xlsx` 文件
- **WHEN** 提交解析
- **THEN** 后端 SHALL 调用 Excel 解析器读取第一个 Sheet 所有行
- **AND** 保存到服务端临时文件
- **AND** 返回 `{next: "/import/excel_mapping"}`
- **AND** 浏览器 SHALL 跳转到列映射页

#### Scenario: 上传 CSV

- **GIVEN** 用户上传 `.csv` 文件
- **WHEN** 后端读取
- **THEN** 系统 SHALL 依次尝试 `utf-8-sig`、`utf-8`、`gbk` 三种编码
- **AND** 首个成功解码的编码 SHALL 被采用
- **AND** 后续流程与 xlsx 一致

#### Scenario: 上传不支持的格式

- **GIVEN** 用户尝试上传 `.xls`、`.txt` 或其他非 PDF/xlsx/CSV 格式
- **WHEN** 提交
- **THEN** 前端 `accept` 属性 SHALL 拦截
- **AND** 后端 SHALL 在收到时返回 400 错误 `仅支持 .pdf / .xlsx / .csv 文件`

### Requirement: Excel/CSV 多 Sheet 处理

当上传的 Excel 文件包含多个 Sheet 时，系统 SHALL 仅读取第一个 Sheet。

#### Scenario: 多 Sheet Excel

- **GIVEN** 用户上传一个含 3 个 Sheet 的 `.xlsx` 文件
- **WHEN** 解析
- **THEN** 系统 SHALL 只读取第一个 Sheet 的数据
- **AND** 其他 Sheet SHALL 被静默忽略

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

#### Scenario: 用户手动改变映射

- **GIVEN** 列映射页已渲染
- **WHEN** 用户从下拉菜单中选择不同的列作为英文/中文列
- **THEN** 预览表格 SHALL 高亮显示对应列

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

### Requirement: 列映射页 - 音标与词性自动识别

音标列和词性列 SHALL 通过列名匹配自动识别，用户不可手动指定。

#### Scenario: 命中音标列名

- **GIVEN** 文件首行包含以下任一列名（不区分大小写）：`phonetic`、`phonetics`、`pronunciation`、`ipa`、`音标`、`发音`、`英标`
- **WHEN** 列映射页渲染
- **THEN** 该列 SHALL 被识别为音标列
- **AND** 页面 SHALL 显示提示"✓ 自动识别到音标列：[列名]"

#### Scenario: 命中词性列名

- **GIVEN** 文件首行包含以下任一列名（不区分大小写）：`pos`、`part of speech`、`词性`、`词类`
- **WHEN** 列映射页渲染
- **THEN** 该列 SHALL 被识别为词性列
- **AND** 页面 SHALL 显示提示"✓ 自动识别到词性列：[列名]"

#### Scenario: 无规范音标/词性列名

- **GIVEN** 文件首行无匹配的音标/词性列名
- **WHEN** 列映射页渲染
- **THEN** 音标/词性 SHALL 不被识别
- **AND** 导入后这些字段保持为空
- **AND** 用户无法手动指定（保持 UI 简洁）

### Requirement: 表头识别

列映射页 SHALL 提供"第一行是表头"复选框，并智能预设默认值。

#### Scenario: 智能判定为表头

- **GIVEN** 第一行所有单元格不含中文字符
- **AND** 至少一个单元格匹配常见表头词（word、english、单词等）
- **WHEN** 列映射页加载
- **THEN** "第一行是表头"复选框 SHALL 默认勾选

#### Scenario: 智能判定为数据行

- **GIVEN** 第一行明显是数据（如含中文释义）
- **WHEN** 列映射页加载
- **THEN** "第一行是表头"复选框 SHALL 默认不勾选

#### Scenario: 用户手动调整

- **GIVEN** 用户位于列映射页
- **WHEN** 用户切换"第一行是表头"复选框
- **THEN** 应用映射时 SHALL 根据用户最终选择决定是否跳过第一行

### Requirement: 应用映射并进入预览

用户在列映射页确认后，系统 SHALL 将原始行转换为标准 entries 结构，并跳到与 PDF 共用的预览校对页。

#### Scenario: 用户点击"继续"

- **GIVEN** 用户已在列映射页选定英文/中文列
- **WHEN** 用户点击"继续"按钮
- **THEN** 前端 SHALL 调用 `POST /import/excel_apply`，携带 `english_col`、`chinese_col`、`skip_first_row` 参数
- **AND** 后端 SHALL 转换为 `[{english, chinese, phonetic, pos, failed}]` 结构
- **AND** 保存到服务端临时文件
- **AND** 清理 Excel raw 临时文件
- **AND** 返回 `{next: "/import/preview"}`
- **AND** 浏览器 SHALL 跳转到预览页

#### Scenario: 转换为标准 entries

- **GIVEN** 用户选择英文列=0、中文列=1、音标列=2（已自动识别）、词性列=-1（未识别）、skip_first_row=true
- **AND** 原始数据有 100 行（含表头）
- **WHEN** 应用映射
- **THEN** 系统 SHALL 跳过第 1 行
- **AND** 输出 99 条 entries
- **AND** 每条 entries 的 `phonetic` 字段 SHALL 来自第 2 列，`pos` 字段 SHALL 为空字符串
- **AND** `failed` 字段 SHALL 在英文或中文为空时设为 true

#### Scenario: 英文或中文为空的行

- **GIVEN** 某一行的英文列或中文列单元格为空
- **WHEN** 转换为 entries
- **THEN** 该行 entries 的 `failed` 字段 SHALL 为 true（用户可在预览校对页手动补全或删除）

### Requirement: 错误处理

Excel/CSV 解析过程中的所有错误 SHALL 返回 4xx 状态码与中文错误信息，不出现 5xx。

#### Scenario: 空文件或空 Sheet

- **GIVEN** 用户上传一个空的或只有空白行的 Excel/CSV
- **WHEN** 后端解析
- **THEN** 系统 SHALL 返回 400 错误 `文件中未读到任何数据`

#### Scenario: CSV 编码无法识别

- **GIVEN** 用户上传一个非 UTF-8 / UTF-8-BOM / GBK 编码的 CSV
- **WHEN** 后端尝试解码
- **THEN** 系统 SHALL 返回 400 错误 `CSV 文件编码无法识别，请用 UTF-8 保存`

#### Scenario: Excel 文件损坏

- **GIVEN** 用户上传一个损坏或非真实 xlsx 的文件
- **WHEN** openpyxl 抛异常
- **THEN** 系统 SHALL 捕获并返回 400 错误 `Excel 文件解析失败：[原因]`

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

