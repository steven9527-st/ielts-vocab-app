## 1. 后端选词逻辑修改

- [ ] 1.1 `learn_start()` 改为 `UNION` 查询：先查 unmastered，不足再补 mastered
- [ ] 1.2 `learn_setup()` 的 `default_n` 计算改为 `min(20, max(stats.unmastered, stats.total))`

## 2. 前端修复

- [ ] 2.1 `index.html` 移除 `stats.unmastered == 0` 时禁用按钮的条件分支
- [ ] 2.2 `learn_setup.html` 的 `max` 绑定改为 `max(stats.unmastered, 1)` 或 `stats.total` 兜底
- [ ] 2.3 `learn_setup.html` 前端 JS 中的 `max` 同步修改

## 3. 测试

- [ ] 3.1 测试全部掌握后学习按钮可用
- [ ] 3.2 测试全部掌握后选词来自全词库
- [ ] 3.3 测试部分掌握时仍优先选 unmastered
