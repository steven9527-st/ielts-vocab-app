## Context

当前学习与测验流程的状态机是「单调向前」设计：

```
┌─────────────────────────────────────────────────────────────────┐
│  现状数据模型（关键障碍：状态信息有损丢失）                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  learn_session 表                                               │
│  ─────────────────                                              │
│  word_ids       JSON: [101, 105, 87, 91, 22]  (固定全集)        │
│  remaining_ids  JSON: [91, 22]                (剩余未学)        │
│                                                                 │
│  /learn/next:                                                   │
│      remaining.pop(0)   ← 弹出即丢弃，无法回头                  │
│      → "学过的"位置信息彻底丢失                                 │
│                                                                 │
│  ─────────────────                                              │
│  Flask session 字典（测验状态）                                 │
│  ─────────────────                                              │
│  quiz_index    int  0,1,2,...                                   │
│  quiz_answers  dict {"0":"A","1":"C","2":"B"}                   │
│                                                                 │
│  /quiz/answer:                                                  │
│      session['quiz_index'] = idx + 1   ← 单调递增               │
│      → 索引前进后不可回退                                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

learn 路径丢失了"哪些词已学过"的位置信息；quiz 路径虽然 `quiz_answers` 保留了历史答案（dict 按 idx 存储），但 `quiz_index` 不支持回退。两边的修复策略不同。

涉及的现有路由与模板：
- `app.py` `/learn/card` `/learn/next` `/learn/quiz` `/quiz/question` `/quiz/answer` `/quiz/submit` `/quiz/retry`
- `templates/flashcard.html` `templates/quiz.html` `templates/quiz_error.html`
- `database.py` `learn_session` 表 schema
- 学习中放弃 (`/learn/abandon`) / 断点续传 (`/learn/continue`) 等周边逻辑

## Goals / Non-Goals

**Goals:**

- 翻卡学习内可双向流转，键盘 ← / → 与按钮均可用
- 学习测验、正式测试（文字 + 听力）可回退改答案，最终分数按最后一次提交计算
- 后端状态机改造不破坏既有「放弃」「断点续传」「错题循环」流程
- 旧版数据库（无 `current_index` 字段）能平滑迁移，不丢失用户进度

**Non-Goals:**

- 不引入"标记困难词"等学习强度调整功能（与回退正交，未来可单独 propose）
- 不改变翻卡测验结束后 `study_log` / `learn_session.status='done'` 的记账逻辑
- 不调整测试结果页 (`test_result.html`) 与错题统计页 (`quiz_result.html`) UI
- 不引入"撤销最后一次操作"等通用 undo 框架，仅做导航级双向流转

## Decisions

### 决策 1：翻卡数据模型从「剩余列表」改为「全集 + 游标」

**选择**：`learn_session` 增加 `current_index INTEGER DEFAULT 0` 字段，配合既有 `word_ids` 全集；`remaining_ids` 字段保留但其语义变成「冗余镜像」（仅用于兼容旧逻辑），所有读写以 `word_ids[current_index]` 为准。

**为什么**：

| 方案 | 优点 | 缺点 |
|---|---|---|
| A. 不动 schema，将"已学过"的词重新塞回 `remaining_ids` 末尾 | 零 DB 变更 | 顺序变乱，进度计数无法准确反映；abandon 时刻状态不一致 |
| B. 新增 `current_index` 字段 ✅ | 状态机清晰；前进/后退就是 `index += 1` / `index -= 1`；abandon 仍工作 | 需要 schema 迁移 |
| C. 用 `studied_ids` + `remaining_ids` 双列表 | 学过/未学截然分开 | 两个列表同步维护，bug 面大；游标本质上还是要算 |

方案 B 是状态机标准建模，前进/后退对称，便于推理。

### 决策 2：测验回退采用「重置 `quiz_index`」而非新增字段

**选择**：`/quiz/prev` 路由仅执行 `session['quiz_index'] -= 1`，不引入新字段。题目页渲染时根据 `session['quiz_answers'].get(str(idx))` 回填已选选项。

**为什么**：`quiz_answers` dict 已按 idx 存储用户每次的选择，回退即"重新展示某 idx 的题目，预选回原答案"，回答后覆盖即可。无须新增数据。

### 决策 3：进度计数器显示「最大已达进度」而非「当前位置」

**选择**：在 `session` 中新增 `learn_max_reached` 与 `quiz_max_reached` 字段，记录历史峰值；模板显示 `max(current, max_reached)` 风格的"X / Total"。

**为什么**：用户明确要求"进度不动"。这样回退浏览时不会让数字倒退给人"白学了"的感觉；同时前进到新位置时计数自然推进。需要在 `/learn/next` `/quiz/answer` 中维护此峰值。

**实现细节**：

```
learn_max_reached  存储已学过的张数（1-based 的最大值）
quiz_max_reached   存储已答过的题数

