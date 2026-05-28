## 1. 后端：注册 has_cjk Jinja test

- [x] 1.1 在 `app.py` Flask 应用初始化处（`app = Flask(__name__)` 之后），新增 `has_cjk(s)` 函数：遍历字符串字符判断是否有任一字符 `'\u4e00' <= ch <= '\u9fff'`，对非字符串输入安全返回 False
- [x] 1.2 用 `app.jinja_env.tests['has_cjk'] = has_cjk` 注册为模板可用的 test
- [x] 1.3 验证：`python3 -c "from app import has_cjk; assert has_cjk('折磨'); assert not has_cjk('plight'); print('OK')"`

## 2. 前端：CSS 新增两个工具类

- [x] 2.1 在 `static/style.css` 末尾追加 `.synonym-front-chinese`：margin-top:12px / font-size:14px / color:var(--clr-text-muted) / line-height:1.5 / max-width:90% / text-align:center
- [x] 2.2 追加 `.synonym-syn--cn`：color:var(--clr-text-muted) / font-weight:400（覆盖 SYNONYMS 列表 meaning-line 默认的 500）

## 3. 前端：模板正面新增中文行

- [x] 3.1 修改 `templates/flashcard_synonym.html`：在 `<div class="flashcard__front">` 内部、`flashcard__hint` 之上，新增条件块 `{% if word.chinese %}`
- [x] 3.2 复用现有 ` | ` 分隔逻辑：`{% for line in (word.chinese or '').split(' | ') %}`，每行包裹 `<div class="synonym-front-chinese">{{ line }}</div>`
- [x] 3.3 保持英文/音标/🔊/提示文字的位置与样式不变

## 4. 前端：模板背面 SYNONYMS 列表加中英区分

- [x] 4.1 修改 `templates/flashcard_synonym.html` 背面 `{% for s in syn_list %}` 循环：根据 `{% if s.strip() is has_cjk %}` 给 `meaning-line` 元素附加 `synonym-syn--cn` class
- [x] 4.2 验证：含中文项与不含中文项渲染输出在 class 属性上有差异

## 5. 测试

- [x] 5.1 新增 `tests/test_synonym_card_render.py`：用 Flask test_client GET 同义词卡片页（先准备一个含 chinese 与含 CJK synonym 的词条），断言响应 HTML 含 `synonym-front-chinese` 与 `synonym-syn--cn` class
- [x] 5.2 同测试文件覆盖反向用例：词条 `chinese=''` 时 HTML 不含 `synonym-front-chinese` class
- [x] 5.3 测试 has_cjk 函数：含中文 → True；纯英文 → False；空字符串 → False；混合 → True
- [x] 5.4 跑全部既有测试（≥ 32 个）确保零回归：**41 测试全绿**（32 既有 + 9 新增）

## 6. 文档与验收

- [x] 6.1 更新 `README.md`「功能」段落：在「同义词学习」描述末追加"卡片正反面同步显示中文释义（按词级别自动判断）"
- [ ] 6.2 在 main 分支提交所有改动；commit message: "feat(synonym): 同义词卡片正反面显示中文释义 + SYNONYMS 列表中英分色"
- [ ] 6.3 切到 packaging 分支 merge main，跑 `bash build_mac.sh` 生成新 .app/.dmg
- [ ] 6.4 push packaging 到远端，提示用户在 Win 虚拟机 pull 后 `build_win.bat`
- [x] 6.5 `openspec validate show-chinese-on-synonym-card --strict` 通过
- [ ] 6.6 Mac 实测：导入有中文释义的同义词词库 → 正面看到 14px 灰色中文 → 翻面 → SYNONYMS 中文项灰色，英文项黑色 ✓
- [ ] 6.7 Mac 实测：词条无中文（`chinese=''`）时正面布局与改造前完全一致 ✓
- [ ] 6.8 用户 Win 实测：跨平台行为一致 ✓
