## Context

**当前架构**：
- `words.status` 字段（`'unmastered' | 'mastered'`）表示单词的掌握状态，`get_list_stats` 直接查这个字段统计首页 metric
- 普通学习流通关时 (`quiz_submit`, mode='learn', accuracy=1.0)，会遍历 `word_ids` 执行 `UPDATE words SET status='mastered'`
- 同义词学习流（`add-synonym-learn-quiz` change 引入）为避免破坏 `learn_session` 逻辑，**故意跳过了 UPDATE words**，只写 `study_log`
- 错题重做 `quiz_retry` 会把 `session['quiz_token']` 指向的 `_save_quiz_data` payload 中的 `word_ids` 从 20 个（原始）覆盖成 2 个（错题子集）
- `study_log` 表用于 streak 计算，字段完整（`list_id, date, mode, word_ids, accuracy, duration_s`）

**关键洞察**：
1. `learn_session.word_ids` 是不可变的"本次会话原始全集"，重做流程不修改它 → **单一可信来源**
2. 同义词流的原始全集在 `session['syn_word_ids']`（Flask session），跳测验前已存入 `session['pending_quiz_word_ids']` → `learn_quiz` 读取后写入 `_save_quiz_data({'word_ids': ...})`，同样会被 retry 覆盖
3. 首页"今日新增掌握"数据源用 `study_log`（`learn`+`learn_synonym` 且 `accuracy=1.0` 的当天记录）去重合并即可

## Goals / Non-Goals

**Goals:**
- 通关页 total、mastered 更新、study_log 三者都反映"本次学习会话的原始 word_ids 全集"
- 同义词学习通关也标 mastered，首页统计对齐真实进度
- 首页在"今日已通关 ✅"下方展示"今日新增掌握 N 个"
- 提供一次性迁移，补齐历史遗留的同义词流未标 mastered 的词

**Non-Goals:**
- 不改 `study_log` 表结构
- 不改 `learn_session` 表结构
- 不引入"今日累计"字段（每次算即可，量小）
- 不修改测试模式（test_text/test_audio）的 mastered 逻辑

## Decisions

### Decision 1: 普通流通关 total 数据源

**选择**：从 `learn_session.word_ids` 读取（DB 中的原始全集）。

**理由**：
- `learn_session.word_ids` 在 `learn_start` 时写入后不变
- `quiz_retry` 只覆盖 `session['quiz_token']` 指向的临时文件里的 word_ids，DB 记录不动
- 现有 `quiz_submit` 代码里 `sess_id = session.get('learn_session_id')` 已经在读 learn_session，插一句 `original_word_ids = json.loads(ls['word_ids'])` 就够

**替代方案**：新加一个 session key `learn_original_word_ids` 记录原始 20 个词。被否决，因为 DB 已有权威来源，session 又冗余又难维护。

### Decision 2: 同义词流通关 total 数据源

**选择**：从 `session['syn_word_ids']`（若还在）或**回退到 quiz_data 中的 word_ids**（跳测验前 pending_quiz_word_ids 是原始 syn_word_ids 的复制）。

**关键点**：`learn_quiz` 里把 `pending_quiz_word_ids` 存到 `_save_quiz_data({'word_ids': ...})` 时是**首次学习的完整列表**；如果用户没重做（0 错题直接通关），quiz_data.word_ids 就是完整的；但用户有错题重做，quiz_retry 会覆盖它。

**解决方案**：在 `learn_quiz` 触发同义词流时，额外把原始 word_ids 写入 `session['quiz_original_word_ids']`；`quiz_submit` 通关时优先读它，而不是 quiz_data。普通流也用同样机制，逻辑统一。

**替代方案**：让 `quiz_retry` 保留 quiz_data 原始 word_ids 不覆盖，另外用一个字段存错题子集。被否决，因为改动面更大、影响现有 quiz_retry 语义。

### Decision 3: 「今日新增掌握 N 个」计算方法

**选择**：`SELECT word_ids FROM study_log WHERE list_id=? AND date=? AND mode IN ('learn','learn_synonym') AND accuracy=1.0` → 每条 `json.loads` 后 flatten 去重 → `len(set(...))`。

**理由**：
- 直接反映当天所有通关会话的独立词数，重复学同一个词只算一次
- study_log 是唯一权威事件流
- 只在首页渲染时查询一次，性能可接受（每日记录数不会超过几十条）

**替代方案A**：新增字段 `words.mastered_at` 时间戳，然后 `SELECT COUNT(*) WHERE mastered_at=today`。被否决，需要 schema 迁移；且不能追溯"重新掌握又忘记又掌握"这类边缘场景（虽然目前没这需求）。

**替代方案B**：把 today count 缓存在 session。被否决，切词库、多标签页、跨请求都会失效。

### Decision 4: 历史数据回补策略

**选择**：`init_db()` 里加一次幂等迁移函数 `_migrate_synonym_mastered()`，扫 `study_log` 里所有 `mode='learn_synonym' AND accuracy=1.0` 的记录，对 word_ids 中每个 wid 执行 `UPDATE words SET status='mastered' WHERE id=?`。

**幂等保证**：SQL 语义天然幂等（一次或多次 UPDATE 结果相同），且已经是 mastered 的词再 UPDATE 无副作用。

**触发时机**：应用启动时自动跑（对齐 `_migrate_word_list_types` 的模式），用户无感升级。

## Risks / Trade-offs

- **[风险] `learn_session.word_ids` 在极端情况下与 quiz_data 中的错题重做不一致**：例如用户重做时 word_ids 只剩 2 个错题，但通关后仍 UPDATE 全部 20 个为 mastered——这是**期望行为**，因为首轮已经答对的 18 个也确实"本次学习会话中掌握"，用户就是这样理解的。
  → 不缓解，此为设计意图。

- **[风险] 历史数据回补可能把用户已"手动标为未掌握"的词回撤为 mastered**：如果用户在词库管理页手动点了"未掌握"（把一个原本 mastered 的词降级），迁移会误伤。
  → **缓解**：迁移只针对当前 status='unmastered' 的词做 UPDATE（`UPDATE ... WHERE id=? AND status='unmastered'`），已经手动改过的不动。

- **[风险] `today_mastered_count` 每次首页请求都跑一次 SQL**：低频页面 + 小数据量，可接受。
  → 不缓解。

## Migration Plan

- 部署即生效，无 schema 变更
- `_migrate_synonym_mastered()` 在应用启动时自动运行一次（幂等）
- 回滚：还原 `app.py`、`templates/index.html` 即可；被回补的 mastered 数据保留（不影响功能）
