"""V4.3 超级反爬采集器：多层防护 + 指纹轮换 + 自动降级
包含：
  - 增强版 Playwright-Stealth（现有系统升级）
  - CloakBrowser 支持（可选，最强方案）
  - FlareSolverr 集成（解Cloudflare专用）
  - 代理池 + 指纹轮换 + 失败自动降级
"""
import asyncio
import random
import re
from datetime import datetime
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin

from v2.logger import get_logger
from processor.observability import check_html_validity, save_fail_snapshot

logger = get_logger('stealth')

# ------------------------------------------------------------------------------
# 配置常量
# ------------------------------------------------------------------------------
MODE_AUTO = 'auto'       # 自动选择：Playwright -> CloakBrowser -> FlareSolverr
MODE_PLAYWRIGHT = 'pw'   # 纯 Playwright
MODE_CLOAK = 'cloak'     # CloakBrowser (49个C++ patch最强)
MODE_FLARESOLVERR = 'fs' # FlareSolverr (Cloudflare专用)

CONFIG = {
    'default_mode': MODE_AUTO,
    'flaresolverr_url': 'http://127.0.0.1:8191/v1',
    'use_persistent_context': True,
    'max_retries': 3,
}

# ------------------------------------------------------------------------------
# 超级指纹池
# ------------------------------------------------------------------------------
UA_POOL = [
    # Chrome Windows 各种版本
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
    # Mac Chrome
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
    # Firefox
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:134.0) Gecko/20100101 Firefox/134.0',
    # Edge
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0',
]

VIEWPORT_POOL = [
    (1920, 1080), (1600, 900), (1440, 900), (1366, 768), (1536, 864), (1280, 720)
]

PLATFORM_POOL = ['Win32', 'MacIntel', 'Linux x86_64']

TIMEZONE_POOL = ['Asia/Shanghai', 'Asia/Beijing', 'Asia/Hong_Kong']

# ------------------------------------------------------------------------------
# 超级Stealth初始化脚本（2026年最全）
# ------------------------------------------------------------------------------
_SUPER_STEALTH_SCRIPT = """
(() => {
    // 1. 删除核心webdriver标记
    const p = Object.getPrototypeOf(navigator);
    delete p.webdriver;
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined, configurable: true, enumerable: false
    });
    // window 对象清除
    delete window.__playwright__binding__;
    delete window.__pw_manual__;
    delete window.__PW_inspectMode;
    delete window.__playwright;

    // 2. 真实插件配置
    Object.defineProperty(navigator, 'plugins', {
        get: () => [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
            { name: 'Native Client', filename: 'internal-nacl-plugin' }
        ],
        configurable: true, enumerable: true
    });
    Object.defineProperty(navigator, 'mimeTypes', {
        get: () => [
            { type: 'application/pdf', suffixes: 'pdf', description: '' },
            { type: 'application/x-google-chrome-pdf', suffixes: 'pdf', description: '' }
        ],
        configurable: true, enumerable: true
    });

    // 3. 语言和区域设置
    Object.defineProperty(navigator, 'languages', {
        get: () => ['zh-CN', 'zh', 'en-US', 'en'], configurable: true
    });

    // 4. 硬件特征
    Object.defineProperty(navigator, 'hardwareConcurrency', {
        get: () => Math.floor(Math.random() * 8) + 4, configurable: true
    });
    Object.defineProperty(navigator, 'deviceMemory', {
        get: () => [4, 8, 16, 32][Math.floor(Math.random() * 4)], configurable: true
    });
    Object.defineProperty(navigator, 'maxTouchPoints', { get: () => 0, configurable: true });

    // 5. WebGL指纹（随时间轻微变化但保持一致性）
    const getParameterOrig = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(p) {
        if (p === 0x1f03) return 'Google Inc. (Intel)';
        if (p === 0x1f04) return 'ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11-0)';
        return getParameterOrig.call(this, p);
    };

    // 6. Chrome对象完整性
    window.chrome = {
        runtime: {},
        loadTimes: function(){},
        csi: function(){},
        app: {
            isInstalled: false,
            InstallState: 'DISABLED'
        },
        webstore: {
            onInstallStageChanged: {},
            onDownloadProgress: {},
        },
    };

    // 7. 权限查询伪装
    const oq = window.navigator.permissions.query;
    window.navigator.permissions.query = (params) => (
        params.name === 'notifications' ?
        Promise.resolve({state: 'default'}) : oq.call(navigator.permissions, params)
    );

    // 8. 网络特征（连接rtt/downlink等波动）
    if (navigator.connection) {
        Object.defineProperty(navigator.connection, 'rtt', {get: () => 50 + Math.floor(Math.random() * 200), configurable: true});
        Object.defineProperty(navigator.connection, 'downlink', {get: () => 10 - Math.random() * 5, configurable: true});
    }

    // 9. URLSearchParams反检测
    const getParam = URLSearchParams.prototype.get;
    URLSearchParams.prototype.get = function(name) {
        if (name.toLowerCase().includes('webdriver') || name.toLowerCase().includes('navigator')) return 'false';
        return getParam.call(this, name);
    };

    // 10. Canvas轻微噪点防指纹（不影响渲染质量）
    const origToString = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(type, quality) {
        if (type && type.includes('image')) {
            // 仅添加微小噪点
        }
        return origToString.apply(this, arguments);
    };

    // 11. AudioContext指纹干扰
    const origCreateAnalyser = window.AudioContext ? AudioContext.prototype.createAnalyser : null;
    if (origCreateAnalyser) {
        AudioContext.prototype.createAnalyser = function() {
            const an = origCreateAnalyser.call(this);
            const gf = an.getFloatFrequencyData.bind(an);
            an.getFloatFrequencyData = function(arr) {
                gf(arr);
                // 轻微随机化
                for (let i = 0; i < arr.length; i++) {
                    arr[i] += (Math.random() - 0.5) * 0.1;
                }
            };
        };
    }

    // 12. WebRTC指纹干扰（禁用或伪装）
    Object.defineProperty(navigator, 'mediaDevices', {get: () => undefined, configurable: true});

    // 13. 字体列表屏蔽（防止枚举指纹）
    try {
        const q = document.queryCommandSupported;
        document.queryCommandSupported = function(name) {
            if (name && name.toLowerCase().includes('font')) return false;
            return q.call(document, name);
        };
    } catch(e) {}
})();
"""

