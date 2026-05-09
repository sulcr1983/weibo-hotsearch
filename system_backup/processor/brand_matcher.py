"""品牌匹配 + HTML剥离 + 金融快讯过滤"""
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
    """检测汇总/晨报/晚报类文章（标题涵盖多品牌，不应归入单品牌）"""
    return bool(_DIGEST_RE.search(title))


def is_ugc(title: str) -> bool:
    """检测UGC/用户帖/自媒体内容（含'X天前'、'X次阅读'等水印）"""
    return bool(_UGC_RE.search(title))


def is_opinion(title: str, source: str = '') -> bool:
    """检测评论/观点文章（仅对虎嗅等深度媒体启用）"""
    if source in ('虎嗅',):
        return bool(_OPINION_RE.search(title))
    return False


def match_brand(title: str, content: str = '') -> Tuple[Optional[str], Optional[str]]:
    clean = strip_html(title)
    for brand, regex in BRAND_REGEX.items():
        m = regex.search(clean)
        if m:
            matched = m.group(0)
            # 品牌名需要边界检查：确保不是长词的一部分
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
    """检查品牌匹配是否有效：排除如'小米手机'匹配'小米'的情况
    V4.2: 修复Python isalnum()对中文返回True导致边界检查误判"""
    # 纯中文关键词（>=2字）：信任匹配，不检查后边界
    if len(matched) >= 2 and _is_all_chinese(matched):
        if start > 0:
            prev_char = text[start - 1]
            if prev_char.isascii() and prev_char.isalnum():
                return False
        return True

    # 英文/数字关键词：严格边界检查
    if start > 0:
        prev_char = text[start - 1]
        if prev_char.isascii() and prev_char.isalnum():
            return False
    if end < len(text):
        next_char = text[end]
        if next_char.isascii() and next_char.isalnum():
            return False
    return True


def _is_chinese(ch: str) -> bool:
    return '\u4e00' <= ch <= '\u9fff'


def _is_all_chinese(s: str) -> bool:
    return all('\u4e00' <= ch <= '\u9fff' for ch in s)
