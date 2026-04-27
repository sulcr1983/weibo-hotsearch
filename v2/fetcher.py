import asyncio
import random
from typing import List, Optional

import aiohttp
import feedparser
import trafilatura
from bs4 import BeautifulSoup

from v2.constants import (
    RSS_FEEDS, BRAND_REGEX, FETCH_TIMEOUT, FETCH_RETRY,
    FETCH_DELAY_MIN, FETCH_DELAY_MAX,
)
from v2.logger import get_logger

logger = get_logger('fetcher')


class SmartFetcher:
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=FETCH_TIMEOUT)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; CarMonitor/2.0; +https://github.com/car-monitor)',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.5',
                }
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def fetch_html(self, url: str) -> Optional[str]:
        session = await self._get_session()
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    logger.warning(f"HTTP {response.status}: {url}")
                    return None
        except asyncio.TimeoutError:
            logger.warning(f"抓取超时: {url}")
            return None
        except Exception as e:
            logger.error(f"抓取异常: {url} - {e}")
            return None

    async def fetch_with_retry(self, url: str, max_retries: int = FETCH_RETRY) -> Optional[str]:
        for attempt in range(max_retries + 1):
            html = await self.fetch_html(url)
            if html is not None:
                return html
            if attempt < max_retries:
                wait = random.uniform(FETCH_DELAY_MIN, FETCH_DELAY_MAX)
                logger.info(f"重试 ({attempt + 1}/{max_retries}): {url}，等待 {wait:.1f}s")
                await asyncio.sleep(wait)
        return None

    def extract_content(self, html: str, url: str) -> Optional[dict]:
        if not html:
            return None

        try:
            result = trafilatura.extract(
                html,
                url=url,
                include_comments=False,
                include_tables=False,
                favor_precision=True,
            )
            if result and len(result.strip()) > 50:
                return {'content': result.strip(), 'method': 'trafilatura'}
        except Exception as e:
            logger.debug(f"trafilatura 提取失败: {url} - {e}")

        try:
            from readability import Document
            doc = Document(html)
            summary_html = doc.summary()
            soup = BeautifulSoup(summary_html, 'html.parser')
            text = soup.get_text(separator='\n', strip=True)
            if text and len(text.strip()) > 50:
                return {'content': text.strip(), 'method': 'readability'}
        except Exception as e:
            logger.debug(f"readability 提取失败: {url} - {e}")

        try:
            soup = BeautifulSoup(html, 'html.parser')
            meta = soup.find('meta', attrs={'name': 'description'})
            if meta and meta.get('content'):
                desc = meta['content'].strip()
                if len(desc) > 20:
                    return {'content': desc, 'method': 'meta_description'}
        except Exception as e:
            logger.debug(f"meta description 提取失败: {url} - {e}")

        return None

    async def fetch_article(self, url: str) -> Optional[dict]:
        html = await self.fetch_with_retry(url)
        if not html:
            return None

        extracted = await asyncio.to_thread(self.extract_content, html, url)
        if not extracted:
            return None

        return {
            'url': url,
            'content': extracted['content'],
            'extraction_method': extracted['method'],
        }

    async def fetch_rss_feed(self, feed_config: dict) -> List[dict]:
        feed_url = feed_config['url']
        feed_name = feed_config['name']
        feed_level = feed_config.get('level', 3)

        logger.info(f"解析 RSS: {feed_name} ({feed_url})")

        try:
            html = await self.fetch_html(feed_url)
            if not html:
                logger.warning(f"RSS 获取失败: {feed_name}")
                return []

            feed = feedparser.parse(html)

            if feed.bozo and not feed.entries:
                logger.warning(f"RSS 解析异常: {feed_name} - {feed.bozo_exception}")
                return []

            articles = []
            for entry in feed.entries:
                title = getattr(entry, 'title', '').strip()
                link = getattr(entry, 'link', '').strip()

                if not title or not link:
                    continue

                brand_matched = False
                for brand_group, regex in BRAND_REGEX.items():
                    if regex.search(title):
                        brand_matched = True
                        break

                if not brand_matched:
                    continue

                published = getattr(entry, 'published', '') or getattr(entry, 'updated', '')
                summary = getattr(entry, 'summary', '').strip()

                articles.append({
                    'title': title,
                    'url': link,
                    'source': feed_name,
                    'source_level': feed_level,
                    'published': published,
                    'rss_summary': summary,
                })

            logger.info(f"RSS [{feed_name}]: 获取 {len(feed.entries)} 条，品牌命中 {len(articles)} 条")
            return articles

        except Exception as e:
            logger.error(f"RSS 处理异常: {feed_name} - {e}")
            return []

    async def fetch_all_rss(self) -> List[dict]:
        all_articles = []

        for feed_config in RSS_FEEDS:
            try:
                articles = await self.fetch_rss_feed(feed_config)
                all_articles.extend(articles)
                wait = random.uniform(FETCH_DELAY_MIN, FETCH_DELAY_MAX)
                await asyncio.sleep(wait)
            except Exception as e:
                logger.error(f"RSS 源处理失败: {feed_config['name']} - {e}")

        logger.info(f"RSS 全源采集完成: 共 {len(all_articles)} 条品牌相关文章")
        return all_articles

    async def enrich_article(self, article: dict) -> dict:
        url = article.get('url', '')
        if not url:
            return article

        try:
            result = await self.fetch_article(url)
            if result:
                article['content'] = result['content']
                article['extraction_method'] = result['extraction_method']
            else:
                rss_summary = article.get('rss_summary', '')
                if rss_summary:
                    soup = BeautifulSoup(rss_summary, 'html.parser')
                    article['content'] = soup.get_text(strip=True)
                    article['extraction_method'] = 'rss_summary'
                else:
                    article['content'] = ''
                    article['extraction_method'] = 'none'
        except Exception as e:
            logger.error(f"文章内容提取失败: {url} - {e}")
            article['content'] = ''
            article['extraction_method'] = 'error'

        wait = random.uniform(FETCH_DELAY_MIN, FETCH_DELAY_MAX)
        await asyncio.sleep(wait)

        return article
