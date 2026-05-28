## Context

首页 `templates/index.html` 当前按钮区结构（约 60-90 行）：

```
┌────────────────────────────────────────────────────────────────┐
│  当前布局                                                      │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  [继续上次学习]?  [开始学习]  [测试模式]  [同义词学习 (N)]?    │
│         ↑              ↑                       ↑               │
│         条件1          固定指向                条件2            │
│                        /learn/setup            stats.with_syn   │
│                                                                │
│  条件1：active_session（learn_session in_progress）            │
│  条件2：stats.with_synonyms > 0（词库内有同义词的词数）        │
│                                                                │
│  问题：                                                        │
│    • 「开始学习」与「同义词学习」是两个不同的"开始"            │
│    • 用户得理解词库 type 才能选对                              │
│    • 同义词词库其实根本不应该走"普通学习"                      │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

`add-synonym-quiz-mode` 引入了 `word_lists.type` 字段（`'standard'` / `'synonym'`），是天然的分发依据。

后端两个学习 session 状态机彼此独立：

- 普通学习：`learn_session` 表 + Flask session `learn_session_id`
- 同义词学习：Flask session `syn_queue` / `syn_total`（无 DB 表）

`calc_streak()` 与 `today_completed()` 当前只看 `study_log.mode='learn'` 与 `accuracy=1.0`，同义词学习完成后没有写 `study_log`，导致打卡 streak 漏算。

## Goals / Non-Goals

**Goals:**

- 首页只剩**一个**「开始学习」按钮，按当前词库 type 自动分发
- 「继续上次学习」按钮在两种 session 类型下都正常工作
- 同义词学习完成时计入 streak（与普通学习一致）
- 同义词词库的 `stats.with_synonyms` 数字仍可在某处展示（如词库管理页徽章），但不再作为按钮可见性条件

**Non-Goals:**

- 不合并底层路由（`/learn/setup` 与 `/learn/synonym/setup` 仍各自存在；只是首页按钮指向变化）
- 不动测验入口（`/test/setup` 已与 type 无关，仍按词库 type 自动出题）
- 不引入"按钮文案根据 type 变化"（例如改成"同义词学习"——保持"开始学习"统一文案更简洁）
- 不动同义词学习的进度计算 UI（"X / N · 同义词模式"那种顶部计数）

## Decisions

### 决策 1：分发逻辑放在 Jinja 模板层（前端），不引入新路由

**选择**：

```jinja
{% if current_list.type == 'synonym' %}
  <a href="{{ url_for('synonym_setup') }}" class="btn btn--primary btn--lg">开始学习</a>
{% else %}
  <a href="{{ url_for('learn_setup') }}" class="btn btn--primary btn--lg">开始学习</a>
{% endif %}
```

**为什么**：

| 方案 | 优点 | 缺点 |
|---|---|---|
| A. 模板层 if 分发 ✅ | 简单、所见即所得；后端无需新路由 | 模板里多一个 if |
| B. 后端加 `/learn/start_smart` 路由，根据 type 重定向 | 模板更干净 | 多一次重定向；维护成本+1 |
| C. JavaScript 拦截点击事件做分发 | 灵活 | 复杂；禁用 JS 时失效 |

A 最朴素。

### 决策 2：「继续上次学习」按钮的双 session 检测

**选择**：模板检测两个 session 任一存在即显示按钮，链接根据 type 分发：

```jinja
{% set has_progress = active_session or active_syn_session %}
{% if has_progress and not completed_today %}
  {% if current_list.type == 'synonym' %}
    <a href="{{ url_for('synonym_setup') }}" class="btn btn--ghost">继续上次学习</a>
  {% else %}
    <a href="{{ url_for('learn_continue') }}" class="btn btn--ghost">继续上次学习</a>
  {% endif %}
{% endif %}
```

同义词学习的"继续"实质就是回到 setup 页（因为 syn_queue 在 session 里，自然恢复）。如果 syn_queue 已耗尽，setup 会进入"今日已完成"分支。

**为什么不做独立的 `/learn/synonym/continue` 路由**：现状同义词进度本就由 Flask session 保存，setup 页是天然的"恢复入口"。再造一个路由没必要。

### 决策 3：同义词学习完成时写 study_log

**选择**：在 `synonym_done` 路由（用户完成所有同义词卡片后跳转的页面）的前置逻辑里，新增：

```python
db.execute(
    'INSERT INTO study_log (list_id, date, mode, word_ids, accuracy, duration_s) VALUES (?,?,?,?,?,?)',
    (list_id, str(date.today()), 'learn_synonym', json.dumps(word_ids), 1.0, duration)
)
```

mode 值用 `'learn_synonym'` 区分（不与 `'learn'` 混淆，便于未来统计区分）。

### 决策 4：扩展 calc_streak / today_completed 包含同义词学习

**选择**：

```python
# calc_streak() 内：
"SELECT DISTINCT date FROM study_log WHERE mode IN ('learn', 'learn_synonym') ORDER BY date DESC LIMIT 30"

