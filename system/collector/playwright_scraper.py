"""Playwright 浏览器采集器 V4.1：JS 渲染页面 + 权威来源补充"""
import asyncio
import random
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from urllib.parse import urljoin

from v2.logger import get_logger
from processor.observability import check_html_validity, save_fail_snapshot

logger = get_logger('playwright')

# ── 默认配置（可被 sources.yml 覆盖）──
DEFAULT_PLAYWRIGHT_FEEDS = [
    # ── 权威传统媒体（Level 1）──
    {
        'name': '央视汽车',
        'url': 'https://auto.cctv.com/',
        'level': 1,
        'method': 'playwright',
        'max_items': 20,
        'selectors': {
            'article': 'a[href*="/"]',
            'container': 'ul.list li, div.item, div.news_list li, div.list li',
        },
    },
    {
        'name': '新华网汽车',
        'url': 'http://www.xinhuanet.com/auto/',
        'level': 1,
        'method': 'playwright',
        'max_items': 20,
        'selectors': {
            'article': 'a[href*=".htm"]',
            'container': 'div.news-list li, ul.listWrap li, div.part-news li',
        },
    },
    # ── 垂直汽车媒体（Level 2）──
    {
        'name': '太平洋汽车网',
        'url': 'https://www.pcauto.com.cn/',
        'level': 2,
        'method': 'playwright',
        'max_items': 25,
        'selectors': {
            'article': 'a[href*=".html"]',
            'container': 'div.newsList li, div.item, div.news-item',
        },
    },
    {
        'name': '腾讯汽车',
        'url': 'https://auto.qq.com/',
        'level': 2,
        'method': 'playwright',
        'max_items': 25,
        'selectors': {
            'article': 'a[href*="auto.qq.com"]',
            'container': 'li[class*="item"], div.list-item, div.news-list li',
        },
    },
    {
        'name': '汽车商业评论',
        'url': 'https://m.autoreport.cn/',
        'level': 2,
        'method': 'playwright',
        'max_items': 15,
        'selectors': {
            'article': 'a[href*="/article/"], a[href*="/news/"]',
            'container': 'div.news-item, li.item, div.list-item',
        },
    },
    # ── 汽车专业杂志/工程（Level 2）──
    {
        'name': '汽车之友',
        'url': 'https://www.autofan.com.cn/',
        'level': 2,
        'method': 'playwright',
        'max_items': 15,
        'selectors': {
            'article': 'a[href*=".html"], a[href*="/article/"]',
            'container': 'li, div.item, div.post-item',
        },
    },
    # ── 新华社/人民日报 汽车频道 ──
    {
        'name': '人民网汽车',
        'url': 'http://auto.people.com.cn/',
        'level': 1,
        'method': 'playwright',
        'max_items': 20,
        'selectors': {
            'article': 'a[href*=".html"]',
            'container': 'div.news-list li, div.list-item, div.headline',
        },
    },
]

# ── 反爬/验证码检测正则 ──
CAPTCHA_RE = re.compile(r'验证|滑块|点击完成|captcha|请证明|安全校验', re.I)
LOGIN_RE = re.compile(r'请登录|立即登录|login|sign.?in', re.I)
BLOCK_RE = re.compile(r'403|forbidden|access denied|封禁|blocked|访问被拒', re.I)


