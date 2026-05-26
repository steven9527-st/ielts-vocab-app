# 设计文档

## Context

当前架构：Flask 单机应用 + SQLite + Jinja 模板 + 服务端临时文件存储 quiz/parse 数据（避免 cookie 超限）。session 中保存 `list_id`、`learn_session_id`、`quiz_token` 等运行时状态。

本次三个需求共用一条主线：**降低多词库环境下的认知负担**，并扩展学习场景至听力。

## Goals / Non-Goals

### Goals
- 用户能在任何页面 1 次点击切换词库
- 学习/测试中切换有保护机制（防止误操作丢失进度）
- 单词卡片提供朗读能力，零外部依赖
- 测试模式可选文字或听力，结果分别记录

### Non-Goals
- 不做多音标分英美（因数据无法稳定区分两个音标的语种）
- 不做"手动新建空词库"（新建一律走 PDF 导入流程）
- 不做学习模式的"听力学习"形态（只在测试时区分）
- 不引入任何外部 TTS 服务或音频文件（保持单机零依赖原则）
- 不做听力测试影响 streak 的复杂规则（streak 维持现有 learn-only 逻辑）

## Key Decisions

### Decision 1: 词库选择浮层的触发条件

**问题**：什么时候弹"选择词库"浮层？

**选项**：
- A. 永远弹（每次进学习/测试都弹）
- B. 应用首次启动只弹一次（`localStorage` 持久化）
- C. session 内首次进入时弹（关浏览器再开会再弹一次）

**决定**：**C 的变种** — `session['list_picked']` 标记 + 词库数量 ≥ 2 才弹。

**理由**：
- A 太烦
- B 跨设备/清缓存后不再弹，新设备体验差
- C 是平衡点：每个会话提示一次，单词库时直接跳过
- session 已是现有机制，零新增依赖

```
进入 /learn/setup 或 /test/setup
        │
        ▼
   word_lists count >= 2 ?
        │
   ┌────┴────┐
   No        Yes
   │          │
   直接进入   session['list_picked'] ?
              │
         ┌────┴────┐
         True      False
         │          │
         直接进入   渲染浮层
                    用户选完 → POST /api/pick_list
                    → set session['list_picked']=True
                    → set session['list_id']
                    → 重定向回原页面
```

### Decision 2: 进行中切换词库的处理

**问题**：用户在 `flashcard.html`/`quiz.html` 上点顶部"切换词库"会发生什么？

**决定**：前端 JS 检测当前页是否处于"进行中"状态，若是则 `confirm("将放弃当前进度，确认切换？")`。确认后调用 `POST /api/switch_list_safe { list_id, abandon: true }`，后端 abandon 当前 `learn_session` + 清 `quiz_token`，然后切换 `session['list_id']`。

**判定"进行中"**：`request.endpoint` 在 `{'learn_card', 'learn_quiz', 'quiz_question'}` 集合中。模板渲染顶部 nav 时传递一个 `is_in_progress` 上下文变量给前端 JS。

**为什么不在后端检测**：后端检测会让"切换词库"按钮变成两次请求（先查状态再决定要不要弹），不如前端一次完成。

### Decision 3: TTS 实现方案

**决定**：浏览器原生 `window.speechSynthesis` API。

**实现要点**：
```javascript
function speakWord(text) {
  if (!('speechSynthesis' in window)) {
    alert('当前浏览器不支持发音功能');
    return;
  }
  window.speechSynthesis.cancel();  // 防止上一次未完成
  const u = new SpeechSynthesisUtterance(text);
  u.lang = 'en-US';
  u.rate = 0.9;
  window.speechSynthesis.speak(u);
}
```

**抽离位置**：放进 `static/style.css` 同目录的 `static/tts.js`，由 `base.html` 末尾统一引入，flashcard / quiz 都能复用。

**降级**：检测 `'speechSynthesis' in window`，不支持时按钮渲染为 disabled + 灰色 + title 提示"当前浏览器不支持发音"。

**为什么不预生成音频**：
- 单机应用无外网假设 → 不能用 CDN
- 词库导入是动态的 → 不能预生成
- 服务端生成音频要装 espeak/festival 等系统包 → 破坏"零依赖 Flask"

### Decision 4: 听力测试题目数据结构

**决定**：复用现有 `generate_quiz_questions` 输出，**不改数据结构**，只在 quiz_data 顶层增加 `question_type` 字段：

```python
{
    "questions": [...],
    "word_ids": [...],
    "question_type": "text" | "audio"   # 新增
}
```

`quiz.html` 模板根据 `question_type` 切换渲染：
- `text`：显示 `<div class="quiz-english">{{ question.english }}</div>`（现状）
- `audio`：显示 `<button class="quiz-audio-btn" data-text="{{ question.english }}">🔊 播放</button>` + `<script>` 进入时自动调用一次 `speakWord()`

### Decision 5: study_log.mode 扩展策略

**决定**：保持 schema 不变，写入时使用新值，读取时归一化。

```python
# 写入侧（test_start）
mode_value = 'test_audio' if test_type == 'audio' else 'test_text'

# 读取侧（streak/统计）
# 历史 'test' 视为 'test_text'：
#   WHERE mode IN ('test', 'test_text')  → 文字测试
#   WHERE mode = 'test_audio'             → 听力测试
#   WHERE mode = 'learn'                  → 不变
```

streak 计算逻辑（`calc_streak`）目前 `WHERE mode='learn'`，无需改动。

**为什么不做物理迁移**：风险 vs 收益不成比例。归一化只增加 2 个查询的 SQL 复杂度，没有运行时性能影响。

### Decision 6: 顶部导航词库切换组件

**决定**：在 `base.html` 顶部 nav 中加 `_list_switcher.html` partial，通过 context processor 全局注入数据。

```python
@app.context_processor
def inject_nav_data():
    db = get_db()
    all_lists = [dict(r) for r in db.execute(
        'SELECT id, name FROM word_lists ORDER BY created_at ASC'
    ).fetchall()]
    db.close()
    current_id = session.get('list_id')
    in_progress = request.endpoint in {'learn_card', 'learn_quiz', 'quiz_question'}
    return {
        'nav_all_lists': all_lists,
        'nav_current_list_id': current_id,
        'nav_in_progress': in_progress
    }
```

**位置约定**：组件在 nav 中央，brand 右侧、links 左侧；无词库时不显示。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| Web Speech 在 Linux/某些 Windows 浏览器无声 | 检测后禁用按钮 + tooltip 提示；不阻塞核心流程 |
| `speechSynthesis.cancel()` 在快速连点时可能吞掉首声 | 加 50ms setTimeout 缓冲；提供"再播一次"重试 |
| context_processor 每个请求多 1 次 SELECT | word_lists 数据量极小（<100 条），SQLite 内存查询，影响可忽略 |
| 用户在听力测试中关闭声音/拔耳机 | UI 显示"听不清？再播一次"按钮兜底；不能完全规避 |
| session['list_picked'] 跨标签页不一致 | 接受。Flask session 是 cookie 级别的，多标签共享，影响小 |

## Migration Plan

无 schema 迁移。一次性发布，用户首次访问后：
1. session 中无 `list_picked` → 进入学习/测试时按新逻辑触发浮层
2. 历史 `study_log.mode='test'` 自动按 `test_text` 处理
3. 词库导航切换组件无需用户操作即可使用

## Open Questions

无。所有决策已对齐。
