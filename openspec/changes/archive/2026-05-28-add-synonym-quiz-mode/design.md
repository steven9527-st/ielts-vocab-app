## Context

当前测验出题逻辑（`app.py` 中 `generate_quiz_questions()`）：

```
┌──────────────────────────────────────────────────────────────────┐
│  现状（一刀切：英文词 → 4 个中文释义）                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  for wid in word_ids:                                            │
│      correct = words[wid]                                        │
│      others = random.sample(其他词, 3)                           │
│      options = [correct.chinese] + [w.chinese for w in others]   │
│      questions.append({                                          │
│          'word_id': wid,                                         │
│          'english': correct.english,                             │
│          'correct': correct.chinese,                             │
│          'options': options,                                     │
│      })                                                          │
│                                                                  │
│  → 同义词词库下：题目 plight，选项是 4 个半段中文，体验糟糕      │
└──────────────────────────────────────────────────────────────────┘
```

需求按词库 type 分支：

```
┌──────────────────────────────────────────────────────────────────┐
│  改造后（按 list.type 决定出题方式）                            │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  if list.type == 'synonym':                                      │
│      正确答案 = correct.synonyms     (英文同义词)                │
│      干扰项 = random.sample(其他词的 synonyms, 3)               │
│      → 选项 4 个均为英文同义词，符合配对学习语义                │
│  else:                                                           │
│      → 走原中文选项逻辑                                         │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## Goals / Non-Goals

**Goals:**

- 同义词词库下测验自动用英文同义词作为选项
- 通过持久化的 `word_lists.type` 字段精确判断"是不是同义词词库"
- 旧用户的既有词库通过 lazy 迁移合理打标签（不需要重新导入）
- 听力测试豁免（保持原中文选项体验）

**Non-Goals:**

- 不做"用户在词库管理页修改 type"功能（首版导入时定）
- 不做"按词决定每道题用哪种选项"的混合策略（一刀切）
- 不动错题循环、回退改答案、卡片渲染等任何无关逻辑
- 不修改 PDF 表格导入相关的 type 写入（PDF 表格也走类似逻辑，但本 change 只动 Excel；PDF 路径放下个 change）

## Decisions

### 决策 1：词库 type 字段而非"全局开关"

**选择**：在 `word_lists` 表加 `type` 列（`'standard'` / `'synonym'`），导入时写入；不引入"用户在测验设置页选模式"的开关。

**为什么**：

| 方案 | 优点 | 缺点 |
|---|---|---|
| A. 词库表 type 字段 ✅ | 持久化、确定、自动 | 需要 schema 迁移 |
| B. 测验时按 synonyms 填充率动态判断 | 不改 schema | 同一词库可能边界飘忽（删几个词后比例变化）；性能浪费（每次出题都要全表扫） |
| C. 测验设置页加"测验模式"下拉 | 灵活 | 用户每次都要选；不符合"按你想的来"的原则 |

A 是数据驱动、最自然的方案。

### 决策 2：旧词库 lazy 自动迁移

**选择**：`init_db()` 内执行一次性扫描——对所有 `type` 为默认值（或 NULL）的词库，统计 synonyms 字段填充率，≥ 80% 标 `'synonym'`，否则保持 `'standard'`。

**为什么**：

- 用户已有词库不强制重新导入
- 80% 阈值经验上可靠（同义词词库导入后填充率应接近 100%；标准词库填充率应接近 0%；中间灰色地带极少）
- 首次启动后已迁移则后续启动无开销（`type` 已经显式设置）

**实现细节**：

```python
def _migrate_word_list_types(conn):
    """将既有 word_lists 按 synonyms 填充率自动分类（仅对未明确设置 type 的词库）"""
    cursor = conn.execute("SELECT id FROM word_lists WHERE type IS NULL OR type = 'standard'")
    for (list_id,) in cursor.fetchall():
        total = conn.execute("SELECT COUNT(*) FROM words WHERE list_id=?", (list_id,)).fetchone()[0]
        if total == 0:
            continue
        with_syn = conn.execute(
            "SELECT COUNT(*) FROM words WHERE list_id=? AND synonyms IS NOT NULL AND synonyms != ''",
            (list_id,)
        ).fetchone()[0]
        if with_syn / total >= 0.8:
            conn.execute("UPDATE word_lists SET type='synonym' WHERE id=?", (list_id,))
