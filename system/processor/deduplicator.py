"""去重 + 事件聚类 (simhash Simhash类)"""
import hashlib
import json
from datetime import datetime
from typing import List

import simhash

from v2.constants import HAMMING_THRESHOLD, EVENT_TIME_WINDOW_HOURS
from v2.logger import get_logger

logger = get_logger('dedup')


def compute_simhash(text: str) -> str:
    if not text or not text.strip():
        return '0' * 16
    words = [w.strip() for w in text.split() if len(w.strip()) >= 2]
    if not words:
        words = [text[:50]]
    try:
        s = simhash.Simhash(words)
        return format(s.value, '016x')
    except Exception:
        return hashlib.md5(text.encode()).hexdigest()[:16]


def hamming_dist(h1: str, h2: str) -> int:
    try:
        return simhash.Simhash(0).distance(simhash.Simhash(0))
    except Exception:
        pass
    try:
        v1 = int(h1, 16)
        v2 = int(h2, 16)
        return bin(v1 ^ v2).count('1')
    except (ValueError, Exception):
        return 64


def _hamming_distance(val1: int, val2: int) -> int:
    return bin(val1 ^ val2).count('1')


def generate_event_id(brand: str, keywords: List[str], date_bucket: str) -> str:
    kws = '|'.join(sorted(keywords)[:3])
    return hashlib.md5(f"{brand}|{kws}|{date_bucket}".encode()).hexdigest()


async def cluster_article(article: dict, vault) -> str:
    brand = article.get('brand', '')
    sh = article.get('simhash', '')
    title = article.get('title', '')
    kws_str = article.get('keywords', '[]')
    source = article.get('source', '')
    try:
        keywords = json.loads(kws_str) if isinstance(kws_str, str) else kws_str
    except (json.JSONDecodeError, TypeError):
        keywords = []
    date_bucket = (article.get('created_at', '') or datetime.now().strftime('%Y-%m-%d'))[:10]
    eid = generate_event_id(brand, keywords, date_bucket)
    if sh and sh != '0' * 16:
        try:
            similar = await vault.get_similar_articles(brand, EVENT_TIME_WINDOW_HOURS)
            for ex in similar:
                ex_sh = ex.get('simhash', '')
                if not ex_sh or ex_sh == '0' * 16:
                    continue
                try:
                    v1 = int(sh, 16)
                    v2 = int(ex_sh, 16)
                    dist = _hamming_distance(v1, v2)
                except (ValueError, Exception):
                    continue
                if dist <= HAMMING_THRESHOLD:
                    eeid = ex.get('event_id')
                    if eeid:
                        vault.update_event(event_id=eeid, brand=brand, title=title, source=source, keywords=kws_str)
                        logger.info(f"聚类命中: [{brand}] -> event={eeid[:8]} (dist={dist})")
                        return eeid
        except Exception as e:
            logger.error(f"聚类查询失败: {e}")
    vault.update_event(event_id=eid, brand=brand, title=title, source=source, keywords=kws_str)
    return eid
