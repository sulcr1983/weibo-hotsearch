"""汽车垂媒采集器 V5.1：统一SharedSession + extract_links"""
import asyncio
import random
from typing import List, Optional

from v2.http_session import SharedSession
from v2.html_utils import extract_links
from sources import get_auto_feeds
from v2.constants import FETCH_DELAY_MIN, FETCH_DELAY_MAX
from v2.logger import get_logger
from processor.observability import check_html_validity, save_fail_snapshot

logger = get_logger('auto')


class AutoScraper:
    def __init__(self):
        self._feeds = get_auto_feeds()

    async def scrape_one(self, session: SharedSession, cfg: dict) -> List[dict]:
        name, url = cfg['name'], cfg['url']
        level = cfg.get('level', 2)
        max_n = cfg.get('max_items', 20)
        sels = cfg.get('selectors', {})
        article_sel = sels.get('article', 'a[href]')
        container_sel = sels.get('container', '')

        logger.info(f"  [{name}]: {url[:60]}")
        html = await session.fetch(url)
        if not html:
            html = await session.fetch_with_cc(url)
        if not html:
            return []

        check = check_html_validity(html, name)
        if not check['valid']:
            logger.warning(f"  [{name}]: {';'.join(check['issues'])}")
            save_fail_snapshot(html, name, ','.join(check['issues']), prefix='auto_fail')
            return []

        links = extract_links(html, url, article_sel, container_sel, max_n)
        articles = []
        for link in links:
            articles.append({
                'title': link['title'], 'url': link['url'],
                'source': name, 'source_level': level, 'rss_summary': '',
            })
        logger.info(f"  [{name}]: {len(articles)}条")
        return articles

    async def scrape_all(self) -> List[dict]:
        if not self._feeds:
            return []
        all_items = []
        async with SharedSession() as session:
            for cfg in self._feeds:
                try:
                    items = await self.scrape_one(session, cfg)
                    all_items.extend(items)
                    await asyncio.sleep(random.uniform(FETCH_DELAY_MIN, FETCH_DELAY_MAX))
                except Exception as e:
                    logger.error(f"垂媒 {cfg.get('name','?')}: {e}")
        logger.info(f"垂媒采集完成: {len(all_items)}条")
        return all_items

    async def close(self):
        pass