```

**注意**：仅对 `type IS NULL OR type = 'standard'` 的词库执行迁移——已显式标 `synonym` 的不动。新导入的词库由路由直接写入正确 type，不走迁移路径。

### 决策 3：干扰项采集策略

**选择**：从同词库其他词的 `synonyms` 字段中随机抽 3 个，去重，去除与正确答案语义重复的项。

**伪代码**：

```python
def _generate_synonym_quiz_question(correct_word, other_words):
    correct_syn = correct_word.synonyms or correct_word.chinese  # 兜底
    pool = [w.synonyms for w in other_words if w.synonyms and w.synonyms != correct_syn]
    distractors = random.sample(pool, min(3, len(pool)))
    options = [correct_syn] + distractors
    random.shuffle(options)
    return {
        'word_id': correct_word.id,
        'english': correct_word.english,
        'correct': correct_syn,
        'options': options,
    }
```

**边界**：

- pool 不足 3 个 → 降级用中文释义补齐（甚至降级整库改回中文选项 + 警告）
- 某词 `synonyms` 为空 → 跳过该题（不出现在题目集中）；学习测验场景由 learn 流程保证全有 synonyms

### 决策 4：听力测试豁免

**选择**：听力测试（`question_type='audio'`）即使在同义词词库下，仍走原中文选项逻辑。

**为什么**：

- 听力测试的设计语义是"听英文 → 选中文释义"，是一种翻译练习
- 听到 `keep sth off` 然后从 `prevent sth from appearing / frequent exposure / 折磨 / understand` 这样的英文同义词中选——音频与选项割裂，体验更差
- 声音输出仅一次，干扰大；中文选项至少给视觉锚点
- 用户明确说"听力测试不用改"

**实现**：在 `generate_quiz_questions` 调用方传入 `mode='audio'` 标志，决定是否走 synonym 分支。

### 决策 5：导入路由直接写 type

**选择**：`/import/excel_apply` 路由在调用 `apply_mapping` 之前/之后，新建词库时把 `import_mode` 映射成 `type`：

```python
list_type = 'synonym' if import_mode == 'synonym' else 'standard'
db.execute("INSERT INTO word_lists (name, type, ...) VALUES (?, ?, ...)", (name, list_type, ...))
```

**为什么**：导入时已经有 `import_mode`，直接转译，零额外用户操作。

### 决策 6：双英文列同义词词库的特殊处理

**选择**：双英文列模式（`english_col_2 >= 0`）展开后写入的词库，type 也设为 `'synonym'`（因为只有同义词模式才能启用 english_col_2）。

**为什么**：double-check——双英文列模式必然走同义词出题逻辑。这是已经在决策 5 内自动满足的。

## Risks / Trade-offs

- **风险 1：迁移误判** → 80% 阈值可能误把"部分有同义词"的标准词库标成 synonym。缓解：保守阈值（80% 而非 50%）+ 提供未来"词库管理页改 type"功能（本次不做但留好接口）
- **风险 2：干扰项不足** → 同义词词库小（< 4 个有 synonyms 的词）时无法生成 3 个干扰项。缓解：自动降级为中文选项 + log warning
- **风险 3：词库管理页未显示 type** → 用户看不到"这是同义词词库"。本次先不展示；如果用户反馈认知混淆再加（本次 spec 不约束）
- **风险 4：测试覆盖不全** → 增加 6+ 个 test case 覆盖核心路径（迁移、出题、降级、听力豁免）

## Migration Plan

1. `database.py` 加 `type` 字段（`CREATE TABLE` + 幂等 `ALTER`）
2. `database.py` 加 `_migrate_word_list_types(conn)` 函数，在 `init_db()` 末尾调用
3. `app.py` `/import/excel_apply` 写词库时设 type
4. `app.py` `generate_quiz_questions()` 加分支
5. 测试 + 验证 + 文档

无回滚顾虑（旧代码不读 type 列，全部按现有逻辑工作）。

## Open Questions

- 词库管理页要不要显示 `[同义词]` 徽章？暂不做，等用户反馈
- 用户能否手动修改词库的 type？暂不做
- PDF 双列同义词导入也要同步写 type 吗？理论要，但本 change 仅动 Excel；下一个小 change 处理（约 5 行代码）
