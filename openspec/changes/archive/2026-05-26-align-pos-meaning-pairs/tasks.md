# Tasks: 对齐词性与释义

## Phase 1: 解析器重构

- [x] 1.1 在 `pdf_parser.py` 中重写 `_clean_meaning()` 返回 `list[(pos, chi)]`
- [x] 1.2 新增 `_serialize_meanings(meanings)` 工具函数：输出 `(pos_str, chinese_str)` 元组
  - `pos_str = "; ".join(p)`、`chinese_str = " | ".join(f"{p} {c}" for p,c in meanings)`
- [x] 1.3 单词性也加前缀（统一格式）
- [x] 1.4 空释义条目过滤逻辑

## Phase 2: PDF 解析增强

- [x] 2.1 实现"续行类型 A"识别（音标残尾 + 词性释义）
- [x] 2.2 实现"续行类型 B"识别（纯词性释义续行）
- [x] 2.3 实现 `(for xxx.)` 中词性提取（修复 appropriate）
- [x] 2.4 实现字符间空格修复（修复 addict 的 "v t ."）
- [x] 2.5 整合所有续行类型到 parse_pdf 主循环

## Phase 3: 前端模板修改

- [x] 3.1 找出所有展示 `word.chinese` 的模板
- [x] 3.2 改为按 ` | ` split 后按行渲染
- [x] 3.3 添加最小化 CSS 样式

## Phase 4: 验证

- [x] 4.1 验证关键样本：addict / appropriate / survey / apprentice / calculate / auction
- [x] 4.2 全量回归 1422 条无退化
- [x] 4.3 多词性条目数量 ≥121（实际 264，提升 24x）
- [x] 4.4 重启应用并请用户重新导入验证视觉效果

## Phase 5: 清理

- [x] 5.1 删除调试临时文件
- [x] 5.2 lint 检查 0 错误

## Phase 6: 额外改进（探索阶段触发）

- [x] 6.1 翻卡正面增加音标展示（学习体验优化）
