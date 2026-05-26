# 设计文档

## Context

`templates/flashcard.html` 当前用单一 `flipped` 布尔锁死翻转方向，导致用户无法翻回正面。问题源于早期"翻面 = 进入完成态"的隐含假设。

实际上"翻面"和"准备下一题"是两件事：
- 翻面 = UI 状态（正/背面）
- 准备下一题 = 学习进度（是否看过释义）

## Goals / Non-Goals

### Goals
- 用户可以无限次翻转卡片
- "下一张"按钮的出现时机不变（首次翻到背面后）
- 一旦出现，"下一张"按钮不再消失（避免反复横跳）

### Non-Goals
- 不改翻转动画
- 不改键盘快捷键的语义
- 不引入"标记已掌握/未掌握"等学习信号

## Key Decisions

### Decision 1: 双状态变量替代单一 flipped

**问题**：当前 `flipped` 既表示"当前面"又表示"是否完成"，两个语义纠缠。

**决定**：拆为两个独立状态：
- `isBack: boolean` — 当前是否在背面（UI 状态，每次 flip 切换）
- `everFlipped: boolean` — 是否曾经翻到过背面（学习进度，一旦 true 永不重置）

```javascript
function flip() {
  isBack = !isBack;
  card.classList.toggle('flipped', isBack);
  if (!everFlipped && isBack) {
    everFlipped = true;
    nextWrap.style.display = 'block';
  }
}
```

### Decision 2: "下一张"按钮常驻策略

**问题**：用户翻回正面时是否要隐藏"下一张"按钮？

**选项**：
- A. 隐藏（"下一张"严格跟随背面状态）
- B. 常驻（一旦显示就不消失）

**决定**：**B 常驻**。

**理由**：
- 用户在"已经看过释义"的认知下，按钮消失反而像 bug
- 学习场景下常见的操作序列：翻面看释义 → 翻回正面再确认 → 点"下一张"——按钮消失会打断这个流
- 视觉上多一个按钮的成本远小于体验断裂的成本

### Decision 3: 提示文案动态切换

**决定**：原有的 `点击查看释义` 提示在背面时切换为 `点击返回正面`，让"可以再翻回去"的能力**可发现**。

如果不切换文案，用户可能不知道还能翻回去——这是默认行为变更后必须配的引导。

### Decision 4: ArrowRight 快捷键条件

**问题**：原 `if (ArrowRight && flipped)` 中的 `flipped` 在新语义下指的是什么？

**决定**：替换为 `everFlipped`。

**理由**：
- 原意是"翻过才能去下一张"，防止用户跳过释义
- 新逻辑下，用户可能"翻面 → 翻回正面 → 按 →"，此时 `isBack=false` 但 `everFlipped=true`，仍应允许进入下一张
- 用 `everFlipped` 准确表达了"翻过即可"的原意

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 用户习惯了"翻一次就结束"，新行为打乱节奏 | 提示文案明示当前态，过渡平滑 |
| 反复翻转可能让 CSS 动画卡顿 | 现有 transition 已有 0.5s，再点击自然中断重排，无累积副作用 |
| `everFlipped` 名字稍长 | 接受；可读性优于过度缩写 |

## Migration Plan

无数据/接口变更，纯前端模板内 JS 改动。用户下次访问卡片页时（强制刷新一次绕过缓存）即可体验新行为。

## Open Questions

无。
