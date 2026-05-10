"""网页抓取器 V6.0：智能降级 — aiohttp → cloudscraper → DrissionPage"""
import asyncio
import json
import random
import re
from typing import List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from v2.http_session import SharedSession
from v2.constants import WEB_FEEDS
from v2.logger import get_logger
from v2.html_utils import extract_links
from v2.user_agents import get_random_ua
from processor.observability import check_html_validity, save_fail_snapshot

logger = get_logger('scraper')

_REFERER_MAP = {
    '36氪': 'https://36kr.com/',
    '虎嗅': 'https://huxiu.com/',
    '新浪财经': 'https://finance.sina.com.cn/',
    '每日经济新闻': 'https://www.nbd.com.cn/',
    '第一财经': 'https://www.yicai.com/',
    '界面新闻': 'https://www.jiemian.com/',
    '澎湃新闻': 'https://www.thepaper.cn/',
    'IT之家': 'https://www.ithome.com/',
    '新浪汽车': 'https://auto.sina.com.cn/',
    '搜狐汽车': 'https://auto.sohu.com/',
    '腾讯汽车': 'https://new.qq.com/',
    '懂车帝': 'https://www.dongchedi.com/',
    '易车网': 'https://www.yiche.com/',
    '汽车之家': 'https://www.autohome.com.cn/',
    '太平洋汽车': 'https://www.pcauto.com.cn/',
    '爱卡汽车': 'https://www.xcar.com.cn/',
    '盖世汽车': 'https://www.gasgoo.com/',
    '电车之家': 'https://www.diandong.com/',
}


def _get_headers(name: str = '') -> dict:
    referer = ''
    for keyword, ref in _REFERER_MAP.items():
        if keyword in name:
            referer = ref
            break
    h = {
        'User-Agent': get_random_ua(),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Sec-Ch-Ua': '"Chromium";v="135", "Google Chrome";v="135"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
    }
    if referer:
        h['Referer'] = referer
    return h


async def _smart_fetch(session: SharedSession, url: str, name: str, timeout: int = 12) -> Optional[str]:
    """V6.0 智能降级: aiohttp → cloudscraper → DrissionPage"""
    headers = _get_headers(name)

    # Level 0: aiohttp 直接请求
    html = await session.fetch(url, extra_headers=headers, timeout=timeout)
    if html:
        check = check_html_validity(html, name)
        if check['valid']:
            return html
        logger.info(f"[{name}] aiohttp被拦截({check.get('issue_type', '')}), 降级到cloudscraper")

    # Level 1: cloudscraper-enhanced (Cloudflare/5s盾)
    html = await session.fetch_with_cc(url, timeout=timeout)
    if html:
        check = check_html_validity(html, name)
        if check['valid']:
            logger.info(f"[{name}] cloudscraper成功")
            return html
        logger.info(f"[{name}] cloudscraper也被拦截, 降级到DrissionPage")

    # Level 2: DrissionPage (无WebDriver检测)
    html = await session.fetch_with_dp(url, timeout=30)
    if html:
        check = check_html_validity(html, name)
        if check['valid']:
            logger.info(f"[{name}] DrissionPage成功")
            return html
        save_fail_snapshot(html, name, ','.join(check['issues']), prefix='web_fail')

    logger.warning(f"[{name}] 所有降级方式均失败")
    return None


class WebScraper:
    async def _scrape_api_source(self, session: SharedSession, cfg: dict) -> List[dict]:
        name, url = cfg['name'], cfg['url']
        api_cfg = cfg.get('api_config', {})
        level = cfg.get('level', 3)
        max_n = cfg.get('max_items', 20)

        logger.info(f"API [{name}]: {url[:60]}")
        html = await session.fetch(url, extra_headers=_get_headers(name), timeout=12)
        if not html:
            html = await session.fetch_with_cc(url)
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
        html = await _smart_fetch(session, url, name)
        if not html:
            logger.warning(f"HTML [{name}]: 获取失败")
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
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.warning(f"Web源 [{cfg.get('name','?')}] 异常: {e}")
                    continue
                await asyncio.sleep(random.uniform(1.5, 3.5))
        logger.info(f"Web采集完成: {len(all_items)}条")
        return all_items