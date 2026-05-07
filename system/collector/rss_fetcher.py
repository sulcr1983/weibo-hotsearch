"""RSS 采集器：20个直接RSS源 + 10个RSSHub路由"""
import asyncio
import random
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import List, Optional

import aiohttp
import feedparser
from bs4 import BeautifulSoup

from v2.constants import RSS_FEEDS, BRAND_REGEX, FETCH_TIMEOUT, FETCH_DELAY_MIN, FETCH_DELAY_MAX
from v2.logger import get_logger

logger = get_logger('rss')


def _parse_rss_date(raw: str) -> str:
    """RSS RFC 2822 → 'YYYY-MM-DD HH:MM:SS'，解析失败返回空字符串"""
    if not raw:
        return ''
    try:
        return parsedate_to_datetime(raw).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return ''


class RssFetcher:
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=FETCH_TIMEOUT),
                headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; CarMonitor/4.1)',
                    'Accept': 'text/html,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9',
                }
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _fetch_raw(self, url: str) -> Optional[str]:
        session = await self._get_session()
        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                raw = await resp.read()
                for enc in ['utf-8', 'gbk', 'gb2312', 'gb18030']:
                    try:
                        return raw.decode(enc)
                    except (UnicodeDecodeError, UnicodeError):
                        continue
                return None
        except asyncio.TimeoutError:
            logger.warning(f"RSS 超时: {url}")
            return None
        except Exception as e:
            logger.error(f"RSS 异常: {url[:60]} - {e}")
            return None

    async def fetch_feed(self, cfg: dict) -> List[dict]:
        name = cfg['name']
        url = cfg['url']
        level = cfg.get('level', 3)
        logger.info(f"RSS [{name}]: {url[:70]}")
        html = await self._fetch_raw(url)
        if not html:
            logger.warning(f"RSS 失败: {name}")
            return []
        feed = feedparser.parse(html)
        if feed.bozo:
            bozo_msg = str(getattr(feed, 'bozo_exception', 'unknown parsing error'))
            if not feed.entries:
                logger.warning(f"RSS解析失败 [{name}]: {bozo_msg[:100]}")
                return []
            logger.warning(f"RSS部分解析 [{name}]: bozo={bozo_msg[:80]}, entries={len(feed.entries)}")
        if not feed.entries:
            logger.warning(f"RSS无条目 [{name}]: URL可能失效或内容为空")
            return []
        articles = []
        for entry in feed.entries:
            title = getattr(entry, 'title', '').strip()
            link = getattr(entry, 'link', '').strip()
            if not title or not link:
                continue
            summary = getattr(entry, 'summary', '').strip()
            published_raw = getattr(entry, 'published', '') or getattr(entry, 'updated', '')
            published = _parse_rss_date(published_raw)
            search_text = title + ' ' + summary[:200]
            if not any(r.search(search_text) for r in BRAND_REGEX.values()):
                continue
            articles.append({
                'title': title, 'url': link, 'source': name,
                'source_level': level, 'published': published,
                'rss_summary': summary,
            })
        logger.info(f"  [{name}]: {len(feed.entries)}条 -> 命中{len(articles)}条")
        return articles

    async def fetch_all(self) -> List[dict]:
        all_items = []
        for cfg in RSS_FEEDS:
            try:
                items = await self.fetch_feed(cfg)
                all_items.extend(items)
                await asyncio.sleep(random.uniform(FETCH_DELAY_MIN, FETCH_DELAY_MAX))
            except Exception as e:
                logger.error(f"RSS源异常 [{cfg['name']}]: {e}")
        logger.info(f"RSS采集完成: {len(all_items)}条")
        return all_items
