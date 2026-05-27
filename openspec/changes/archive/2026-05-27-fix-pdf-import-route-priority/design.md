## Context

`add-pdf-table-import` 的双路径分发设计当时是基于这样的假设：
- 编号词表 PDF 通常**没有表格线** → `extract_tables()` 自然返回空 → 自动 fallback 到 `_ENTRY_RE`
- 双列同义词词库 PDF **有表格线** → `extract_tables()` 命中 → 走表格路径

实际接触真实样本后这个假设崩了：**雅思教材类编号词表 PDF 普遍带表格线**（为了美化排版），导致 `extract_tables()` 命中，"截胡"了本该归 `_ENTRY_RE` 处理的 PDF。

用「雅思阅读高分词汇.pdf」实测对比两条路径的输出质量：

```
表格路径输出：
  ['1.', 'aback', "英 [ə'bæk]\n美 [ə'bæk]", 'adv. (对某事）大吃一惊\nbe taken aback']
   ↑                ↑                          ↑
   序号             整列塞 phonetic              整列塞 chinese（含换行/英文例句）

_ENTRY_RE 路径输出：
  {english: 'aback', phonetic: "ə'bæk", pos: 'adv.', chinese: 'adv. (对某事）大吃一惊'}
              ↑                ↑               ↑          ↑
              干净             去标记            提取出   结构化
```

两个修复点必须同时做，否则任何一条 fallback 仍可能踩坑。

## Goals / Non-Goals

**Goals:**
- 让编号词表 PDF（无论是否带表格线）都走 `_ENTRY_RE` 路径，获得结构化字段
- 表格 PDF（如双列同义词词库）保留走表格路径的能力
- 修复后 Mac/Win 两端表现完全一致——同一份 PDF 同样的结果
- 现有 add-pdf-table-import 的 e2e 测试继续通过（同义词模式不能被破坏）

**Non-Goals:**
- 不重构 `pdf_parser.py` 内部结构（`_ENTRY_RE` 主流程保持不变）
- 不调整 `pdfplumber` 表格抽取参数（成本不可控）
- 不提供"用户手动选 PDF 类型"的 UI 兜底（双路径自动判断应当够用）
- 不修复 Windows 上 pdfplumber 表格抽取的列数抖动问题（绕开它而非修它）

## Decisions

### D1：分发顺序——编号词表优先

**决策**：上传 PDF 后按以下顺序尝试：

```
                 文字层探测（不变）
                       │
                       ▼
              先跑 parse_pdf (_ENTRY_RE)
                       │
              ┌────────┴─────────┐
              ▼                  ▼
        命中率 ≥ 30%         命中率 < 30%
        采用 entries          尝试 extract_pdf_tables
              │                  │
              │           ┌──────┴──────┐
              │           ▼             ▼
              │      抽到表格        没抽到
              │      走表格路径      返回原 _ENTRY_RE
              │                       结果（即使少）
              ▼
        跳预览页
```

**为什么"命中率 30%"作为阈值**：
- 真编号词表（如雅思 3500）`_ENTRY_RE` 命中率 ≈ 74-99%
- 真表格 PDF（如同义词词库）`_ENTRY_RE` 命中率 ≈ 0%
- 30% 是两者中间的安全分界——绝不会有"30% 编号 + 70% 表格混排"的真实 PDF
- 设得更低（如 10%）会让"偶尔几行像编号词表"的杂表格走错路径

**为什么不简单 ">0 就用"**：
- 偶尔扫描提取出来会有几行"伪命中"（误把页码、章节号当成编号）
- 30% 是经验值，宁可严格

### D2：`guess_columns` 加固——序号列不能当英文列

**决策**：在英文列候选评分阶段，加入"列内容是否像英文单词"的过滤：

```python
def _looks_like_word_column(col_cells: list[str]) -> bool:
    """判断一列是否「主要由英文单词构成」。

    规则：
      • 至少 50% 非空 cell 含有 ≥2 字母连续的字母串
      • 排除"全数字+标点"的列（如序号列 "1." / "2." / "1000."）
    """
```

集成到 `guess_columns`：英文列候选必须先通过 `_looks_like_word_column` 才进入 ASCII 占比排序。

**为什么"≥2 字母连续"而不是"≥3"**：
- 部分缩写（如 `ID`、`AI`）虽然只有 2 字母仍是有效英文
- 序号列 `"1."` 只含 1 个数字字符，必然不通过

