"""网页抓取器 V5.1：统一SharedSession + user_agents + v2.html_utils"""
import asyncio
import json
import random
import re
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from v2.http_session import SharedSession
from v2.constants import WEB_FEEDS, FETCH_DELAY_MIN, FETCH_DELAY_MAX
from v2.logger import get_logger
from v2.html_utils import extract_links
from processor.observability import check_html_validity, save_fail_snapshot

logger = get_logger('scraper')


class WebScraper:
    async def _scrape_api_source(self, session: SharedSession, cfg: dict) -> List[dict]:
        name, url = cfg['name'], cfg['url']
        api_cfg = cfg.get('api_config', {})
        level = cfg.get('level', 3)
        max_n = cfg.get('max_items', 20)

        logger.info(f"API [{name}]: {url[:60]}")
        html = await session.fetch(url)
        if not html:
            return []

        try:
            if api_cfg.get('jsonp'):
                m = re.search(r'[a-zA-Z_]\w*\((.*)\)', html, re.S)
                html = m.group(1) if m else html
            data = json.loads(html) if not isinstance(html, dict) else html
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"API [{name}]: JSON解析失败")
            return []

        path = api_cfg.get('item_path', 'data.list').split('.')
        items = data
        for p in path:
            if isinstance(items, dict):
                items = items.get(p, [])
            elif isinstance(items, list):
                break
        if not isinstance(items, list):
            items = []

        tk = api_cfg.get('title_key', 'title')
        lk = api_cfg.get('link_key', 'url')
        time_k = api_cfg.get('time_key', '')
        sum_k = api_cfg.get('summary_key', '')
        lp = api_cfg.get('link_prefix', '')

        articles = []
        for item in items[:max_n]:
            if not isinstance(item, dict):
                continue
            title = str(item.get(tk, '')).strip()
            link = str(item.get(lk, ''))
            if not title or len(title) < 4:
                continue
            if lp and link and not link.startswith('http'):
                if link.startswith('/'):
                    link = lp + link
                else:
                    link = lp + '/' + link
            articles.append({
                'title': title, 'url': link, 'source': name,
                'source_level': level,
                'rss_summary': str(item.get(sum_k, ''))[:100],
                'published': str(item.get(time_k, '')) if time_k else '',
            })
        logger.info(f"API [{name}]: {len(articles)}条")
        return articles

    async def _scrape_html_source(self, session: SharedSession, cfg: dict) -> List[dict]:
        name, url = cfg['name'], cfg['url']
        level = cfg.get('level', 3)
        max_n = cfg.get('max_items', 20)
        sels = cfg.get('selectors', {})
        article_sel = sels.get('article', 'a[href]')
        container_sel = sels.get('container', '')

        logger.info(f"HTML [{name}]: {url[:60]}")
        html = await session.fetch(url)
        if not html:
            html = await session.fetch_with_cc(url)
        if not html:
            logger.warning(f"HTML [{name}]: 获取失败")
            return []

        check = check_html_validity(html, name)
        if not check['valid']:
            logger.warning(f"⚠ [{name}] HTML异常: {check['issues']}")
            save_fail_snapshot(html, name, ','.join(check['issues']), prefix='web_fail')
            if check.get('issue_type') in ('captcha_page', 'forbidden_page'):
                return []

        links = extract_links(html, url, article_sel, container_sel, max_n)
        articles = []
        for link in links:
            articles.append({
                'title': link['title'], 'url': link['url'],
                'source': name, 'source_level': level, 'rss_summary': '',
            })
        logger.info(f"HTML [{name}]: {len(articles)}条")
        return articles

    async def scrape_one(self, session: SharedSession, cfg: dict) -> List[dict]:
        method = cfg.get('method', 'html')
        if method == 'api':
            return await self._scrape_api_source(session, cfg)
        return await self._scrape_html_source(session, cfg)

    async def scrape_all(self) -> List[dict]:
        all_items = []
        async with SharedSession() as session:
            for cfg in WEB_FEEDS:
                try:
                    items = await self.scrape_one(session, cfg)
                    all_items.extend(items)
                    await asyncio.sleep(random.uniform(FETCH_DELAY_MIN, FETCH_DELAY_MAX))
                except Exception as e:
                    logger.error(f"Web源 {cfg.get('name','?')} 异常: {e}")
        logger.info(f"Web采集完成: {len(all_items)}条")
        return all_items

