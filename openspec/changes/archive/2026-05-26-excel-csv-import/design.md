# 设计文档

## Context

当前 `/import/parse` 强绑定 PDF 解析（`pdf_parser.parse_pdf()`）。Excel/CSV 数据结构化程度远高于 PDF，不需要正则；但列结构在用户来源不固定（"网上下载"），必须有一个轻量的"列映射"步骤。

下游流程（服务端临时文件 `_save_parse_result` + 预览校对 + `/import/confirm`）与文件类型无关，只要解析器输出统一结构 `[{english, chinese, phonetic, pos, failed}]` 即可完全复用。

## Goals / Non-Goals

### Goals
- Excel / CSV 导入与 PDF 导入并存，统一入口
- 列映射步骤简洁（仅 2 个必选下拉 + 音标/词性自动识别）
- 解析阶段不允许出现 5xx 错误（坏文件 → 友好提示）

### Non-Goals
- 不做"追加到现有词库"
- 不支持 .xls 老格式
- 不做模板下载
- 不读多 Sheet
- 不做 5 列全字段映射 UI

## Key Decisions

### Decision 1: 文件类型分发

**决定**：在 `/import/parse` 中按扩展名分发到不同解析器，前端 `accept` 属性限制可上传类型。

```python
ext = os.path.splitext(f.filename)[1].lower()
if ext == '.pdf':
    entries = parse_pdf(tmp_path)
    # 走原有流程，直接跳预览页
elif ext in ('.xlsx', '.csv'):
    raw_rows, headers = parse_table_raw(tmp_path)
    # 存到服务端临时文件，跳到列映射页
    token = _save_excel_raw({'rows': raw_rows, 'headers': headers, 'filename': f.filename})
    session['excel_raw_token'] = token
    return jsonify({'next': '/import/excel_mapping'})
```

**为什么不让前端一次性提交映射**：用户需要看到预览数据才能正确选列。所以解析必须分两步：(1) 读取所有行 → (2) 用户确认列 → (3) 转换为 entries。

### Decision 2: 解析器接口

`excel_parser.py` 暴露两个函数：

```python
def parse_table_raw(filepath: str) -> tuple[list[list[str]], list[str]]:
    """读取文件全部行，返回 (rows, headers_guess)
    headers_guess: 第一行（无论是否真为表头）
    rows: 包含所有行（包括第一行），由前端决定是否跳过
    """

def apply_mapping(rows: list[list[str]],
                  english_col: int,
                  chinese_col: int,
                  phonetic_col: int = -1,
                  pos_col: int = -1,
                  skip_first_row: bool = True) -> list[dict]:
    """根据列映射转换为 entries 标准格式"""
```

**xlsx 用 openpyxl**：`load_workbook(filepath, read_only=True, data_only=True)` → 第一个 sheet → `iter_rows(values_only=True)`。
**csv 用标准库**：尝试 `utf-8` → 失败回退 `gbk`（中文 Excel 导出常见）→ 再失败回退 `utf-8-sig` (带 BOM)。

### Decision 3: 音标 / 词性列的自动识别

**决定**：在列映射页加载时，扫描第一行（假定为表头）的每个单元格，按字典匹配：

```python
PHONETIC_HEADERS = {'phonetic', 'phonetics', 'pronunciation', 'ipa',
                    '音标', '发音', '英标'}
POS_HEADERS = {'pos', 'part of speech', 'partofspeech',
               '词性', '词类'}
```

- 命中 → 该列预选为音标/词性列
- 未命中 → 该列设为"无"，用户也无法手动指定（设计简化，符合方案 ①）

如果用户的 Excel 没有规范列名，那音标/词性就是空——不影响核心功能。

### Decision 4: "第一行是表头" 启发式判定

**默认勾选规则**：

```python
def looks_like_header(first_row: list[str]) -> bool:
    """第一行像表头的特征：
    1. 所有单元格都不含中文字符
    2. 至少有一个单元格匹配常见表头词（word, english, 单词等）
    3. 单元格内容长度普遍较短（<= 30 字符）
    """
```

用户在 UI 上可手动改这个勾选。

### Decision 5: 英文列 / 中文列的智能预选

**决定**：进入映射页时，根据列名+内容启发式预选：

1. **英文列优先级**：列名匹配 `word / english / 单词 / 英文` > 全列内容大多为 ASCII 字符
2. **中文列优先级**：列名匹配 `meaning / chinese / 释义 / 中文 / 解释` > 全列内容大多含中文字符

预选可能错误，用户可改。

### Decision 6: CSV 编码处理

**决定**：依次尝试 `utf-8-sig` → `utf-8` → `gbk`，第一个不报 `UnicodeDecodeError` 即用。

```python
ENCODINGS = ['utf-8-sig', 'utf-8', 'gbk']
for enc in ENCODINGS:
    try:
        with open(filepath, 'r', encoding=enc, newline='') as f:
            rows = list(csv.reader(f))
        return rows
    except UnicodeDecodeError:
        continue
raise RuntimeError("CSV 文件编码无法识别，请用 UTF-8 保存")
```

### Decision 7: 流程图

```
[用户上传 file]
       │
       ▼
  /import/parse
       │
   ┌───┴────┐
   ▼        ▼
 PDF      Excel/CSV
   │        │
   │        ▼
   │   parse_table_raw()
   │        │
   │        ▼
   │   保存 rows 到 _excel_raw_TOKEN.json
   │   返回 next='/import/excel_mapping'
   │        │
   │        ▼
   │   /import/excel_mapping (GET)
   │   渲染列映射 UI（含预选、预览前 5 行）
   │        │
   │        ▼
   │   /import/excel_apply (POST {english_col, chinese_col, skip_first_row})
   │   调 apply_mapping() 转 entries
   │   存到 _parse_TOKEN.json（与 PDF 流程同一格式）
   │        │
   │        ▼
   └────► /import/preview （PDF & Excel 共用，无改动）
              │
              ▼
        /import/confirm （无改动）
```

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| CSV 编码识别失败 | 三种编码 fallback，仍失败则给明确错误信息 |
| 用户上传空 Sheet 或全是合并单元格 | parse_table_raw 返回空 rows → 友好提示"未读到数据" |
| openpyxl 内存占用（大文件） | `read_only=True` 模式流式读取；预期词表通常 < 5000 行 |
| 用户选错列（例如把音标当英文）→ 数据库进了垃圾 | 预览校对页可逐行编辑；用户也可在词库管理删除 |
| xls 老格式被误传 | 前端 accept 限制 + 后端文件名后缀检查双重防护 |

## Migration Plan

无数据库迁移。一次性发布即可：
- 用户原有 PDF 导入流程完全不受影响
- 新增 Excel/CSV 导入入口在同一 `/import` 页
- 部署需 `pip install -r requirements.txt`（添加 openpyxl）

## Open Questions

无。所有决策已对齐。
