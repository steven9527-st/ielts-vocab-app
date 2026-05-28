## Context

普通词库学习流（`/learn/next`）在学完最后一张后自动 `redirect(url_for('learn_quiz'))`，进入「学完即测」闭环。同义词学习流（`/learn/synonym/next` 和 `/learn/synonym/done` 周边路由）在学完最后一张时直接 `redirect(url_for('synonym_done'))`，缺失测验环节。

已有能力 `synonym-quiz` 通过 `generate_quiz_questions(list_type='synonym')` 支持同义词测验模式（用英文同义词作选项、听力豁免），但目前只被「首页 → 开始测验」入口调用，未接入同义词学习流。

本次目标：在不破坏 `synonym_done` 的统计写入逻辑（`learn_synonym` study_log）前提下，把测验环节插入到「学完最后一张 → 完成页」之间。

## Goals / Non-Goals

**Goals:**
- 同义词学完最后一张 → 自动跳测验 → 测验完成 → 完成页（对齐普通流体验）
- 测验范围严格限定为本次学习的 `syn_word_ids`，不混入词库其他词
- `synonym_done` 现有 `study_log(mode='learn_synonym')` 写入逻辑保留（streak / today_completed 统计不变）
- 测验通用流程自然写入 `study_log(mode='quiz')`（和普通流一致）

**Non-Goals:**
- 不修改 `synonym-quiz` 能力本身（题目生成、选项规则、UI 完全复用）
- 不修改首页「开始测验」入口的行为
- 不引入新的「跳过测验」开关（保持简单，对齐普通流）

## Decisions

### Decision 1: 复用 `learn_quiz` 还是另起 `synonym_learn_quiz` 路由？

**选择**：复用 `learn_quiz`。

**理由**：
- `learn_quiz` 内部已经通过 `_get_list_type()` + `generate_quiz_questions(list_type)` 分发到同义词测验模式，逻辑天然兼容
- 同义词学习流的 `syn_word_ids` 与普通流的 `learn_session.word_ids` 结构一致，只需让 `learn_quiz` 能从同义词 session 取词即可
- 避免新增重复路由

**替代方案**：新增 `/learn/synonym/quiz` 路由，独立于 `learn_quiz`。被否决，因为会重复 90% 的测验流程代码。

### Decision 2: 如何让 `learn_quiz` 知道"这次是同义词学习收尾"？

**选择**：在跳转测验前，把 `syn_word_ids` 写入一个临时 session key（如 `pending_quiz_word_ids` 和 `pending_quiz_return_to='synonym_done'`），由 `learn_quiz` 优先消费。

**理由**：
- 不污染 `learn_session` 表（同义词学习没有用这张表）
- 测验完成后能识别"该回到 synonym_done"而不是普通流的 `learn_done`

**替代方案**：把同义词学习也写入 `learn_session` 表，统一走普通流。被否决，因为同义词学习的 session 结构（`syn_queue`、`syn_total` 等）与 `learn_session` 不同，硬塞会破坏现有逻辑。

### Decision 3: 测验完成后的跳转目标

**选择**：测验完成页（`quiz_result.html` 或现有 `learn_done.html` 流程）保持现状；"返回首页"按钮所在的 `synonym_done` 页改为通过 session 标记决定是否还要展示「同义词学完」的庆祝文案。

**实现路径**：测验流程结束后，若 `pending_quiz_return_to == 'synonym_done'`，则在测验结果页的 CTA 中加一个「返回同义词完成页」入口；或直接在测验完成时自动 redirect 到 `synonym_done`，由 `synonym_done` 复用已 pop 的 session 数据展示总结。

**简化策略**：MVP 阶段——测验完成后**直接 redirect 到 `synonym_done`**，复用原有完成页。`synonym_done` 内部已经在做 `session.pop`，需要确保在跳测验前不要 pop `syn_total/syn_word_ids/syn_started_at/syn_list_id`，留给完成页消费。

### Decision 4: `study_log` 重复写入风险？

**选择**：让测验流程自然写 `study_log(mode='quiz')`，`synonym_done` 仍写 `study_log(mode='learn_synonym')`。两条记录互不冲突，且和普通流（`learn` + `quiz` 两条）行为一致。

## Risks / Trade-offs

- **[风险] session 数据生命周期变长**：原来"学完 → 完成页 pop"一气呵成，现在中间插入测验，期间用户可能刷新或导航离开，导致 `syn_*` session 丢失。
  → **缓解**：在测验完成跳转 `synonym_done` 时，若 session 已丢失，`synonym_done` 走 fallback（显示通用文案 + 返回首页，不写 study_log，因为 quiz 流程已经记录了学习行为）。

- **[风险] 测验中途用户退出**：用户在测验页面点"返回首页"，此时 `learn_synonym` 的 study_log 未写入，会影响 streak 统计。
  → **缓解**：在跳转测验**之前**就把 `learn_synonym` 的 study_log 写好（不再等到完成页），完成页只负责 UI 展示。这样无论用户是否完成测验，学习行为都已记账。

- **[风险] 单词数过少时（如只学了 3 个）测验意义不大**：和普通流一致，普通流也没有最低数量门槛。
  → **不缓解**：保持和普通流一致行为，由用户在 setup 阶段决定学习数量。

## Migration Plan

无数据迁移。仅代码改动，部署后立即生效。回滚策略：还原 `app.py` 中跳转逻辑即可。