进度显示规则：
    显示 = max(current_position, max_reached)
    
例：用户已经到了第 5 张（max_reached=5），回到第 3 张
    显示 "5 / 20"  ← 不退步
回到第 3 张再前进到第 6 张
    显示 "6 / 20"  ← 推进，max_reached 更新为 6
```

### 决策 4：旧 session 兼容采用「lazy 迁移」

**选择**：不写一次性 SQL 迁移脚本，而是在 `/learn/continue` 与 `/learn/card` 路由读取 session 时按需推算：

```python
if ls['current_index'] is None:
    # 旧版 session：用 word_ids - remaining_ids 推算游标
    word_ids = json.loads(ls['word_ids'])
    remaining = json.loads(ls['remaining_ids'] or '[]')
    current_index = len(word_ids) - len(remaining)
    db.execute('UPDATE learn_session SET current_index=? WHERE id=?',
               (current_index, ls['id']))
```

**为什么**：本应用是单机 SQLite，无升级窗口概念；用户随时可能在旧 session 进行中升级新版。lazy 迁移在用户继续学习时透明完成，零中断。一次性脚本反而要担心"应用启动时机"。

### 决策 5：键盘交互沿用既有约定

**选择**：
- 翻卡：`Space` 翻转、`→` 下一张（既有）、`←` 上一张（新增）、`←` 在第一张时无效
- 测验：`→` 提交并下一题（既有）、`←` 上一题（新增）、`←` 在第一题时无效

**为什么**：← / → 是用户对前后翻页的本能映射。仅在边界静默忽略，不弹提示（弹了反而打断节奏）。

### 决策 6：错题循环（quiz_error）页一并支持回退

**选择**：`quiz_error.html` 与 `quiz.html` 共用 `/quiz/question` 路由，自然继承回退能力。错题轮次内的 quiz_index 同样支持回退。

**为什么**：错题循环本质上就是新一轮 quiz，复用同套机制是当前架构的优点，应延续。

## Risks / Trade-offs

- **风险 1：旧 session 迁移异常** → Lazy 迁移代码加 try/except，迁移失败则降级为"按旧逻辑继续"（remaining_ids pop 模式），用户至少不卡死；记 warning log 便于排查
- **风险 2：用户回退测验后改答案导致预期外的成绩** → 这是产品本意（用户已确认决策 ②），无需缓解；但在 quiz_result.html 显示分数时不显示"曾经选过 X 后改为 Y"的历史轨迹，避免界面混乱
- **风险 3：max_reached 在 abandon 后未清理污染下一个 session** → `learn_abandon` / `quiz_submit` 路由末尾必须 `session.pop('learn_max_reached', None)` / `session.pop('quiz_max_reached', None)`；测试用例必须覆盖
- **风险 4：current_index 越界（用户手动改 URL）** → 路由读取时 clamp 到 `[0, len(word_ids)-1]`；超过末尾仍走"全部学完→进入测验"逻辑
- **风险 5：听力测试回退后音频自动播放可能不符合用户预期** → 听力测试当前是用户主动点 🔊 播放（已查 quiz.html 行为），回退后不会自动重播，符合预期；写入 spec 明确这一点
- **Trade-off：max_reached 让进度计数不直观地"反映当前所在位置"** → 用户明确选择此方案，文档清楚说明即可

## Migration Plan

1. **DB schema 迁移**：在 `database.py` 的 `init_db()` 中以 `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE learn_session ADD COLUMN current_index INTEGER` 兼容方式新增字段（外加 try/except SQLite "duplicate column" 错误吞掉，幂等）
2. **代码部署**：单机应用直接覆盖 .exe / .app；用户下次启动应用时 `init_db()` 自动加列
3. **Lazy session 迁移**：用户首次访问 `/learn/continue` 或 `/learn/card` 时触发推算与回填
4. **回滚策略**：如紧急回滚旧版，新 `current_index` 列对旧代码无害（旧代码不读它）；旧代码继续按 `remaining_ids` 工作

## Open Questions

- 翻卡学习的"上一张"按钮在**第一张**时如何呈现？灰显（disabled）还是直接不渲染？倾向灰显（保持布局稳定），开工时再最终定。
- 测验回退到第一题时"上一题"按钮是否要做同样处理？同上。
- 听力测试模式下，回退后用户需不需要"自动重播一次"？倾向不自动播，保持用户主控；如后续反馈强烈再调整。
