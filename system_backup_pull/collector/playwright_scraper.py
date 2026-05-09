"""Playwright 浏览器采集器 V4.2：增强反爬 + 汽车垂媒统一采集"""
import asyncio
import random
import re
from datetime import datetime
from typing import List, Optional
from urllib.parse import urljoin

from v2.logger import get_logger
from processor.observability import check_html_validity, save_fail_snapshot

logger = get_logger('playwright')


UA_POOL = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0',
]

_STEALTH_SCRIPT = """
(() => {
    const p = navigator.__proto__;
    delete p.webdriver;
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
    Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en-US', 'en']});
    Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
    Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
    Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
    Object.defineProperty(navigator, 'maxTouchPoints', {get: () => 0});

    delete window.__playwright__binding__;
    delete window.__pw_manual__;
    delete window.__PW_inspectMode;

    window.chrome = {runtime: {}, loadTimes: function(){}, csi: function(){}, app: {}};

    const oq = window.navigator.permissions.query;
    window.navigator.permissions.query = (p) => (
        p.name === 'notifications' ?
        Promise.resolve({state: Notification.permission}) : oq(p)
    );

    if (navigator.connection) {
        Object.defineProperty(navigator.connection, 'rtt', {get: () => 50});
    }

    const getParam = URLSearchParams.prototype.get;
    URLSearchParams.prototype.get = function(name) {
        if (name === 'navigator_webdriver' || name === 'webdriver') return 'false';
        return getParam.call(this, name);
    };

    HTMLCanvasElement.prototype.toDataURL = (function(orig) {
        return function() { return orig.apply(this, arguments); };
    })(HTMLCanvasElement.prototype.toDataURL);
})();
"""


class PlaywrightScraper:
    def __init__(self):
        self._playwright = None
        self._browser = None
        self._context = None
        self._feeds: List[dict] = []
        self._auto_feeds: List[dict] = []
        self._load_feeds()

    def _load_feeds(self):
        try:
            from sources import get_playwright_feeds
            feeds = get_playwright_feeds()
            if feeds:
                self._feeds = feeds
                logger.info(f"Playwright采集器: 加载 {len(feeds)} 个源 (from YAML)")
            else:
                self._feeds = []
                logger.info("Playwright采集器: YAML无配置")
        except Exception:
            self._feeds = []
            logger.info("Playwright采集器: 使用空源列表")

        try:
            from sources import get_auto_feeds
            auto_feeds = get_auto_feeds()
            if auto_feeds:
                self._auto_feeds = auto_feeds
                logger.info(f"Playwright采集器: 加载 {len(auto_feeds)} 个垂媒源 (from YAML, 自动升级)")
        except Exception:
            self._auto_feeds = []

    async def start(self):
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-infobars',
                    '--window-size=1920,1080',
                    '--disable-setuid-sandbox',
                    '--disable-accelerated-2d-canvas',
                    '--disable-gpu',
                ]
            )
            ua = random.choice(UA_POOL)
            self._context = await self._browser.new_context(
                user_agent=ua,
                viewport={'width': random.randint(1366, 1920), 'height': random.randint(768, 1080)},
                locale='zh-CN',
                timezone_id='Asia/Shanghai',
                permissions=['geolocation'],
                geolocation={'latitude': 39.9042, 'longitude': 116.4074},
            )
            await self._context.add_init_script(_STEALTH_SCRIPT)
            logger.info(f"Playwright 浏览器已启动 (stealth增强 | UA池{len(UA_POOL)}个)")
        except Exception as e:
            logger.error(f"Playwright 启动失败: {e}")
            self._browser = None

    async def close(self):
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("Playwright 浏览器已关闭")

    async def _fetch_page(self, url: str, extra_headers: dict = None, scroll: bool = True) -> Optional[str]:
        if not self._context:
            logger.warning("Playwright 上下文未初始化")
            return None
        page = await self._context.new_page()
        try:
            if extra_headers:
                await page.set_extra_http_headers(extra_headers)

            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(random.uniform(0.5, 1.2))

            if scroll:
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight * 0.25)')
                await asyncio.sleep(random.uniform(0.3, 0.6))
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight * 0.5)')
                await asyncio.sleep(random.uniform(0.2, 0.5))
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight * 0.75)')
                await asyncio.sleep(0.3)

            await page.wait_for_timeout(random.randint(800, 2000))
            html = await page.content()
            return html
        except Exception as e:
            logger.warning(f"Playwright 页面加载失败: {url[:50]} - {e}")
            return None
        finally:
            await page.close()

    async def scrape_one(self, cfg: dict) -> List[dict]:
        name = cfg['name']
        url = cfg['url']
        level = cfg.get('level', 3)
        max_n = cfg.get('max_items', 20)
        sels = cfg.get('selectors', {})
        article_sel = sels.get('article', 'a[href]')
        container_sel = sels.get('container', '')
        extra_headers = cfg.get('extra_headers', None)

        logger.info(f"Playwright [{name}]: {url[:60]}")
        html = await self._fetch_page(url, extra_headers=extra_headers)
        if not html:
            logger.warning(f"Playwright [{name}]: 获取失败")
            return []

        check = check_html_validity(html, name)
        if not check['valid']:
            logger.warning(f"⚠ [{name}] HTML异常: {check['issues']}")
            save_fail_snapshot(html, name, ','.join(check['issues']), prefix='pw_fail')
            if check.get('issue_type') in ('captcha_page', 'forbidden_page'):
                return []

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')

        if container_sel:
            containers = soup.select(container_sel)
            links = []
            for c in containers:
                links.extend(c.select(article_sel))
        else:
            links = soup.select(article_sel)

        articles = []
        seen_urls = set()
        for el in links:
            if len(articles) >= max_n:
                break
            title = el.get_text(strip=True)
            href = el.get('href', '').strip()
            if not title or len(title) < 5 or not href:
                continue
            full_url = urljoin(url, href)
            if full_url in seen_urls:
                continue
            if any(skip in full_url.lower() for skip in ['javascript:', 'mailto:', '#', 'tel:']):
                continue
            seen_urls.add(full_url)
            articles.append({
                'title': title,
                'url': full_url,
                'source': name,
                'source_level': level,
                'rss_summary': '',
            })
        logger.info(f"Playwright [{name}]: {len(articles)}条")
        return articles

    async def scrape_all(self) -> List[dict]:
        all_sources = self._feeds + self._auto_feeds
        if not all_sources:
            logger.info("Playwright: 无源配置, 跳过")
            return []

        all_items = []
        await self.start()
        if not self._context:
            return []

        try:
            for cfg in all_sources:
                try:
                    items = await self.scrape_one(cfg)
                    all_items.extend(items)
                    await asyncio.sleep(random.uniform(2, 5))
                except Exception as e:
                    logger.error(f"Playwright源异常 [{cfg.get('name','?')}]: {e}")
            logger.info(f"Playwright采集完成: {len(all_items)}条 (源数={len(all_sources)})")
            return all_items
        finally:
            await self.close()