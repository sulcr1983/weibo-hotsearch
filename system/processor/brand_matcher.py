"""Brand matcher - FIXED V4.4: relaxed boundary check"""
import re
from typing import Optional, Tuple

from v2.constants import BRAND_REGEX

_HTML_TAG_RE = re.compile(r'<[^>]+>')
_FINANCIAL_RE = re.compile(
    r'(涨超|跌超|涨逾|跌逾|涨近|跌近|涨破|跌破|盘前|盘后|收盘|开盘|'
    r'恒指|恒生|港股|美股|\d+%|涨停|跌停|中概股|股指|大盘|'
    r'收涨|收跌|纳指|道指|标普|A股|沪指|深成指|创业板|科创板|'
    r'快讯|截至发稿|异动|拉升|下挫|走强|走弱)',
    re.IGNORECASE
)

_DIGEST_RE = re.compile(
    r'(晨报|晚报|周报|日报|汇总|盘点|解读|前瞻|一周|月报|'
    r'新闻精选|行业速览|快讯合集|一周车闻|车圈情报局)',
    re.IGNORECASE
)

_UGC_RE = re.compile(
    r'(\d+天前|触角说|电车网界|车图腾|车主指南|汽车之家说|懂车帝说|'
    r'车友圈|论坛|帖子|发帖)',
    re.IGNORECASE
)

_OPINION_RE = re.compile(
    r'(还有什么是真的|离他的|离她的|梦还有多远|泼脏水|'
    r'一地鸡毛|裸泳|遮羞布|遮不住了|真的假的)',
    re.IGNORECASE
)


def strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub('', text).strip()


def is_financial_brief(title: str, content: str = '') -> bool:
    combined = title + ' ' + (content or '')[:300]
    matches = _FINANCIAL_RE.findall(combined)
    if len(matches) >= 3 or (len(title) < 30 and len(matches) >= 2):
        return True
    if '涨超' in combined and '跌超' in combined:
        return True
    return False


def is_digest(title: str) -> bool:
    return bool(_DIGEST_RE.search(title))


def is_ugc(title: str) -> bool:
    return bool(_UGC_RE.search(title))


def is_opinion(title: str, source: str = '') -> bool:
    if source in ('虎嗅',):
        return bool(_OPINION_RE.search(title))
    return False


def match_brand(title: str, content: str = '') -> Tuple[Optional[str], Optional[str]]:
    """Match brand keywords in title/content. Returns (brand_name, matched_keyword)."""
    clean = strip_html(title)
    for brand, regex in BRAND_REGEX.items():
        m = regex.search(clean)
        if m:
            matched = m.group(0)
            if _is_valid_brand_hit(clean, matched, m.start(), m.end()):
                return brand, matched
    if content:
        snippet = strip_html(content)[:200]
        for brand, regex in BRAND_REGEX.items():
            m = regex.search(snippet)
            if m:
                matched = m.group(0)
                if _is_valid_brand_hit(snippet, matched, m.start(), m.end()):
                    return brand, matched
    return None, None


def _is_valid_brand_hit(text: str, matched: str, start: int, end: int) -> bool:
    """Validate brand match - only block clear false positives.
    
    V4.4 FIX: Relaxed boundary check. Chinese text naturally has chars
    adjacent to keywords. Only block when the match is clearly a partial
    substring of a longer word (e.g., '零跑' inside '零跑腿').
    
    Key insight: In Chinese, words are NOT separated by spaces, so we
    can't require word boundaries. Instead we only check for obvious
    false positives.
    """
    # Rule 1: Only block if matched keyword is part of a longer CHINESE word
    # that would change the meaning (e.g., '零跑' inside '零跑腿' where '跑腿' 
    # means 'run errands' - completely different meaning)
    
    # Check if there's a Chinese character AFTER the match that would form
    # a different meaningful word
    if end < len(text):
        next_char = text[end]
        if _is_chinese(next_char):
            # Only block if the keyword + next char forms a known false positive
            # Common false positives to block:
            false_positives = [
                ('零跑', '腿'),   # 零跑腿 (run errands)
                ('理想', '型'),   # 理想型 (ideal type)
                ('蔚来', '蓝'),   # 蔚蓝 (azure)
                ('智己', '任'),   # 知己任 (nonsense)
            ]
            for kw, next_kw in false_positives:
                if matched == kw and next_char == next_kw:
                    return False
    
    # Otherwise, accept the match. Chinese text naturally has keywords
    # adjacent to other Chinese chars, and that's fine.
    return True


def _is_chinese(ch: str) -> bool:
    return '\u4e00' <= ch <= '\u9fff'


def _is_all_chinese(s: str) -> bool:
    return all('\u4e00' <= ch <= '\u9fff' for ch in s)


# Brand alias map for grouping (normalize short names to full brand names)
BRAND_ALIAS_MAP = {
    "零跑汽车": ["零跑"],
    "蔚来汽车": ["蔚来"],
    "小米汽车": ["小米"],
    "鸿蒙智行": ["问界", "智界", "享界", "尊界"],
    "理想汽车": ["理想"],
    "极氪汽车": ["极氪"],
    "智己汽车": ["智己"],
    "比亚迪": ["仰望", "腾势", "方程豹"],
    "特斯拉": ["Tesla"],
}


def normalize_brand(brand: str) -> str:
    """Normalize brand name to main brand for consistent grouping."""
    if not brand:
        return brand
    for main_brand, aliases in BRAND_ALIAS_MAP.items():
        if brand == main_brand or brand in aliases:
            return main_brand
    return brand
