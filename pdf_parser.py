import re
import pdfplumber


# 宽松正则：序号. 单词/词组 英[音标] 剩余内容（含词性和中文）
_ENTRY_RE = re.compile(
    r'^\d+\.\s+'                        # 序号
    r'([a-zA-Z][a-zA-Z\s\-]*?)\s+'     # 英文单词或词组（支持空格和连字符）
    r'英\s*\[.*?\]\s*'                  # 英式音标（宽松匹配）
    r'(.+)$'                            # 剩余内容（词性+中文）
)

# 词性前缀清理：去掉开头的词性标记（保留完整内容作为释义）
_POS_STRIP_RE = re.compile(r'^[a-zA-Z\s\.]+\.\s*')


def _clean_meaning(raw: str) -> str:
    """从词条首行的剩余内容中提取中文释义，去除前置词性标记，保留原始内容"""
    raw = raw.strip()
    # 移除开头的词性标记（如 "adj. "、"v t. "、"n . " 等）
    cleaned = re.sub(r'^[a-zA-Z]+[\s\.]*\s+', '', raw, count=1).strip()
    return cleaned if cleaned else raw


def parse_pdf(filepath: str) -> list[dict]:
    """
    解析 PDF 词表，返回词条列表。
    每条格式：{'english': str, 'chinese': str, 'failed': bool}
    """
    results = []
    seen_nums = set()  # 防止同一序号重复（跨页时偶发）

    try:
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue

                for line in text.split('\n'):
                    line = line.strip()
                    if not line:
                        continue

                    # 检查是否是词条首行（以序号开头）
                    num_match = re.match(r'^(\d+)\.', line)
                    if not num_match:
                        continue

                    num = int(num_match.group(1))
                    if num in seen_nums:
                        continue
                    seen_nums.add(num)

                    m = _ENTRY_RE.match(line)
                    if m:
                        english = m.group(1).strip()
                        meaning_raw = m.group(2).strip()
                        chinese = _clean_meaning(meaning_raw)
                        results.append({
                            'english': english,
                            'chinese': chinese,
                            'failed': False
                        })
                    else:
                        # 解析失败：只知道有序号，但无法提取单词和释义
                        # 尝试至少提取英文单词
                        word_match = re.match(r'^\d+\.\s+([a-zA-Z][a-zA-Z\s\-]*?)(?:\s+英|\s+美|\s*$)', line)
                        english_guess = word_match.group(1).strip() if word_match else ''
                        results.append({
                            'english': english_guess,
                            'chinese': '',
                            'failed': True,
                            'raw': line[:120]  # 保留原始行供用户参考
                        })

    except Exception as e:
        raise RuntimeError(f"PDF 解析失败：{e}")

    return results
