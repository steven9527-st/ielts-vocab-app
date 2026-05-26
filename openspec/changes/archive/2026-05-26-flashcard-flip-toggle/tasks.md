# 任务清单

本 change 为已落地的 hotfix（在 propose 之前已完成实现），任务清单作为补登记。

---

## Phase 1: 实现

- [x] 1.1 修改 `templates/flashcard.html` 的 `<script>` 块：
  - [x] 删除单一 `flipped` 布尔标记
  - [x] 新增 `isBack` 与 `everFlipped` 两个状态变量
  - [x] `flip()` 函数改为 toggle 行为
  - [x] "下一张"按钮首次显示后常驻
  - [x] 提示文案随状态切换（"点击查看释义" ↔ "点击返回正面"）
  - [x] ArrowRight 快捷键条件从 `flipped` 改为 `everFlipped`
- [x] 1.2 保留 🔊 发音按钮的 `stopPropagation` 阻止冒泡

## Phase 2: 验证

- [x] 2.1 浏览器实测：反复点击卡片可正反切换
- [x] 2.2 浏览器实测：Space 键多次按可反复翻转
- [x] 2.3 浏览器实测：首次翻到背面 → "下一张"按钮出现 → 翻回正面 → 按钮仍在
- [x] 2.4 浏览器实测：点 🔊 按钮不会触发翻转
- [x] 2.5 `openspec validate flashcard-flip-toggle --strict` 通过
