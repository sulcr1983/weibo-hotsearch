"""采集器基类 V5.0 — 统一的 HTTP 获取 + 链接提取 + 云防护兜底"""
import asyncio
import random
from typing import List, Optional

from bs4 import BeautifulSoup

from v2.logger import get_logger
from v2.http_session import SharedSession
from v2.html_utils import extract_links, clean_html_text
from v2.constants import FETCH_DELAY_MIN, FETCH_DELAY_MAX
from processor.observability import check_html_validity, save_fail_snapshot

logger = get_logger('base-collector')


class BaseScraper:
    """统一采集基类"""

    async def _safe_fetch_html(self, session: SharedSession, url: str, source_name: str,
                                 extra_headers: dict = None, check: bool = True) -> Optional[str]:
        """获取 HTML（含有效性检查 + cloudscraper 兜底）"""
        html = await session.fetch(url, extra_headers)
        if not html:
            html = await session.fetch_with_cc(url)
        if not html:
            logger.warning(f"HTTP 失败 [{source_name}]: {url[:60]}")
            return None

        if not check:
            return html

        validity = check_html_validity(html, source_name)
        if not validity['valid']:
            logger.warning(f"⚠ [{source_name}] HTML异常: {validity['issues']}")
            save_fail_snapshot(html, source_name, ','.join(validity['issues']))
            if validity.get('issue_type') in ('captcha_page', 'forbidden_page'):
                return None
        return html

    async def _extract_links(self, session: SharedSession, source: dict, check_html: bool = True) -> List[dict]:
        """通用提取流程：GET → HTML → extract_links"""
        name, url = source['name'], source['url']
        level = source.get('level', 3)
        max_n = source.get('max_items', 20)
        sels = source.get('selectors', {})
        article_sel = sels.get('article', 'a[href]')
        container_sel = sels.get('container', '')

        html = await self._safe_fetch_html(session, url, name, source.get('extra_headers'), check=check_html)
        if not html:
            return []

        links = extract_links(html, url, article_sel, container_sel, max_n)
        items = []
        for link in links:
            items.append({
                'title': link['title'],
                'url': link['url'],
                'source': name,
                'source_level': level,
                'rss_summary': '',
            })
        logger.info(f"  [{name}]: {len(items)}条")
        return items

    async def scrape_one(self, session: SharedSession, source: dict) -> List[dict]:
        return await self._extract_links(session, source)

    async def scrape_all(self, session: SharedSession, sources: List[dict]) -> List[dict]:
        all_items = []
        for src in sources:
            try:
                items = await self.scrape_one(session, src)
                all_items.extend(items)
                await asyncio.sleep(random.uniform(FETCH_DELAY_MIN, FETCH_DELAY_MAX))
            except Exception as e:
                logger.error(f"采集异常 [{src.get('name', '?')}]: {e}")
        return all_items