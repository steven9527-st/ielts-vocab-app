## Context

当前 Excel 同义词导入的数据流：

```
┌────────────────────────────────────────────────────────────────┐
│  现状（单英文列）                                              │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Excel 一行 ────► apply_mapping ────► 一条 entry               │
│                                                                │
│  english_col=B (文章)  →  english="keep sth off"               │
│  chinese_col=D (中文)  →  chinese="保持某事关闭 / 防止某事出现" │
│  synonym_col=-1         →  synonyms="" 或自动复制 chinese      │
│                                                                │
│  问题：C 列「prevent sth from appearing」彻底丢失              │
│  问题：chinese 字段塞了两个词的中文，显示混乱                  │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

需求改造为：

```
┌────────────────────────────────────────────────────────────────┐
│  目标（双英文列展开）                                          │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Excel 一行 ────► apply_mapping ────► 两条 entries             │
│                                                                │
│  english_col   = B → english="keep sth off"                    │
│  english_col_2 = C → english2="prevent sth from appearing"     │
│  chinese_col   = D → 拆分 "保持某事关闭 / 防止某事出现"        │
│                       ├─ 前半 "保持某事关闭" → 给 B 列          │
│                       └─ 后半 "防止某事出现" → 给 C 列          │
│                                                                │
│  输出：                                                        │
│    entry1: english="keep sth off",                             │
│            chinese="保持某事关闭",                             │
│            synonyms="prevent sth from appearing"               │
│    entry2: english="prevent sth from appearing",               │
│            chinese="防止某事出现",                             │
│            synonyms="keep sth off"                             │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

## Goals / Non-Goals

**Goals:**

- 支持「双英文列 + 单中文列」的 Excel 同义词词库导入
- 中文按 `/` 拆分对应到两个英文词
- 列映射 UI 上让用户清晰指定哪两列是英文、哪列是中文
- 既有导入路径（标准模式、单英文列同义词模式）零回归

**Non-Goals:**

- 不支持「三个及以上英文列」（罕见且复杂度跳跃）
- 不支持自定义拆分符（`/` 已覆盖你截图样本中的 100% 情况；如未来需要再加）
- 不修改 PDF 表格导入（pdf_parser.py 路径独立，本次只动 Excel/CSV）
- 不引入「智能猜测哪两列是英文」的 AI 推断（用户手选即可）

## Decisions

### 决策 1：API 形态用「新增可选参数 `english_col_2`」

**选择**：`apply_mapping()` 新增 `english_col_2: int = -1` 参数。`english_col_2 >= 0` 时启用展开逻辑；否则走原路径。

**为什么**：

| 方案 | 优点 | 缺点 |
|---|---|---|
| A. 新参数 `english_col_2` ✅ | 增量、向后兼容；逻辑分支清晰 | 函数签名增加 1 个参数 |
| B. 改 `english_col` 为 `list[int]` | 未来扩展性更好 | 现有调用全部要改；类型不一致；过度设计 |
| C. 写一个新函数 `apply_mapping_paired()` | 完全隔离 | 大量代码重复；调用方要分支选择 |

A 最朴素。

### 决策 2：中文拆分用 `_split_chinese_pair(text)` 工具函数

**选择**：

```python
def _split_chinese_pair(text: str) -> tuple[str, str]:
    """按第一个 / 拆分中文文本为两半。

    Cases:
      "A / B"     → ("A", "B")
      "A/B"       → ("A", "B")           # 无空格也支持
      "A / B / C" → ("A", "B / C")       # 仅取第一个分隔符
      "A"         → ("A", "")            # 无分隔符：全部归前半
      ""          → ("", "")
      None        → ("", "")
    """
```

**为什么**：用第一个 `/` 拆分是简单可预测的策略——95% 的真实数据是恰好两段。少数三段及以上情况，第二段及之后归到第二个词，符合"信息不丢失"原则。

### 决策 3：UI 仅在「同义词模式」激活时显示「英文列 2」下拉

**选择**：模板用 JS 监听 `import_mode` radio 变化，切到 `synonym` 时显示英文列 2 下拉，切回 `standard` 时隐藏并清空。

**为什么**：标准模式（B = 中文释义）下不需要第二英文列；UI 始终可见会让用户困惑。

**默认值**：

- 「英文列 1」默认 = 当前 `guess.english_col`（保持现有体验）
- 「英文列 2」默认 = -1（用户主动选）；如果用户切换到同义词模式但没选第二列，按"单英文列同义词模式"工作（向后兼容）

### 决策 4：每条 Excel 行展开为两条 entries 时的 failed 判定

**选择**：每条 entry 独立判 failed —— `failed = (not english) or (not chinese)`。

**为什么**：考虑到 D 列没有 `/` 的情况（只有 B 列拿到中文，C 列 chinese 为空），这一行展开后会出现：

- entry1：english="keep sth off", chinese="保持某事关闭" → ✓ 不 failed
- entry2：english="prevent sth from appearing", chinese="" → ✗ failed=True

预览页会高亮 failed 项让用户决定，符合既有交互。**用户可在预览页删掉 failed 项**或手动补中文。

### 决策 5：synonym 字段填充

**选择**：

- entry1.synonyms = entry2.english（即 `english_col_2` 的值）
- entry2.synonyms = entry1.english（即 `english_col` 的值）

互为同义词，保持本应用同义词模式的语义对称。

### 决策 6：列名启发式提示（可选 nice-to-have）

**选择**：暂不实现"自动猜哪两列是英文"。用户截图中列名形如 `B: 文章 (英文)` `C: 题目 (英文)`，含"英文"关键词，理论上可猜，但**首版不做**——先把功能跑通，让用户手选。

## Risks / Trade-offs

- **风险 1：中文拆分误伤** → 极少数 D 列文本本身含 `/`（如 "A/B 类型"）会被误拆。缓解：预览页可手动修正；后续可加"用户自定义分隔符"开关
- **风险 2：english 与 english_col_2 重复** → 路由层校验：`english_col == english_col_2` 时返回 400 错误
- **风险 3：english_col_2 等于 chinese_col 等其他列** → 同上校验
- **风险 4：双倍 entry 数量导致预览页卡顿** → 既有预览页已能处理几百行，双倍后仍在合理范围；不优化
- **Trade-off：失去「不指定 english_col_2 时仍用展开逻辑」的智能猜测能力** → 选择"显式优于隐式"，用户必须主动选第二列才触发展开

## Migration Plan

1. 改 `excel_parser.py`：加 `english_col_2` 参数 + 拆分函数 + 展开循环
2. 改 `app.py`：路由接收新参数 + 校验
3. 改 `import_excel_mapping.html`：UI 增「英文列 2」+ JS 切换
4. 加测试：单元 + 端到端
5. 用户现场验证：用截图中那份 C19 词库再导一次，预览应展示双倍行数与拆分中文

无数据迁移；无回滚顾虑（仅导入侧）。

## Open Questions

- 是否需要支持「PDF 表格导入」也走类似双列逻辑？暂不做，PDF 表格目前只见过 2 列结构，遇到再说。