class PlaywrightScraper:
    def __init__(self):
        self._playwright = None
        self._browser = None
        self._context = None
        self._feeds: List[dict] = []
        self._load_feeds()

    def _load_feeds(self):
        """优先从 YAML 加载，fallback 到默认配置"""
        try:
            from sources import get_playwright_feeds
            feeds = get_playwright_feeds()
            if feeds:
                self._feeds = feeds
                logger.info(f"Playwright采集器: 加载 {len(feeds)} 个源 (from YAML)")
                return
        except Exception:
            pass
        self._feeds = DEFAULT_PLAYWRIGHT_FEEDS
        logger.info(f"Playwright采集器: 使用默认 {len(self._feeds)} 个源")

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
                    '--start-maximized',
                ]
            )
            # 使用 stealth 伪装
            try:
                from playwright_stealth import stealth_sync
                # stealth 需要通过 sync API 注入，这里手动注入关键属性
            except ImportError:
                pass

            self._context = await self._browser.new_context(
                user_agent=(
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/130.0.0.0 Safari/537.36'
                ),
                viewport={'width': 1920, 'height': 1080},
                locale='zh-CN',
                timezone_id='Asia/Shanghai',
                # 模拟真实浏览器的权限状态
                permissions=['geolocation'],
                geolocation={'latitude': 39.9042, 'longitude': 116.4074},  # 北京
            )
            # 注入多层反检测脚本
            await self._context.add_init_script("""
                // 隐藏 webdriver 标记
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                // 伪造 plugins
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                // 伪造 languages
                Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
                // 伪造 platform
                Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
                // 伪造 hardwareConcurrency
                Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
                // 伪造 deviceMemory
                Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
                // 移除 chrome 自动化标记
                delete window.__playwright__binding__;
                delete window.__pw_manual__;
                delete window.__PW_inspectMode;
                // 伪造 chrome 对象
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };
                // 伪造权限查询
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                    Promise.resolve({state: Notification.permission}) :
                    originalQuery(parameters)
                );
            """)
            logger.info("Playwright 浏览器已启动 (stealth模式)")
        except Exception as e:
            logger.error(f"Playwright 启动失败: {e}")
            self._browser = None

    async def close(self):
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Playwright 浏览器已关闭")

    async def _fetch_page(self, url: str, wait_ms: int = 3000, extra_headers: dict = None) -> Optional[str]:
        """用 Playwright 加载页面，等待 JS 渲染后返回 HTML"""
        if not self._browser:
            logger.warning("Playwright 浏览器未启动，跳过")
            return None
        page = await self._context.new_page()
        try:
            # 设置额外 headers
            if extra_headers:
                await page.set_extra_http_headers(extra_headers)
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            # 等待 JS 渲染 + 模拟人类滚动行为
            await asyncio.sleep(random.uniform(0.8, 1.5))
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight * 0.3)')
            await asyncio.sleep(random.uniform(0.4, 0.8))
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight * 0.6)')
            await asyncio.sleep(0.3)
            await page.wait_for_timeout(wait_ms)
            html = await page.content()
            return html
        except Exception as e:
            logger.warning(f"Playwright 页面加载失败: {url[:60]} - {e}")
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

        # HTML 有效性检查
        check = check_html_validity(html, name)
        if not check['valid']:
            logger.warning(f"⚠️ [{name}] HTML异常: {check['issues']}")
            save_fail_snapshot(html, name, ','.join(check['issues']), prefix='pw_fail')
            if check.get('issue_type') in ('captcha_page', 'forbidden_page'):
                return []

        # 用 BeautifulSoup 解析
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')

        # 优先在 container 内找 links，找不到则全局搜
        if container_sel:
            containers = soup.select(container_sel)
            if containers:
                links = []
                for c in containers:
                    links.extend(c.select(article_sel))
            else:
                links = soup.select(article_sel)
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
            # 过滤明显非文章链接
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

        logger.info(f"Playwright [{name}]: {len(links)}个链接 -> 命中{len(articles)}条")
        return articles

    async def scrape_all(self) -> List[dict]:
        if not self._feeds:
            return []
        all_items = []
        await self.start()
        if not self._browser:
            return []
        try:
            for cfg in self._feeds:
                try:
                    items = await self.scrape_one(cfg)
                    all_items.extend(items)
                    # 源间随机延迟
                    await asyncio.sleep(random.uniform(3, 7))
                except Exception as e:
                    logger.error(f"Playwright源异常 [{cfg.get('name','?')}]: {e}")
            logger.info(f"Playwright采集完成: {len(all_items)}条")
            return all_items
        finally:
            await self.close()
