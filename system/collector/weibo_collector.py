"""微博热搜采集器 V3：weibo.com/ajax/side/hotSearch（免Cookie，无需登录）"""
import re
from datetime import datetime
from typing import List, Optional

import aiohttp

from v2.constants import BRAND_REGEX
from v2.logger import get_logger

logger = get_logger('weibo')

# 微博首页侧边栏热搜API — 无需登录即可返回50+条热搜
SIDE_API = 'https://weibo.com/ajax/side/hotSearch'
_HOTGOV_RE = re.compile(r'<a href="([^"]+)"[^>]*>(.+?)</a>')


async def _fetch(session: aiohttp.ClientSession) -> Optional[dict]:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://weibo.com/',
    }
    try:
        async with session.get(SIDE_API, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                return await resp.json()
            logger.warning(f"微博热搜API HTTP {resp.status}")
            return None
    except Exception as e:
        logger.warning(f"微博热搜API异常: {e}")
        return None


def _match_brand(title: str) -> Optional[str]:
    for brand_group, regex in BRAND_REGEX.items():
        if regex.search(title):
            return brand_group
    return None


def _parse(data: dict) -> List[dict]:
    realtime = data.get('data', {}).get('realtime') or []
    hotgov = data.get('data', {}).get('hotgov') or {}
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    items = []

    for rs in realtime:
        word = rs.get('word', '').strip()
        if not word:
            continue
        brand = _match_brand(word)
        if not brand:
            continue
        link = f'https://s.weibo.com/weibo?q={word}'
        items.append({
            'brand_group': brand, 'title': word, 'link': link,
            'label': rs.get('label_name', '') or rs.get('flag_desc', ''),
            'source': '微博热搜', 'is_hotgov': False,
            'rank': rs.get('num', 0) or rs.get('rank', 0),
            'created_at': now,
        })

    if hotgov:
        name = hotgov.get('word', '').strip('#')
        if name:
            brand = _match_brand(name)
            if brand:
                link = f'https://s.weibo.com/weibo?q={name}'
                items.append({
                    'brand_group': brand, 'title': name, 'link': link,
                    'label': '置顶', 'source': '微博热搜', 'is_hotgov': True,
                    'rank': 0, 'created_at': now,
                })

    return items


async def collect(session: aiohttp.ClientSession) -> List[dict]:
    data = await _fetch(session)
    if not data:
        return []
    items = _parse(data)
    logger.info(f"微博热搜: {len(items)} 条品牌命中")
    return items
