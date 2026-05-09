"""Jieba 关键词提取（带品牌词典 + 金融词过滤）"""
import re
from typing import List

import jieba
import jieba.analyse

from v2.constants import BRAND_PATTERNS

_CLUSTER_KW_RE = re.compile(r'[\d.]+%|\d+\.\d+%|涨|跌|涨超|跌超')

for kws in BRAND_PATTERNS.values():
    for kw in kws:
        try:
            jieba.add_word(kw, freq=99999)
        except Exception:
            pass


def extract_keywords(text: str, top_k: int = 10) -> List[str]:
    if not text or not text.strip():
        return []
    try:
        kws = jieba.analyse.extract_tags(text, topK=top_k)
        filtered = [kw for kw in kws if not _CLUSTER_KW_RE.search(kw)]
        return (filtered if len(filtered) >= 5 else kws)[:top_k]
    except Exception:
        return []
