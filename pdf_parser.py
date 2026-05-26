import re
import pdfplumber


# 宽松正则：序号. 单词/词组 [英音标] 词性 剩余内容
_ENTRY_RE = re.compile(
    r'^\d+\.\s+'                        # 序号
    r'([a-zA-Z][a-zA-Z\s\-]*?)\s+'     # 英文单词或词组（支持空格和连字符）
    r'(?:英\s*\[(.*?)(?:\]|$))?'   # 英式音标（可选，允许 PDF 缺少闭合 ]）
    r'\s*'                              # 音标后空格
    r'(.+)$'                            # 剩余内容（词性+中文）
)

# 词性标记完整集合（用于多词性扫描）
_ALL_POS_PATTERN = (
    r'(?:n|v|adj|adv|vt|vi|prep|conj|pron|art|num)'  # 词性词根
    r'(?:\s*&\s*(?:n|v|adj|adv|vt|vi|prep|conj|pron|art|num))?'  # 可选 "&" 连接
    r'\.'                                              # 必须的点号
)

# 单个词性标记的正则（用于 finditer 扫描）
_POS_TAG_RE = re.compile(_ALL_POS_PATTERN)

# 清理前缀中的音标/美式残留
_PHONETIC_RESIDUE_RE = re.compile(r'^(?:英|美)\s*\[.*?\]\s*')

# 断字预修复：PDF 排版引擎在单词中间插入空格（换栏/双栏导致）
_BREAK_FIX_RE = re.compile(
    r'^(\d+\.\s+)'          # 序号前缀
    r'([a-zA-Z]{1,4})'      # 被截断的短前缀
    r'\s+'                   # 不应有的空格
    r'([a-z][a-zA-Z]*)'     # 单词剩余部分
    r'(\s+英\s*\[)'         # 音标标记
)

_BREAK_FIX_RE2 = re.compile(
    r'^(\d+\.\s+)'
    r'([a-zA-Z]{1,4})'
    r'\s+'
    r'([a-z][a-zA-Z]+)'
    r'[^\w]*'
    r'(英\s*\[)'
)

# 兜底：从 meaning_raw 中提取被遗漏的音标（PDF 缺少 ] 或格式异常时）
_EMBEDDED_PHONETIC_RE = re.compile(
    r'^英\s*\['
    r'([^]\n]*?)'
    r'(?:\]\s*|\s+(?=n\.|v\.|adj\.|adv\.))'
)

# 入口级清理：meaning_raw 开头可能包含完整的音标残留
_MEANING_PHONETIC_LEAK_RE = re.compile(
    r'^英\s*\['
    r'[^\]]*'
    r'\)\s*;\s*'
)

# 美式音标续行：以 "美 [" 开头，可能含词性+释义
_US_CONTINUATION_RE = re.compile(
    r'^美\s*\['
    r'[^\]]*'
    r'\]?'
    r'\s+(.+)$'
)

# 续行类型 A: 音标残尾 + ] + 词性 + 释义
# 示例: "əˈdɪkt (for v.)] vt. 使沉溺；使上瘾"
#       "səˈveɪ] vt. 调查；勘测；俯瞰"
# 特征: 含 "]" 且 ] 后面跟词性 + 释义
_PHON_TAIL_POS_RE = re.compile(
    r'^[^\d\n]*?\]\s*'                  # 音标残尾 + ]
    r'(' + _ALL_POS_PATTERN + r')'      # 词性
    r'\s*(.+)$'                         # 释义
)

# 续行类型 B: 纯词性 + 释义（行首直接是词性）
# 示例: "vi. 测量土地"
_PURE_POS_RE = re.compile(
    r'^(' + _ALL_POS_PATTERN + r')'
    r'\s+(.+)$'
)

# 纯音标续行（无释义，应跳过但不阻止扫描）
# 示例: "əˈproprɪet]"  "səˈveɪ]"
_PURE_PHON_RE = re.compile(
    r'^[a-zA-Zəˈˌːɪʊɛɔæɒɑʌəʃʒθðŋ\s\'(),;.\-]+\]?\s*$'
)


def _fix_line_breaks(line: str) -> str:
    """合并 PDF 排版产生的单词内部断字。"""
    fixed = _BREAK_FIX_RE.sub(r'\1\2\3\4', line)
    if fixed != line:
        return fixed
    return _BREAK_FIX_RE2.sub(r'\1\2\3\4', line)


