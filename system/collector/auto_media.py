"""汽车垂媒采集器（V4.0）：汽车之家/懂车帝/爱卡汽车/易车网 + HTML有效性断言"""
import asyncio
import random
from typing import List, Optional
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

from sources import get_auto_feeds
from v2.constants import FETCH_DELAY_MIN, FETCH_DELAY_MAX
from v2.logger import get_logger
from processor.observability import check_html_validity, save_fail_snapshot

logger = get_logger('auto')


class AutoScraper:
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._feeds = get_auto_feeds()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=25),
                headers={
                    'User-Agent': 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36',
                    'Accept': 'text/html,application/json;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9',
                }
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _fetch(self, url: str) -> Optional[str]:
        session = await self._get_session()
        try:
            async with session.get(url) as resp:
                return await resp.text() if resp.status == 200 else None
        except Exception as e:
            logger.warning(f"垂媒采集失败: {url[:60]} - {e}")
            return None

    async def scrape_one(self, cfg: dict) -> List[dict]:
        name = cfg['name']
        url = cfg['url']
        level = cfg.get('level', 2)
        max_n = cfg.get('max_items', 20)
        sels = cfg.get('selectors', {})
        article_sel = sels.get('article', 'a[href]')
        ok, fail = False, []
        logger.info(f"  [{name}]: {url[:60]}")
        html = await self._fetch(url)
        if not html:
            logger.warning(f"  [{name}]: HTTP失败")
            return []
        # HTML有效性断言
        check = check_html_validity(html, name)
        if not check['valid']:
            logger.warning(f"⚠️ [{name}] HTML异常: {check['issues']}")
            save_fail_snapshot(html, name, ','.join(check['issues']))
            if check.get('issue_type') in ('captcha_page', 'forbidden_page'):
                return []
        soup = BeautifulSoup(html, 'html.parser')
        els = soup.select(article_sel)
        articles = []
        for el in els:
            if len(articles) >= max_n:
                break
            title = el.get_text(strip=True)
            # 嵌套元素文字可能分散在子节点中，尝试多种提取方式
            if not title or len(title) < 4:
                title = el.get('title', '').strip() or el.get('aria-label', '').strip()
            # 对于全站链接，可能需要从子元素中查找标题
            if not title or len(title) < 4:
                for child_sel in ['span', 'p', 'h3', 'h4', 'div[class*="title"]', 'div[class*="text"]']:
                    child = el.select_one(child_sel)
                    if child:
                        title = child.get_text(strip=True)
                        if len(title) >= 4:
                            break
            href = el.get('href', '').strip()
            if not title or len(title) < 4 or not href:
                continue
            articles.append({
                'title': title, 'url': urljoin(url, href),
                'source': name, 'source_level': level,
                'rss_summary': '',
            })
        logger.info(f"  [{name}]: 匹配{len(els)}个, 命中{len(articles)}条")
        return articles

    async def scrape_all(self) -> List[dict]:
        all_items = []
        for cfg in self._feeds:
            try:
                items = await self.scrape_one(cfg)
                all_items.extend(items)
                await asyncio.sleep(random.uniform(FETCH_DELAY_MIN, FETCH_DELAY_MAX))
            except Exception as e:
                logger.error(f"垂媒异常 [{cfg.get('name','?')}]: {e}")
        logger.info(f"垂媒采集完成: {len(all_items)}条")
        return all_items
