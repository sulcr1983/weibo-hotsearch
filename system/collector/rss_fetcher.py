"""RSS 采集器 V5.1：统一SharedSession + user_agents"""
import asyncio
import random
from email.utils import parsedate_to_datetime
from typing import List, Optional

import feedparser

from v2.http_session import SharedSession
from v2.user_agents import get_random_ua
from v2.constants import RSS_FEEDS, FETCH_DELAY_MIN, FETCH_DELAY_MAX
from v2.logger import get_logger

logger = get_logger('rss')


def _parse_rss_date(raw: str) -> str:
    if not raw:
        return ''
    try:
        return parsedate_to_datetime(raw).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return ''


class RssFetcher:
    async def _fetch_raw(self, session: SharedSession, url: str) -> Optional[str]:
        try:
            text = await session.fetch(url)
            if not text:
                return None
            return text
        except Exception as e:
            logger.warning(f"RSS 异常: {url[:60]} - {e}")
            return None

    async def fetch_feed(self, session: SharedSession, cfg: dict) -> List[dict]:
        name, url, level = cfg['name'], cfg['url'], cfg.get('level', 3)
        logger.info(f"RSS [{name}]: {url[:70]}")
        html = await self._fetch_raw(session, url)
        if not html:
            logger.warning(f"RSS 失败: {name}")
            return []
        feed = feedparser.parse(html)
        if not feed.entries:
            logger.warning(f"RSS无条目 [{name}]")
            return []
        articles = []
        for entry in feed.entries:
            title = getattr(entry, 'title', '').strip()
            link = getattr(entry, 'link', '').strip()
            if not title or not link:
                continue
            summary = getattr(entry, 'summary', '').strip()
            published = _parse_rss_date(getattr(entry, 'published', '') or getattr(entry, 'updated', ''))
            articles.append({
                'title': title, 'url': link, 'source': name,
                'source_level': level, 'published': published,
                'rss_summary': summary,
            })
        logger.info(f"  [{name}]: {len(feed.entries)}条 -> 通过{len(articles)}条")
        return articles

    async def fetch_all(self) -> List[dict]:
        all_items = []
        async with SharedSession() as session:
            for cfg in RSS_FEEDS:
                try:
                    items = await self.fetch_feed(session, cfg)
                    all_items.extend(items)
                    await asyncio.sleep(random.uniform(FETCH_DELAY_MIN, FETCH_DELAY_MAX))
                except Exception as e:
                    logger.error(f"RSS源异常 [{cfg['name']}]: {e}")
        logger.info(f"RSS采集完成: {len(all_items)}条")
        return all_items

    async def close(self):
        pass