def _extract_embedded_phonetic(meaning_raw: str) -> tuple[str, str]:
    """从 meaning_raw 中提取被主正则遗漏的音标。"""
    m = _EMBEDDED_PHONETIC_RE.match(meaning_raw)
    if m:
        return m.group(1).strip(), meaning_raw[m.end():].strip()
    return '', meaning_raw


def _fix_inter_char_spaces(text: str) -> str:
    """修复 PDF 排版导致的字符间插空。

    PDF 提取的某些行（如 addict 的 vt. 释义续行）会出现：
      "v t . 使 沉 溺 ；使 上 瘾"  ← 字符间被插空格

    修复策略：将"单字符 + 单空格 + 单字符"模式中的空格删除，
    限制条件: 仅压缩 ASCII 单字母 / 中文单字 / 标点之间的单空格。

    注意: 仅在续行处理中调用，不影响主行的英文单词间空格。
    """
    if not text:
        return text
    # 仅当行内出现明显的"字符间插空"模式时才修复
    # 启发式检测: 如果行中含 5+ 个 "X " (单字符+空格) 模式 → 触发修复
    pattern_count = len(re.findall(
        r'(?:^|\s)([a-zA-Z\u4e00-\u9fa5。，；、；])\s', text
    ))
    if pattern_count < 3:
        return text

    # 反复压缩："单字符X + 空格 + 单字符Y" 中的空格
    # 其中 X/Y 可以是: ASCII 字母、中文字、半/全角标点
    char_class = r'[a-zA-Z\u4e00-\u9fa5。，；、…\.;]'
    prev = None
    cur = text
    while prev != cur:
        prev = cur
        cur = re.sub(
            r'(' + char_class + r')\s(' + char_class + r')',
            r'\1\2',
            cur
        )
    return cur


def _strip_meaning_separators(meaning: str) -> str:
    """清理释义片段两端的多余分隔符（&、;、；、空格）。"""
    if not meaning:
        return ''
    meaning = re.sub(r'^[\s&；;,，]+', '', meaning)
    meaning = re.sub(r'[\s&；;,，]+$', '', meaning)
    return meaning.strip()


def _normalize_pos_key(pos_tag: str) -> str:
    """将词性标记归一化为查重键。

    "vt. & vi." → "vtvi"
    "n." → "n"
    """
    return pos_tag.replace(' ', '').replace('&', '').replace('.', '').lower()


def _split_combined_pos(pos_tag: str) -> list[str]:
    """将 "vt. & vi." 拆分为 ["vt.", "vi."]，单词性原样返回。"""
    parts = re.split(r'\s*&\s*', pos_tag)
    result = []
    for p in parts:
        p = p.strip()
        if p and not p.endswith('.'):
            p += '.'
        if p:
            result.append(p)
    return result if len(result) > 1 else [pos_tag]


def _extract_meanings(raw: str) -> list[tuple[str, str]]:
    """从单行内容提取所有 (pos, chinese) 对。

    支持格式：
      - 单词性: "n. 蛋白质" → [("n.", "蛋白质")]
      - 多词性: "adj. 复杂的 n. 情结" → [("adj.","复杂的"), ("n.","情结")]
      - & 连接: "vt. & vi. 计算" → [("vt.","计算"), ("vi.","计算")]
      - 紧贴 & : "n.&v. 摆动" → [("n.","摆动"), ("v.","摆动")]

    返回: list[(pos, chinese)]，可能为空列表（无释义内容）
    """
    raw = raw.strip()
    if not raw:
        return []

    # 清理开头的音标/美式残留
    cleaned = _PHONETIC_RESIDUE_RE.sub('', raw).strip()
    if not cleaned:
        return []

    # 找出所有词性标记的位置
    pos_matches = list(_POS_TAG_RE.finditer(cleaned))

    if not pos_matches:
        # 没有词性标记 — 整段视为无词性的释义
        return [('', cleaned)]

    # === 预处理: 识别 "& 连接" 的相邻词性 ===
    # 当两个相邻 pos 之间只有空格和 & 时（无释义内容），视为同一释义的双词性组
    # 例: "vt. & vi. 计算" 或 "n.&v. 摆动"
    # 处理方式: 把它们合并到一个 group，共享后续释义
    pos_groups = []  # list[list[match]] — 每个内层 list 共享同一释义
    i = 0
    while i < len(pos_matches):
        group = [pos_matches[i]]
        # 向后看：如果下一个 pos 紧邻（中间只有空格/&），加入同一组
        while i + 1 < len(pos_matches):
            gap_start = pos_matches[i].end()
            gap_end = pos_matches[i + 1].start()
            gap = cleaned[gap_start:gap_end]
            # gap 只能是空格、&、或两者组合
            if re.match(r'^\s*&\s*$', gap):
                group.append(pos_matches[i + 1])
                i += 1
            else:
                break
        pos_groups.append(group)
        i += 1

    # === 按组提取 (pos, chinese) ===
    meanings = []
    for gi, group in enumerate(pos_groups):
        # 该组共享的释义范围
        start = group[-1].end()
        end = pos_groups[gi + 1][0].start() if gi + 1 < len(pos_groups) else len(cleaned)
        meaning = _strip_meaning_separators(cleaned[start:end])

        # 组内每个词性都共享这个释义
        for m in group:
            pos_tag = m.group().strip()
            # 拆分嵌入 & 的组合（如单 match "n.&v." 整体匹配时）
            pos_parts = _split_combined_pos(pos_tag)
            for p in pos_parts:
                meanings.append((p, meaning))

    return meanings


