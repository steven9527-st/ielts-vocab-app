## 1. 后端：词库类型扩展

- [x] 1.1 `_get_list_type()` 白名单扩展：加入 `'dictation'`
- [x] 1.2 `import_excel_apply` 支持 `import_mode='dictation'`
- [x] 1.3 `import_confirm` 支持创建 `type='dictation'` 词库

## 2. 后端：默写学习路由

- [x] 2.1 新增 `GET /learn/dictation/setup` — 默写学习设置页
- [x] 2.2 新增 `POST /learn/dictation/start` — 开始默写学习（选词、初始化 session）
- [x] 2.3 新增 `GET /learn/dictation/card` — 默写翻卡页面（游标模型）
- [x] 2.4 新增 `POST /learn/dictation/next` — 下一张
- [x] 2.5 新增 `POST /learn/dictation/prev` — 上一张
- [x] 2.6 新增 `POST /learn/dictation/abandon` — 放弃默写学习
- [x] 2.7 新增 `GET /learn/dictation/done` — 默写完成页
- [x] 2.8 新增 `_dictation_enter_quiz_or_done()` — 学完最后一张后跳测验决策

## 3. 前端：模板

- [x] 3.1 新建 `learn_dictation_setup.html` — 默写学习设置页（复用 learn_setup 结构）
- [x] 3.2 新建 `flashcard_dictation.html` — 默写翻卡模板（正面中文、背面英文）
- [x] 3.3 新建 `flashcard_dictation_done.html` — 默写完成页
- [x] 3.4 修改 `import_excel_mapping.html` — 导入模式新增"默写词库"选项
- [x] 3.5 修改 `index.html` — 默写词库显示"默写学习"入口

## 4. 测试

- [x] 4.1 新增默写学习流集成测试（setup → start → card → next/prev → quiz → done）
- [x] 4.2 新增默写词库导入测试（Excel 导入选 dictation 类型）
- [x] 4.3 验证默写词库在首页 stats 和词库管理页正常展示
