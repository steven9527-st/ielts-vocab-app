# 任务清单

按交付独立性切分为 4 个阶段。建议顺序执行，每阶段结束后可独立验证。

---

## Phase 1: 全站词库切换基础设施（前置）

- [x] 1.1 在 `app.py` 添加 `@app.context_processor inject_nav_data`，全局提供 `nav_all_lists` / `nav_current_list_id` / `nav_in_progress`
- [x] 1.2 在 `app.py` 新增路由 `POST /api/switch_list_safe`，接收 `{list_id, abandon: bool}`，按需 abandon learn_session 并清 quiz_token
- [x] 1.3 创建 `templates/_list_switcher.html` partial，渲染下拉切换组件（含进行中态判定）
- [x] 1.4 在 `templates/base.html` 的 nav 中通过 `{% include '_list_switcher.html' %}` 注入组件
- [x] 1.5 在 `static/style.css` 增加 `.list-switcher` / `.list-switcher__menu` 样式
- [x] 1.6 添加前端 JS：进行中点击切换 → confirm → 调 `/api/switch_list_safe`

## Phase 2: 词库选择浮层 + 新建按钮

- [x] 2.1 创建 `templates/_list_picker.html` partial，包含词库列表、单选、确认按钮
- [x] 2.2 在 `app.py` 新增路由 `POST /api/pick_list`，写入 `session['list_id']` 和 `session['list_picked']=True`
- [x] 2.3 修改 `learn_setup` / `test_setup` 视图：当 `len(all_lists) >= 2` 且 `session.get('list_picked') != True` 时，渲染时传递 `show_picker=True`
- [x] 2.4 在 `learn_setup.html` / `test_setup.html` 中根据 `show_picker` 渲染 `_list_picker.html`
- [x] 2.5 在 `templates/library.html` 右上角增加"+ 新建词库"按钮，链接到 `url_for('import_page')`
- [x] 2.6 在 `import_confirm` 视图成功后，重置 `session['list_picked']=True`（用户主动选了新建后的词库）

## Phase 3: 单词发音

- [x] 3.1 创建 `static/tts.js`，导出全局 `speakWord(text)` 函数和能力检测 `ttsAvailable()`
- [x] 3.2 在 `templates/base.html` 末尾添加 `<script src="{{ url_for('static', filename='tts.js') }}"></script>`
- [x] 3.3 修改 `templates/flashcard.html`：音标右侧添加 `<button class="btn-tts" type="button">🔊</button>`，点击调用 `speakWord(english)`
- [x] 3.4 在 `static/style.css` 增加 `.btn-tts` / `.btn-tts:disabled` 样式（圆形小按钮）
- [x] 3.5 处理无音标场景：单词没有音标时，🔊 按钮直接跟在单词后；有音标时跟在音标行末尾
- [x] 3.6 浏览器不支持时按钮渲染为禁用态 + tooltip"当前浏览器不支持发音"

## Phase 4: 听力测试

- [x] 4.1 修改 `templates/test_setup.html`：在题数输入上方添加"测试类型"单选组（○ 文字测试 / ○ 听力测试），name=`test_type`，default=`text`
- [x] 4.2 修改 `app.py` 的 `test_start`：接收 `test_type` 参数，存入 `quiz_data['question_type']`，写 `session['quiz_test_type']`
- [x] 4.3 修改 `app.py` 的 `quiz_question` 视图：将 `question_type` 传给模板
- [x] 4.4 修改 `templates/quiz.html`：根据 `question_type`：
  - `text` 模式渲染现有 `.quiz-english` 大字
  - `audio` 模式渲染 🔊 大按钮 + 进入时 JS 自动调用 `speakWord()` 一次
- [x] 4.5 修改 `app.py` 的 `quiz_submit`：test 模式写 `study_log.mode` 时，根据 `session['quiz_test_type']` 写入 `'test_text'` 或 `'test_audio'`
- [x] 4.6 修改 `templates/test_result.html`：在标题区显示当前测试类型徽标（"文字测试" / "听力测试"）
- [x] 4.7 验证 `calc_streak` 不受影响（其只查 `mode='learn'`）

## Phase 5: 验证与清理

- [x] 5.1 手动用例：单词库下进学习不弹浮层；新建第二个词库后再进学习弹浮层（用户委托归档，视为接受）
- [x] 5.2 手动用例：学习中切词库 → 弹确认 → 确认后旧 session abandoned + 切到新词库（用户委托归档，视为接受）
- [x] 5.3 手动用例：flashcard 点 🔊 能听到 en-US 朗读；macOS Safari + Chrome 各试一次（用户委托归档，视为接受）
- [x] 5.4 手动用例：听力测试进入题目自动播一次 + 重复点 🔊 重播（用户委托归档，视为接受）
- [x] 5.5 手动用例：完成一次文字测试 + 一次听力测试，结果页显示对应徽标，study_log 中 mode 分别为 `test_text`/`test_audio`（用户委托归档，视为接受）
- [x] 5.6 浏览器不支持 TTS 的降级测试（DevTools 模拟 / 老 Edge）（用户委托归档，视为接受）
- [x] 5.7 `openspec validate multi-list-tts-audio-test --strict` 通过
- [x] 5.8 README 更新：新增"发音功能要求浏览器支持 Web Speech API"说明

> 自动化烟测：所有路由（`/`, `/learn/setup`, `/test/setup`, `/library`, `/static/tts.js`）HTTP 200 通过；`python3 -c "import py_compile; py_compile.compile('app.py')"` 通过；无 linter 报错。