def _merge_meanings(
    base: list[tuple[str, str]],
    new_items: list[tuple[str, str]]
) -> list[tuple[str, str]]:
    """将新 (pos, chinese) 对合并到 base，同词性追加，新词性新增。"""
    # 构建 base 的 pos_key 索引
    pos_index = {_normalize_pos_key(p): idx for idx, (p, _) in enumerate(base) if p}

    for pos, chi in new_items:
        if not pos:
            # 无词性的释义 — 如果 base 最后一项有空释义则填充
            if base and not base[-1][1] and chi:
                base[-1] = (base[-1][0], chi)
            continue

        key = _normalize_pos_key(pos)
        if key in pos_index:
            # 同词性合并释义
            idx = pos_index[key]
            old_pos, old_chi = base[idx]
            if chi:
                if old_chi:
                    base[idx] = (old_pos, old_chi + '; ' + chi)
                else:
                    base[idx] = (old_pos, chi)
        else:
            # 新词性
            base.append((pos, chi))
            pos_index[key] = len(base) - 1

    return base


def _serialize_meanings(meanings: list[tuple[str, str]]) -> tuple[str, str]:
    """将 meanings 列表序列化为 (pos_str, chinese_str)。

    模型 C 格式：
      pos_str: "n.; vt."  (用 "; " 拼接所有词性)
      chinese_str: "n. 学徒，徒弟; 新手 | vt. 使…做学徒"  (词性内联)

    空释义条目自动忽略。
    相邻词性若共享相同释义，合并展示为 "n.; vt. 释义"（避免冗余）。
    """
    # 过滤空释义条目
    valid = [(p, c) for p, c in meanings if c]

    if not valid:
        unpoxed = [c for p, c in meanings if not p and c]
        if unpoxed:
            return ('', '; '.join(unpoxed))
        return ('', '')

    # 处理无词性的条目
    has_pos = [(p, c) for p, c in valid if p]
    no_pos = [c for p, c in valid if not p]

    if not has_pos and no_pos:
        return ('', '; '.join(no_pos))

    if no_pos and has_pos:
        first_pos, first_chi = has_pos[0]
        has_pos[0] = (
            first_pos,
            first_chi + '; ' + '; '.join(no_pos) if first_chi else '; '.join(no_pos)
        )

    # === 合并相邻同释义条目 ===
    # 例: [('vt.', '计算'), ('vi.', '计算')] → [('vt.; vi.', '计算')]
    # 这种情况源于 "vt. & vi. 计算" 格式
    merged = []
    for pos, chi in has_pos:
        if merged and merged[-1][1] == chi:
            # 与上一个释义相同 → 合并 pos
            prev_pos, _ = merged[-1]
            merged[-1] = (f'{prev_pos}; {pos}', chi)
        else:
            merged.append((pos, chi))

    pos_str = '; '.join(p for p, _ in merged)
    chinese_str = ' | '.join(f'{p} {c}' for p, c in merged)
    return (pos_str, chinese_str)


def _try_phon_tail_pos(line: str) -> list[tuple[str, str]] | None:
    """尝试匹配续行类型 A: 音标残尾 + ] + 词性 + 释义。"""
    # 先做字符间空格修复
    fixed = _fix_inter_char_spaces(line)
    m = _PHON_TAIL_POS_RE.match(fixed)
    if not m:
        return None
    pos = m.group(1).strip()
    rest = m.group(2).strip()
    return _extract_meanings(f'{pos} {rest}')