# today_completed() 内：
"SELECT id FROM study_log WHERE list_id=? AND mode IN ('learn', 'learn_synonym') AND accuracy=1.0 AND date=?"
```

**为什么**：合并入口后两种学习地位平等。打卡是看用户"今日是否学习"，不应区分形态。

### 决策 5：同义词学习 duration_s 计算

**选择**：在 `synonym_start` 路由设 `session['syn_started_at'] = datetime.now().isoformat()`；`synonym_done` 取出并算差值。

如果 session 已过期（cookie 丢失），duration_s 写 0，不阻塞 streak 记录。

### 决策 6：「同义词学习」按钮直接删除而非保留禁用

**选择**：完全移除模板中 `{% if stats.with_synonyms %}` 那段按钮代码。

**为什么**：

- 保留禁用状态会让用户疑惑"为什么不能点"
- 用户的直觉就是点「开始学习」开始学习；现在这个按钮已经能正确分发
- 干净优雅

### 决策 7：`stats.with_synonyms` 字段保留但不再驱动 UI

**选择**：后端 `get_list_stats()` 继续返回 `with_synonyms`（被测试与其他代码引用），首页模板不再读它。

未来如果想在某处显示"本词库有 N 个同义词"作为信息展示，可以复用。

## Risks / Trade-offs

- **风险 1：用户记忆中"同义词学习"按钮消失后找不到入口** → 实际新「开始学习」按钮在同义词词库下行为完全等价，零功能损失。可在首版上线后观察是否需要 toast 提示
- **风险 2：active_syn_session 检测逻辑跨 Flask session 时可能不可靠** → Flask session 有效期与 cookie 持久化相关；如果用户清浏览器数据则丢失。但 syn_queue 本就是 ephemeral 设计，此风险一直存在，本 change 不引入新问题
- **风险 3：同义词学习 study_log 写入失败导致 streak 不更新** → try/except 包裹写入，失败仅 log warning，不阻塞用户进入结果页

## Migration Plan

1. 模板首页改造（删按钮 + 按 type 分发）
2. 后端 index 路由增加 active_syn_session 检测
3. synonym_done 路由加 study_log 写入 + syn_started_at 计算
4. synonym_start 路由设置 syn_started_at
5. calc_streak / today_completed 扩展 mode IN
6. 测试 + 实测

零数据迁移；无回滚风险（删按钮不影响数据；study_log 多记录不破坏既有统计）。

## Open Questions

- 同义词学习未通关（中途退出）是否要计入"今日已学习"？目前普通学习也是 accuracy=1.0 才计入；同义词学习也保持一致（全卡通过才计入）。
- 词库管理页（library.html）是否要显示词库 type 徽章？本次不做，留作后续小 change。
