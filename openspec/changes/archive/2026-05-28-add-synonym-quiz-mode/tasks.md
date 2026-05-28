## 1. 数据库 schema 与迁移

- [x] 1.1 修改 `database.py` 的 `CREATE TABLE word_lists` 加 `type TEXT NOT NULL DEFAULT 'standard'` 字段
- [x] 1.2 在 `init_db()` 内幂等 `ALTER TABLE word_lists ADD COLUMN type TEXT NOT NULL DEFAULT 'standard'`，try/except 吞 duplicate column 错误
- [x] 1.3 新增 `_migrate_word_list_types(conn)` 函数：扫描 `type IS NULL OR type = 'standard'` 的词库，按 synonyms 填充率 ≥ 80% 标 `'synonym'`，否则保持 `'standard'`
- [x] 1.4 在 `init_db()` 末尾调用 `_migrate_word_list_types(conn)` 实现首次启动自动迁移
- [x] 1.5 单元自测：`python3 -c "from database import init_db, get_db; init_db(); db=get_db(); print([r[1] for r in db.execute('PRAGMA table_info(word_lists)').fetchall()])"` 确认列名包含 type

## 2. 导入路由写入 type

- [x] 2.1 修改 `app.py` `/import/excel_apply` 路由：在持久化 import_mode 到 session
- [x] 2.2 修改 `app.py` `/import/confirm` 路由：根据 session 的 import_mode 写入 type 字段；末尾清理 session
- [x] 2.3 验证：标准模式导入 → 词库 type 字段为 'standard'；同义词模式导入（含双英文列）→ type 为 'synonym'

## 3. 测验出题分支

- [x] 3.1 修改 `app.py` `generate_quiz_questions()`：增加 `list_type: str = 'standard'` 参数；按 list_type 决定 SELECT 列与出题方式
- [x] 3.2 实现 synonym 分支：从 other_words 的 synonyms 中采集 3 个不重复的干扰项 + 正确答案 = 4 个英文选项
- [x] 3.3 在 `generate_quiz_questions()` 主循环里：若 `list_type == 'synonym'` 且词库内有同义词的词数 ≥ 4，走新逻辑；否则降级原逻辑（含本题级降级）
- [x] 3.4 新增 `_get_list_type(list_id)` 工具函数；修改 `learn_quiz` / `test_start` / `quiz_retry` 调用处先查 type
- [x] 3.5 听力测试豁免：`test_type == 'audio'` 时强制 `list_type='standard'`

## 4. 测试

- [x] 4.1 新增 `tests/test_synonym_quiz.py` 测试 `_migrate_word_list_types`：填充率 100%/80%/79%/0% 的词库正确分类，已显式标 synonym 不被覆盖，空词库跳过
- [x] 4.2 测试 `_get_list_type`：existing/missing/None 都正确返回
- [x] 4.3 测试 `generate_quiz_questions(list_type='synonym')` 输出：选项均为英文、正确答案是 synonyms、4 个选项互不相同
- [x] 4.4 测试干扰项不足时本题级降级：仅有 1 个唯一同义词时，降级到中文选项
- [x] 4.5 测试 `list_type='standard'` 时维持原中文逻辑（含默认值兜底）
- [x] 4.6 测试无 synonyms 的词在 synonym 模式下被跳过
- [x] 4.7 跑全部既有测试（≥ 56 个）确保零回归：**72 测试全绿**（56 既有 + 16 新增）

## 5. 文档与归档

- [x] 5.1 更新 `README.md`「学习测验」与「测试模式」描述：补充"同义词词库自动用英文同义词作为选项"
- [ ] 5.2 在 main 分支提交所有改动；commit message: "feat(quiz): 同义词词库测验自动用英文同义词作为选项"
- [ ] 5.3 切到 packaging 分支 merge main，跑 `bash build_mac.sh` 生成新 .app/.dmg
- [ ] 5.4 push packaging 到远端
- [x] 5.5 `openspec validate add-synonym-quiz-mode --strict` 通过
- [ ] 5.6 `openspec archive add-synonym-quiz-mode -y` 归档
- [ ] 5.7 Mac 实测：用 C19 同义词词库进学习测验 → 选项是英文同义词 ✓
- [ ] 5.8 Mac 实测：用标准词库（雅思 3500）进测验 → 选项仍是中文 ✓（向后兼容）
- [ ] 5.9 Mac 实测：用 C19 词库进听力测试 → 选项是中文（豁免生效）✓
- [ ] 5.10 用户 Win 实测：跨平台行为一致 ✓