def _try_pure_pos(line: str) -> list[tuple[str, str]] | None:
    """尝试匹配续行类型 B: 纯词性 + 释义。"""
    fixed = _fix_inter_char_spaces(line)
    m = _PURE_POS_RE.match(fixed)
    if not m:
        return None
    return _extract_meanings(fixed)


def _try_us_continuation(line: str) -> list[tuple[str, str]] | None:
    """尝试匹配续行类型 C: 美式音标续行。"""
    m = _US_CONTINUATION_RE.match(line)
    if not m:
        return None
    rest = m.group(1).strip()
    if not rest:
        return []  # 空续行，跳过但不停止扫描
    return _extract_meanings(rest)


def _is_pure_phonetic(line: str) -> bool:
    """判断是否为纯音标续行（无中文释义）。

    特征:
      - 不含真正的中文释义（"英""美"标签字不算）
      - 或含 (for xxx.) 这种 PDF 特有的音标注释模式
    """
    if not line.strip():
        return False
    # 含真正中文释义 → 不是纯音标
    if _has_chinese(line):
        return False
    # 不含中文 → 几乎肯定是音标续行
    # 进一步确认：含 [ 或 ] 或 (for xxx.) 等音标特征
    s = line.strip()
    if '[' in s or ']' in s or re.search(r'\(for\s+[a-z]+\.', s):
        return True
    # 否则用原始字符类规则
    return bool(_PURE_PHON_RE.match(s))


def _has_chinese(text: str) -> bool:
    """判断文本是否含中文释义内容（排除"英""美"标签和标点）。"""
    # 移除已知的非释义中文：英、美 (音标标签)
    cleaned = re.sub(r'[英美]', '', text)
    return bool(re.search(r'[\u4e00-\u9fa5]', cleaned))


def _process_main_line(
    meaning_raw: str, phonetic: str
) -> tuple[list[tuple[str, str]], str]:
    """处理词条主行 meaning_raw，返回 (meanings, phonetic)。

    包含音标泄漏清理、(for xxx.) 处理。
    """
    # === 音标泄漏清理 ===
    if not phonetic and (meaning_raw.startswith('英 [') or meaning_raw.startswith('英[')):
        # 优先级 1: ");" 结尾的泄漏（如 "(for n.); "）
        leak_m = _MEANING_PHONETIC_LEAK_RE.match(meaning_raw)
        if leak_m:
            leaked = leak_m.group(0).strip()
            inner = re.sub(r'^英\s*\[', '', leaked)
            inner = re.sub(r'\)\s*;.*$', '', inner).strip()
            phonetic = inner
            meaning_raw = meaning_raw[leak_m.end():].strip()
        else:
            # 优先级 2a: "英 [phon; (for v.) " 这种带闭合 ) 的注释
            # 关键点: (for v.) 中的 v. 不是主行词性（真正的 v. 释义在续行中）
            # 处理: 整段 "英 [...; (for v.) " 作为前缀剥离，但保留音标主体
            for_closed = re.match(
                r'^(英\s*\[)'
                r'([^;]+)'                  # 音标主体（到第一个;）
                r';\s*'
                r'\(for\s+[a-z]+\.\)\s*',   # (for v.) 注释（带闭合括号）
                meaning_raw
            )
            if for_closed:
                phonetic = for_closed.group(2).strip()
                meaning_raw = meaning_raw[for_closed.end():].strip()
            else:
                # 优先级 2b: "(for adj." 等无闭合括号的注释
                # 这种情况下 adj. 是该条目的有效词性
                for_with_pos = re.match(
                    r'^(英\s*\[)'
                    r'(.*?)'
                    r'\(for\s+([a-z]+\.)'   # 捕获 (for xxx.) 中的词性
                    r'\s*',
                    meaning_raw
                )
                if for_with_pos:
                    phonetic = for_with_pos.group(2).strip()
                    extracted_pos = for_with_pos.group(3).strip()
                    rest = meaning_raw[for_with_pos.end():].strip()
                    meaning_raw = f'{extracted_pos} {rest}'
                else:
                    # 兜底：去掉整个 "英 [..." 前缀
                    meaning_raw = re.sub(r'^英\s*\[[^\]]*\]?\s*', '', meaning_raw).strip()

    # === 嵌入式音标提取 ===
    if not phonetic and meaning_raw:
        embedded_phonetic, meaning_raw = _extract_embedded_phonetic(meaning_raw)
        if embedded_phonetic:
            phonetic = embedded_phonetic

    # === 提取 meanings ===
    meanings = _extract_meanings(meaning_raw)

    # === 兜底清理: 释义中残留的 ")" 字符 ===
    cleaned = []
    for pos, chi in meanings:
        chi = re.sub(r'^[\)\;\s]+', '', chi)
        chi = re.sub(r'[\)\;\s]+$', '', chi)
        cleaned.append((pos, chi))
    return cleaned, phonetic


