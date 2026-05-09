"""AI 爬虫 V3 — 仅兜底：只抓 requests 无法访问的站点"""
import asyncio
import random
from typing import List, Optional
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

from v2.logger import get_logger
from reporter.ai_writer import ai_extract_articles

logger = get_logger('ai-scraper')

UA_MOBILE = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1'
UA_DESKTOP = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36'

# 仅保留 plain HTTP 无法访问的源作为兜底
# 目前所有已知源都可通过 requests 访问，以下为预留
FALLBACK_SOURCES: list = []


def _clean_text(html: str) -> str:
    try:
        soup = BeautifulSoup(html, 'html.parser')
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'noscript', 'iframe']):
            tag.decompose()
        text = soup.get_text(separator='\n', strip=True)
        lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) > 2]
        return '\n'.join(lines[:300])
    except Exception:
        return html[:4000]


def _css_extract(html: str, base_url: str, source_name: str) -> List[dict]:
    try:
        soup = BeautifulSoup(html, 'html.parser')
        links = soup.select('a[href]')
        seen = set()
        items = []
        for el in links:
            title = el.get_text(strip=True)
            href = el.get('href', '').strip()
            if not title or len(title) < 8 or not href:
                continue
            if any(s in href.lower() for s in ['javascript:', 'mailto:', '#', 'tel:', 'login']):
                continue
            url = urljoin(base_url, href)
            if url in seen:
                continue
            seen.add(url)
            items.append({
                'title': title, 'url': url, 'rss_summary': '',
                'source': source_name, 'source_level': 2, 'published': '',
            })
            if len(items) >= 20:
                break
        return items
    except Exception:
        return []


async def _fetch(url: str) -> Optional[str]:
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    headers = {
        'User-Agent': random.choice([UA_MOBILE, UA_DESKTOP]),
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ctx)) as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                return await resp.text() if resp.status == 200 else None
    except Exception:
        return None


class AIScraper:
    def __init__(self, ai_config: dict):
        self.api_key = ai_config.get('api_key', '')
        self.api_url = ai_config.get('api_url', '')
        self.model = ai_config.get('model', 'deepseek-chat')
        self.enabled = bool(self.api_key)

    async def scrape_all(self) -> List[dict]:
        if not FALLBACK_SOURCES:
            logger.info("[AI兜底] 无兜底源（所有源已被HTTP直接覆盖），跳过")
            return []

        logger.info(f"[AI兜底] 启动: {len(FALLBACK_SOURCES)} 个兜底源")
        all_items = []
        for src in FALLBACK_SOURCES:
            try:
                html = await _fetch(src['url'])
                if not html:
                    continue
                if self.enabled:
                    text = _clean_text(html)
                    articles = await ai_extract_articles(self.api_key, self.api_url, self.model, text, src['name'])
                    for a in articles[:15]:
                        url = a.get('url', '')
                        if url and not url.startswith('http'):
                            url = urljoin(src['url'], url)
                        all_items.append({
                            'title': a.get('title', ''), 'url': url,
                            'rss_summary': a.get('summary', '')[:80],
                            'source': src['name'], 'source_level': 2,
                            'published': a.get('time', ''),
                        })
                else:
                    all_items.extend(_css_extract(html, src['url'], src['name']))
                await asyncio.sleep(random.uniform(2, 4))
            except Exception as e:
                logger.error(f"[AI兜底] {src.get('name','?')}: {e}")
        logger.info(f"[AI兜底] 完成: {len(all_items)} 条")
        return all_items