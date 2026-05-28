## Context

`templates/flashcard_synonym.html` 当前的渲染规则：

```
┌──────────────────────────────────────────────────────────┐
│  现状（背面已有中文，正面没有）                          │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  正面（front）            背面（back）                   │
│  ┌────────────────┐      ┌────────────────────┐         │
│  │ english 24px   │      │ SYNONYMS (12px灰)  │         │
│  │ phonetic + 🔊  │      │ plight  24px       │         │
│  │ "点击查看同义词"│      │ catastrophe        │         │
│  │                │      │ ──────────         │         │
│  │ ❌ 无中文       │      │ chinese 13px 灰底  │         │
│  └────────────────┘      └────────────────────┘         │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

需求三件事：
1. 正面有 chinese 时新增灰色 14px 中文行
2. SYNONYMS 列表中识别夹杂的中文项给灰色样式
3. 背面底部已有的中文释义块保持原样不动

## Goals / Non-Goals

**Goals:**

- `word.chinese` 非空时正面显示中文，与背面已有中文形成"双面可见"配角姿态
- SYNONYMS 列表内中文/英文项视觉区分，方便用户快速识别同义词主体
- 纯前端改动，零后端、零数据迁移、零回归

**Non-Goals:**

- 不调整背面已有的"底部中文释义块"位置/字号
- 不改变正面英文/音标/🔊 主体的样式
- 不新增「设置开关」让用户配置中文是否显示——按词级别自动判断
- 不引入字段级标记（不要求导入时把"中文同义词"另存一列）——通过 CJK 字符检测推断

## Decisions

### 决策 1：用 Jinja 过滤器或 macro 实现 CJK 字符检测

**选择**：在模板内用 Jinja 内置 `match` / 简单字符判断处理；不引入 Python helper。

**为什么**：

| 方案 | 优点 | 缺点 |
|---|---|---|
| A. 模板内用正则字符判断 ✅ | 零后端改动；本地计算简单 | Jinja 表达式略繁琐 |
| B. 加 `app.py` jinja filter `is_chinese` | 复用方便 | 引入跨层依赖；本次只一个模板用 |
| C. 后端预处理 word.synonyms → 拆分中英文两个列表 | 模板最干净 | 改后端、违反"纯前端"目标；Lazy 兼容性差 |

方案 A 满足"纯前端"约束。具体实现用 `s|select('match', '[\u4e00-\u9fff]')` 这类不可行（select 用于 list），改为字符串包含判断：

```jinja
{% set has_cjk = s.strip() | reject('in', 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ,.;:-/()') | list | length > 0 %}
```

**简化方案**：用 Python 字符串方法 + Jinja test 的组合在模板内判断"包含任意 CJK 字符"。
最实用做法：直接遍历字符串字符，检查 ord 是否在 CJK 范围 `[0x4E00, 0x9FFF]`，但 Jinja 不直接暴露 `ord()`。

**最终落地**：在模板内用一个 inline macro 遍历字符判断（Jinja 支持 `string|length` 与切片），或用 `'[\u4e00-\u9fff]' in s` 这类判断——但 Jinja 对 Unicode 字面量支持不完美。

**所以决定改回方案 B 的轻量版**：在 `app.py` 已有的 jinja_env 上注册一个 `has_cjk(s)` 测试函数（非 filter），仅 5 行代码，本次只这一个模板用，未来可扩展。这是工程上"纯前端 vs 干净实现"的合理折中。

### 决策 2：CJK 范围只判断"有无"，不区分中日韩

**选择**：用 `0x4E00-0x9FFF`（CJK Unified Ideographs 主区段）覆盖中文常用字。即使句子里只有 1 个中文字符也判定为"中文项"。

**为什么**：本应用是中文用户用的英文学习工具，"出现 CJK 字符" ≈ "出现中文释义"，不会误伤纯英文。简单且可靠。

### 决策 3：正面中文样式

**选择**：

```css
.synonym-front-chinese {
  margin-top: 12px;
  font-size: 14px;
  color: var(--clr-text-muted);
  line-height: 1.5;
  max-width: 90%;
  text-align: center;
}
```

位置：放在音标行下方、`flashcard__hint` 上方（"点击查看同义词"提示文字保留）。多义项继承现有 ` | ` 分隔符逻辑（与普通翻卡一致）。

### 决策 4：SYNONYMS 列表中文项的样式

**选择**：

```css
.synonym-syn--cn {
  color: var(--clr-text-muted);
  font-weight: 400;  /* 主项是 500 加粗 */
}
```

`<div class="meaning-line synonym-syn--cn">折磨</div>`——视觉与英文同义词区分但仍在同一字号同一对齐，避免破坏布局。

### 决策 5：触发条件按词级别判断

**选择**：每张卡片独立判断，模板里 `{% if word.chinese %}` 控制正面中文条；`{% for s in syn_list %}` 内 `{% if s|has_cjk %}` 控制是否加 cn class。

**为什么**：用户的词库可能混合——有些词带中文释义，有些不带。按词判断最直观，零配置。

## Risks / Trade-offs

- **风险 1：has_cjk 误判** → CJK 范围已限定主区段，不会误判英文/数字/标点。即使误判，影响也只是颜色变浅，无功能性损失
- **风险 2：长中文释义在小屏挤压版式** → CSS 加 `max-width: 90%` + `text-align: center` + `line-height: 1.5` 可控；如有 360px 以下屏幕用户反馈再调
- **风险 3：模板混乱** → 改动局限于一个模板的两处条件渲染，可读性可控；diff 行数预计 < 30 行
- **Trade-off：has_cjk 注册到 jinja_env** vs **纯模板实现** → 选了前者（更干净），代价是引入一个跨层小函数。可接受。

## Migration Plan

1. 加 `has_cjk` jinja test 注册：`app.py` 新增几行
2. 改 `flashcard_synonym.html`：两处条件渲染
3. 加 CSS：两个 class
4. 测试：1 个模板渲染单测，验证 chinese 有/无 时输出差异

无数据迁移；无回滚风险（旧用户首次访问加载新模板，立即生效）。
