"""网页抓取器：7个HTML/API源，品牌初筛"""
import asyncio
import random
from typing import List, Optional
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

from v2.constants import WEB_FEEDS, BRAND_REGEX, FETCH_DELAY_MIN, FETCH_DELAY_MAX
from v2.logger import get_logger

logger = get_logger('scraper')


class WebScraper:
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=20),
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/json;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9',
                }
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _fetch(self, url: str, no_ssl: bool = False) -> Optional[str]:
        session = await self._get_session()
        kwargs = {}
        if no_ssl:
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            kwargs['ssl'] = ctx
        try:
            async with session.get(url, **kwargs) as resp:
                return await resp.text() if resp.status == 200 else None
        except Exception as e:
            logger.warning(f"Web采集失败: {url[:60]} - {e}")
            return None

    def _extract_text(self, el, sel: Optional[str]) -> str:
        if not sel:
            return el.get_text(strip=True)
        try:
            t = el.select_one(sel)
            return t.get_text(strip=True) if t else el.get_text(strip=True)
        except Exception:
            return el.get_text(strip=True)

    async def scrape_html(self, cfg: dict) -> List[dict]:
        name = cfg['name']
        url = cfg['url']
        level = cfg.get('level', 3)
        max_n = cfg.get('max_items', 30)
        sels = cfg.get('selectors', {})
        article_sel = sels.get('article', 'a[href]')
        title_sel = sels.get('title')
        no_ssl = cfg.get('no_verify_ssl', False)
        logger.info(f"HTML [{name}]: {url[:60]}")
        html = await self._fetch(url, no_ssl=no_ssl)
        if not html:
            return []
        soup = BeautifulSoup(html, 'html.parser')
        els = soup.select(article_sel)
        logger.info(f"  匹配 {len(els)} 个元素")
        articles = []
        for el in els:
            if len(articles) >= max_n:
                break
            title = self._extract_text(el, title_sel).strip()
            href = el.get('href', '').strip()
            if not title or len(title) < 5 or not href:
                continue
            if not any(r.search(title) for r in BRAND_REGEX.values()):
                continue
            articles.append({
                'title': title, 'url': urljoin(url, href),
                'source': name, 'source_level': level,
                'rss_summary': '',
            })
        logger.info(f"  [{name}]: 命中{len(articles)}条")
        return articles

    async def scrape_api(self, cfg: dict) -> List[dict]:
        name = cfg['name']
        url = cfg['url']
        level = cfg.get('level', 3)
        api = cfg.get('api_config', {})
        session = await self._get_session()
        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
        except Exception as e:
            logger.error(f"API失败 [{name}]: {e}")
            return []
        items = data
        for key in api.get('item_path', '').split('.'):
            items = items.get(key, []) if isinstance(items, dict) else items
        if not isinstance(items, list):
            return []
        tk = api.get('title_key', 'title')
        lk = api.get('link_key', 'url')
        articles = []
        for it in items:
            title = it.get(tk, '').strip()
            link = it.get(lk, '').strip()
            if not title or not link:
                continue
            if not any(r.search(title) for r in BRAND_REGEX.values()):
                continue
            articles.append({
                'title': title, 'url': link,
                'source': name, 'source_level': level,
                'rss_summary': '',
            })
        logger.info(f"  [{name}]: {len(items)}条->命中{len(articles)}条")
        return articles

    async def scrape_one(self, cfg: dict) -> List[dict]:
        try:
            return await (self.scrape_api(cfg) if cfg.get('method') == 'api' else self.scrape_html(cfg))
        except Exception as e:
            logger.error(f"抓取异常 [{cfg.get('name','?')}]: {e}")
            return []

    async def scrape_all(self) -> List[dict]:
        all_items = []
        for cfg in WEB_FEEDS:
            items = await self.scrape_one(cfg)
            all_items.extend(items)
            await asyncio.sleep(random.uniform(FETCH_DELAY_MIN, FETCH_DELAY_MAX))
        logger.info(f"Web采集完成: {len(all_items)}条")
        return all_items
