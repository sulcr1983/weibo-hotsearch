"""垂媒抓取器 V6.0：智能降级 — aiohttp → cloudscraper → DrissionPage"""
import asyncio
import random
from typing import List

from v2.http_session import SharedSession
from v2.logger import get_logger
from v2.html_utils import extract_links
from v2.user_agents import get_random_ua
from collector.web_scraper import _smart_fetch, _get_headers

logger = get_logger('auto')

AUTO_SOURCES = [
    {
        'name': '汽车之家', 'url': 'https://www.autohome.com.cn/news/',
        'level': 2, 'max_items': 15,
        'selectors': {'article': 'a[href]', 'container': '.news-list'},
    },
    {
        'name': '懂车帝', 'url': 'https://www.dongchedi.com/',
        'level': 2, 'max_items': 15,
        'selectors': {'article': 'a[href]', 'container': ''},
    },
    {
        'name': '易车网', 'url': 'https://news.yiche.com/',
        'level': 2, 'max_items': 15,
        'selectors': {'article': 'a[href]', 'container': '.news-list'},
    },
    {
        'name': '太平洋汽车', 'url': 'https://www.pcauto.com.cn/news/',
        'level': 2, 'max_items': 15,
        'selectors': {'article': 'a[href]', 'container': ''},
    },
    {
        'name': '爱卡汽车', 'url': 'https://news.xcar.com.cn/',
        'level': 2, 'max_items': 15,
        'selectors': {'article': 'a[href]', 'container': ''},
    },
    {
        'name': '盖世汽车', 'url': 'https://auto.gasgoo.com/newenergy/',
        'level': 2, 'max_items': 15,
        'selectors': {'article': 'a[href]', 'container': ''},
    },
    {
        'name': '电车之家', 'url': 'https://www.diandong.com/news/',
        'level': 2, 'max_items': 15,
        'selectors': {'article': 'a[href]', 'container': ''},
    },
]


class AutoScraper:
    async def scrape_all(self) -> List[dict]:
        all_items = []
        async with SharedSession() as session:
            for cfg in AUTO_SOURCES:
                name, url = cfg['name'], cfg['url']
                level = cfg.get('level', 2)
                max_n = cfg.get('max_items', 15)
                sels = cfg.get('selectors', {})
                article_sel = sels.get('article', 'a[href]')
                container_sel = sels.get('container', '')

                logger.info(f"垂媒 [{name}]: {url[:60]}")
                try:
                    html = await _smart_fetch(session, url, name)
                    if not html:
                        logger.warning(f"垂媒 [{name}]: 获取失败")
                        continue

                    links = extract_links(html, url, article_sel, container_sel, max_n)
                    for link in links:
                        all_items.append({
                            'title': link['title'], 'url': link['url'],
                            'source': name, 'source_level': level, 'rss_summary': '',
                        })
                    logger.info(f"垂媒 [{name}]: {len(links)}条")
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.warning(f"垂媒 [{name}] 异常: {e}")
                    continue
                await asyncio.sleep(random.uniform(2.0, 4.0))

        logger.info(f"垂媒采集完成: {len(all_items)}条")
        return all_items