**保护机制**：若过滤后没有任何列通过，回退到原有"ASCII 占比最高"规则（保证向后兼容，不破坏现有 e2e 测试中的同义词词库样本）

### D3：表格路径的"命中率"统计

**决策**：`parse_pdf` 当前总是返回 entries 列表，但没暴露"命中率"概念。`/import/parse` 路由层需要计算：

```
命中率 = 非 failed entries 数 / max(entries 总数, PDF 估算总词条数)
```

**实现方式**：在分发路由层做计算，不改 `parse_pdf` 内部接口。逻辑：

```python
entries = parse_pdf(tmp_path)
total = len(entries)
hit = sum(1 for e in entries if not e.get('failed'))
hit_rate = hit / total if total > 0 else 0
if hit_rate >= 0.3 and total >= 5:
    # 走老路径
else:
    # 尝试表格路径
```

**`total >= 5` 的小门槛**：避免极小 PDF（只有几行）因为基数太小让 30% 失真。

### D4：保留表格路径作为完整 fallback

**决策**：分发顺序变化后，表格路径**不删除**，作为 `_ENTRY_RE` 命中率不足时的 fallback：

```
情况 1：编号词表 PDF（如雅思 3500）
   → _ENTRY_RE 命中率 99% → 直接采用 ✓

情况 2：双列同义词词库 PDF（如 C4-Test1）
   → _ENTRY_RE 命中率 0%（无编号格式）
   → fallback 到 extract_pdf_tables ✓

情况 3：完全非词表 PDF（如普通文档）
   → _ENTRY_RE 命中率 0%
   → extract_pdf_tables 也返回 None
   → 返回原 _ENTRY_RE 的空 entries，预览页空白让用户决定
```

之前 add-pdf-table-import 的 e2e 测试用 fixture PDF 没有编号格式 → 走 fallback 到表格路径 → 测试结果不变 ✓

### D5：不引入"用户手动覆盖"

**决策**：双路径自动判断后**不在 UI 上加"我这是什么 PDF"的选择**。

**理由**：
- 当前自动判断准确率应该接近 100%（编号率 30% 是非常分明的门槛）
- 增加 UI 步骤会增加用户认知负担
- 万一未来发现还有边界 case，再补这个 UI 也来得及（不阻塞当前修复）

## Risks / Trade-offs

**[R1] 30% 阈值经验值过严或过宽**
- 过严（如设 60%）：质量较差的扫描 PDF 可能错过老路径
- 过宽（如设 10%）：偶尔几行伪命中的表格 PDF 错走老路径
- → Mitigation：30% 是平衡选择；用户提供的样本 PDF（74%-99%）和已知表格 PDF（0%）之间留出宽容区间；如果未来发现 case 可微调

**[R2] `_looks_like_word_column` 误杀同义词词库**
- 同义词词库的释义列（如 `plight` / `classroom`）都是合法英文单词，必然通过
- 序号列被过滤掉
- → 不会误杀

**[R3] `parse_pdf` 性能：现在总是先跑一遍**
- 144 页 PDF 跑 `parse_pdf` 约 1-2 秒（Mac 实测）
- 加上表格路径 fallback 最坏情况 ≈ 双倍时间
- → 用户已经在等待"上传解析"，2-4 秒可接受

**[R4] Windows 上已经被错误导入的词库怎么办**
- 数据库里有 1911 条错位数据
- → 修复后用户手动「删除此词库」+ 重新导入即可
- → 在 README 或本次构建的发布说明里写清

**[R5] 修复后 Mac 用户重新导入会不会冲突？**
- Mac 用户旧数据是 5/26 用老版导入的 1410 条正确数据
- 新版导入会因 UNIQUE(list_id, english) 约束触发"已存在"
- → 用户重新导入会创建**新词库**（不同 list_id），不影响旧数据
- → 旧词库可以保留或手动删除

## Migration Plan

1. 实施 D1 + D2 + D3 代码改动
2. 写单测复现"序号列被误选为英文列"的 bug 并验证修复
3. 跑全部既有测试（11 + 2 = 13 个）确保零回归
4. 跑用户样本 PDF 端到端实测：
   - 输入：`雅思阅读高分词汇.pdf`
   - 期望：english 列是 `aback` / `abate` / `abnormal`，不是 `1.` / `2.`
5. 重新打包 Mac App（`bash build_mac.sh`）
6. Windows 在虚拟机重新打包（`build_win.bat`）
7. Windows 用户：删错误词库 → 用新版导入
