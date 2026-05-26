# import-excel Specification

## ADDED Requirements

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

Excel/CSV 列映射页 SHALL 要求用户指定英文列和中文列，并提供智能预选。

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

#### Scenario: 用户手动改变映射

- **GIVEN** 列映射页已渲染
- **WHEN** 用户从下拉菜单中选择不同的列作为英文/中文列
- **THEN** 预览表格 SHALL 高亮显示对应列

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