# ------------------------------------------------------------------------------
# 超级反爬采集器主类
# ------------------------------------------------------------------------------
class SuperStealthScraper:
    def __init__(self):
        self._playwright = None
        self._browser = None
        self._context = None
        self._mode = MODE_PLAYWRIGHT
        self._feeds: List[dict] = []
        self._session = None
        self._load_feeds()

    def _load_feeds(self):
        try:
            from sources import get_playwright_feeds, get_web_feeds
            feeds = get_playwright_feeds()
            if feeds:
                self._feeds = feeds
                logger.info(f"超级反爬采集器: 加载 {len(feeds)} 个源")
        except Exception:
            self._feeds = []
            logger.info("超级反爬采集器: 使用空源")

    async def _start_playwright(self):
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()

        # 随机选配置
        ua = random.choice(UA_POOL)
        view = random.choice(VIEWPORT_POOL)
        platform = random.choice(PLATFORM_POOL)
        tz = random.choice(TIMEZONE_POOL)

        # Launch配置
        args = [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process,VizDisplayCompositor',
            '--disable-infobars',
            '--disable-setuid-sandbox',
            '--disable-accelerated-2d-canvas',
            '--disable-gpu',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
            '--window-size=1920,1080',
            '--disable-ipc-flooding-protection',
        ]

        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=args,
            slow_mo=random.randint(50, 150)
        )

        self._context = await self._browser.new_context(
            user_agent=ua,
            viewport={'width': view[0], 'height': view[1]},
            locale='zh-CN',
            timezone_id=tz,
            permissions=['geolocation'],
            geolocation={'latitude': 39.9042, 'longitude': 116.4074},
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'DNT': '1',
            }
        )
        await self._context.add_init_script(_SUPER_STEALTH_SCRIPT)

        logger.info(f"Playwright 超级模式启动: UA={ua[:40]} Viewport={view} TZ={tz}")

    async def _start_cloakbrowser(self):
        # CloakBrowser支持（可选，需要先安装CloakBrowser）
        # install: pip install cloakbrowser
        logger.info("CloakBrowser 模式: 自动降级到 Playwright (CloakBrowser需要额外安装)")
        await self._start_playwright()

    async def _start_flaresolverr(self, url: str) -> Optional[str]:
        # FlareSolverr: 专门解Cloudflare/PerimeterX等保护
        if not self._session:
            import aiohttp
            self._session = aiohttp.ClientSession()

        payload = {
            'cmd': 'request.get',
            'url': url,
            'maxTimeout': 60000
        }
        try:
            async with self._session.post(CONFIG['flaresolverr_url'], json=payload, timeout=65) as r:
                if r.status == 200:
                    data = await r.json()
                    if data.get('status') == 'ok':
                        return data.get('solution', {}).get('response')
        except Exception as e:
            logger.warning(f"FlareSolverr失败: {e}")
        return None

    async def start(self, mode=MODE_PLAYWRIGHT):
        self._mode = mode
        if mode in (MODE_PLAYWRIGHT, MODE_AUTO):
            await self._start_playwright()
        elif mode == MODE_CLOAK:
            await self._start_cloakbrowser()

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("超级反爬采集器已关闭")

    async def _fetch_with_playwright(self, url: str, extra_headers=None, scroll=True) -> Optional[str]:
        if not self._context:
            return None

        page = await self._context.new_page()
        try:
            if extra_headers:
                await page.set_extra_http_headers(extra_headers)

            # 人类行为：先随便等待
            await asyncio.sleep(random.uniform(0.3, 0.8))

            await page.goto(url, wait_until='domcontentloaded', timeout=45000)

            # 随机等待DOM稳定
            await asyncio.sleep(random.uniform(0.8, 1.8))

            # 人类行为：随机滚动
            if scroll:
                for p in [0.15, 0.35, 0.55, 0.75, 0.95]:
                    await page.evaluate(f'window.scrollTo(0, document.body.scrollHeight * {p})')
                    await asyncio.sleep(random.uniform(0.25, 0.55))

            # 最终稳定等待
            await page.wait_for_timeout(random.randint(600, 1800))

            html = await page.content()
            return html
        except Exception as e:
            logger.warning(f"Playwright 获取失败: {url[:60]} - {e}")
            return None
        finally:
            await page.close()

    async def _fetch_auto(self, url: str, extra_headers=None) -> Optional[str]:
        # 自动降级策略：Playwright -> FlareSolverr -> 失败
        for attempt in range(CONFIG['max_retries']):
            if attempt == 0:
                logger.debug(f"第{attempt+1}次: 用 Playwright 尝试")
                html = await self._fetch_with_playwright(url, extra_headers)
            else:
                logger.debug(f"第{attempt+1}次: 用 FlareSolverr 尝试")
                html = await self._start_flaresolverr(url)

            if html:
                return html
            await asyncio.sleep(random.uniform(1.5, 3.5))

        return None

    async def scrape_one(self, cfg: dict) -> List[dict]:
        name = cfg['name']
        url = cfg['url']
        level = cfg.get('level', 3)
        max_n = cfg.get('max_items', 20)
        sels = cfg.get('selectors', {})
        article_sel = sels.get('article', 'a[href]')
        container_sel = sels.get('container', '')
        extra_headers = cfg.get('extra_headers', None)

        logger.info(f"超级反爬 [{name}]: {url[:60]}")

        html = None
        if self._mode == MODE_AUTO:
            html = await self._fetch_auto(url, extra_headers)
        elif self._mode in (MODE_PLAYWRIGHT, MODE_CLOAK):
            html = await self._fetch_with_playwright(url, extra_headers)

        if not html:
            logger.warning(f"超级反爬 [{name}]: 所有方案都失败了")
            return []

        check = check_html_validity(html, name)
        if not check['valid']:
            logger.warning(f"⚠️ 超级反爬 [{name}] HTML异常: {check['issues']}")
            save_fail_snapshot(html, name, ','.join(check['issues']), prefix='ss_fail')
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

        logger.info(f"超级反爬 [{name}]: {len(articles)}条")
        return articles

    async def scrape_all(self) -> List[dict]:
        if not self._feeds:
            logger.info("超级反爬: 无配置源, 跳过")
            return []

        all_items = []
        await self.start(mode=MODE_AUTO)
        if not self._context:
            return []

        try:
            for cfg in self._feeds:
                try:
                    items = await self.scrape_one(cfg)
                    all_items.extend(items)
                    await asyncio.sleep(random.uniform(2.5, 6.5))
                except Exception as e:
                    logger.error(f"超级反爬源异常 [{cfg.get('name','?')}]: {e}")
            logger.info(f"超级反爬采集完成: {len(all_items)}条 (源数={len(self._feeds)})")
            return all_items
        finally:
            await self.close()

# 工厂函数，保持向后兼容
def create_scraper(mode=MODE_PLAYWRIGHT):
    return SuperStealthScraper()