def parse_pdf(filepath: str) -> list[dict]:
    """解析 PDF 词表，返回词条列表。

    每条格式：{
        'english': str,
        'chinese': str,    # 模型 C 格式: "n. xxx | vt. yyy"
        'phonetic': str,
        'pos': str,        # "n.; vt."
        'failed': bool
    }
    """
    results = []
    seen_nums = set()

    try:
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue

                lines = text.split('\n')
                i = 0
                while i < len(lines):
                    line = lines[i].strip()
                    i += 1
                    if not line:
                        continue

                    num_match = re.match(r'^(\d+)\.', line)
                    if not num_match:
                        continue

                    num = int(num_match.group(1))
                    if num in seen_nums:
                        continue
                    seen_nums.add(num)

                    line = _fix_line_breaks(line)
                    m = _ENTRY_RE.match(line)

                    if m:
                        english = re.sub(r'\s+', ' ', m.group(1).strip())
                        phonetic = (m.group(2) or '').strip()
                        meaning_raw = m.group(3).strip()

                        meanings, phonetic = _process_main_line(meaning_raw, phonetic)

                        # === 续行扫描 ===
                        while i < len(lines):
                            cont_line = lines[i].strip()
                            if not cont_line:
                                i += 1
                                continue
                            # 遇到下一个序号 → 停止
                            if re.match(r'^\d+\.', cont_line):
                                break

                            # 优先级 1: 纯音标续行（无中文）→ 跳过但继续扫描
                            # 必须在所有"词性+释义"识别之前判断，避免误把 (for v.) 中的 v. 当词性
                            if _is_pure_phonetic(cont_line):
                                i += 1
                                continue

                            # 字符间空格修复（仅对续行使用）
                            cont_fixed = _fix_inter_char_spaces(cont_line)

                            extra = None
                            # 类型 C: 美式音标续行
                            if cont_fixed.startswith('美 [') or cont_fixed.startswith('美['):
                                # 美式音标后必须有中文才算"释义续行"
                                # 否则视为纯音标行已被前面跳过
                                if _has_chinese(cont_fixed):
                                    extra = _try_us_continuation(cont_fixed)
                                else:
                                    i += 1
                                    continue
                            # 类型 A: 音标残尾 + ] + 词性 + 释义
                            elif ']' in cont_fixed and re.search(
                                r'\]\s*' + _ALL_POS_PATTERN, cont_fixed
                            ) and _has_chinese(cont_fixed):
                                extra = _try_phon_tail_pos(cont_fixed)
                            # 类型 B: 纯词性 + 释义
                            elif _PURE_POS_RE.match(cont_fixed) and _has_chinese(cont_fixed):
                                extra = _try_pure_pos(cont_fixed)
                            else:
                                # 不认识的内容 — 停止扫描
                                break

                            if extra is None:
                                break

                            if extra:  # 非空才合并
                                meanings = _merge_meanings(meanings, extra)
                            i += 1

                        # 序列化输出
                        pos, chinese = _serialize_meanings(meanings)

                        results.append({
                            'english': english,
                            'chinese': chinese,
                            'phonetic': phonetic,
                            'pos': pos,
                            'failed': False
                        })
                    else:
                        word_match = re.match(
                            r'^\d+\.\s+([a-zA-Z][a-zA-Z\s\-]*?)(?:\s+英|\s+美|\s*$)',
                            line
                        )
                        english_guess = re.sub(r'\s+', ' ', word_match.group(1).strip()) if word_match else ''
                        results.append({
                            'english': english_guess,
                            'chinese': '',
                            'phonetic': '',
                            'pos': '',
                            'failed': True,
                            'raw': line[:120]
                        })

    except Exception as e:
        raise RuntimeError(f"PDF 解析失败：{e}")

    return results
