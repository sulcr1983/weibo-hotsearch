import hashlib
import json
from datetime import datetime
from typing import List, Optional, Tuple

import jieba
import jieba.analyse

from v2.constants import (
    BRAND_PATTERNS, BRAND_REGEX, CONTENT_MAX_LENGTH,
    SIMHASH_BITS, HAMMING_THRESHOLD, EVENT_TIME_WINDOW_HOURS,
    SOURCE_LEVEL,
)
from v2.logger import get_logger

logger = get_logger('processor')

_brand_keywords = []
for brand, kws in BRAND_PATTERNS.items():
    _brand_keywords.extend(kws)
for kw in _brand_keywords:
    jieba.add_word(kw)


def match_brand(title: str, content: str = '') -> Tuple[Optional[str], Optional[str]]:
    for brand_group, regex in BRAND_REGEX.items():
        m = regex.search(title)
        if m:
            return brand_group, m.group(0)

    if content:
        snippet = content[:200]
        for brand_group, regex in BRAND_REGEX.items():
            m = regex.search(snippet)
            if m:
                return brand_group, m.group(0)

    return None, None


def extract_keywords(text: str, top_k: int = 10) -> List[str]:
    if not text or not text.strip():
        return []
    try:
        keywords = jieba.analyse.extract_tags(text, topK=top_k)
        return keywords
    except Exception as e:
        logger.error(f"关键词提取失败: {e}")
        return []


def _tokenize(text: str) -> List[str]:
    words = jieba.cut(text)
    return [w.strip() for w in words if len(w.strip()) >= 2]


def calculate_simhash(text: str) -> str:
    if not text or not text.strip():
        return '0' * (SIMHASH_BITS // 4)

    tokens = _tokenize(text)
    if not tokens:
        return '0' * (SIMHASH_BITS // 4)

    v = [0] * SIMHASH_BITS

    for token in tokens:
        token_hash = int(hashlib.md5(token.encode()).hexdigest(), 16)
        for i in range(SIMHASH_BITS):
            bitmask = 1 << i
            if token_hash & bitmask:
                v[i] += 1
            else:
                v[i] -= 1

    fingerprint = 0
    for i in range(SIMHASH_BITS):
        if v[i] > 0:
            fingerprint |= (1 << i)

    return format(fingerprint, f'0{SIMHASH_BITS // 4}x')


def hamming_distance(hash1: str, hash2: str) -> int:
    if not hash1 or not hash2:
        return SIMHASH_BITS
    try:
        val1 = int(hash1, 16)
        val2 = int(hash2, 16)
        xor = val1 ^ val2
        return bin(xor).count('1')
    except ValueError:
        return SIMHASH_BITS


def generate_event_id(brand: str, keywords: List[str], date_bucket: str) -> str:
    sorted_kws = sorted(keywords)[:3]
    keyword_str = '|'.join(sorted_kws)
    raw = f"{brand}|{keyword_str}|{date_bucket}"
    return hashlib.md5(raw.encode()).hexdigest()


async def cluster_article(article: dict, vault) -> str:
    brand = article.get('brand', '')
    simhash_val = article.get('simhash', '')
    title = article.get('title', '')
    keywords_str = article.get('keywords', '[]')
    source = article.get('source', '')

    try:
        keywords = json.loads(keywords_str) if isinstance(keywords_str, str) else keywords_str
    except (json.JSONDecodeError, TypeError):
        keywords = []

    date_bucket = article.get('created_at', '')[:10]
    if not date_bucket:
        date_bucket = datetime.now().strftime('%Y-%m-%d')

    event_id = generate_event_id(brand, keywords, date_bucket)

    if simhash_val and simhash_val != '0' * (SIMHASH_BITS // 4):
        try:
            similar_articles = await vault.get_similar_articles(
                brand, hours=EVENT_TIME_WINDOW_HOURS
            )
            for existing in similar_articles:
                existing_simhash = existing.get('simhash', '')
                if not existing_simhash:
                    continue
                dist = hamming_distance(simhash_val, existing_simhash)
                if dist <= HAMMING_THRESHOLD:
                    existing_event_id = existing.get('event_id')
                    if existing_event_id:
                        event_id = existing_event_id
                        vault.update_event(
                            event_id=event_id,
                            brand=brand,
                            title=title,
                            source=source,
                            keywords=keywords_str,
                        )
                        logger.info(f"聚类命中: [{brand}] {title[:20]} -> event={event_id[:8]} (dist={dist})")
                        return event_id
        except Exception as e:
            logger.error(f"聚类查询失败: {e}")

    vault.update_event(
        event_id=event_id,
        brand=brand,
        title=title,
        source=source,
        keywords=keywords_str,
    )
    return event_id


def process_article(raw: dict) -> Optional[dict]:
    title = raw.get('title', '').strip()
    url = raw.get('url', '').strip()
    source = raw.get('source', '').strip()
    content = raw.get('content', '') or ''

    if not title or not url:
        return None

    brand, keyword = match_brand(title, content)
    if not brand:
        return None

    if content and len(content) > CONTENT_MAX_LENGTH:
        content = content[:CONTENT_MAX_LENGTH]

    keywords = extract_keywords(title + ' ' + content, top_k=10)
    simhash_val = calculate_simhash(title + ' ' + content)

    url_hash = hashlib.md5(url.encode()).hexdigest()
    source_level = SOURCE_LEVEL.get(source, 3)

    article = {
        'url_hash': url_hash,
        'title': title,
        'url': url,
        'source': source,
        'source_level': source_level,
        'brand': brand,
        'keywords': json.dumps(keywords, ensure_ascii=False),
        'content': content,
        'simhash': simhash_val,
        'event_id': None,
        'summary': None,
    }

    return article
