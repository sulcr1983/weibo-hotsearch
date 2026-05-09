"""HTTP会话管理器 V5.0 — 统一 aiohttp Session + cloudscraper fallback"""

import asyncio
import random
import ssl
from typing import Optional

import aiohttp

from v2.logger import get_logger
from v2.user_agents import get_random_ua

logger = get_logger('http')


def _build_ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


class SharedSession:
    """
    共享 HTTP 会话（替代各采集器的重复 _get_session 模式）

    Usage:
        async with SharedSession() as session:
            html = await session.fetch("https://...")
            html_cc = await session.fetch_with_cc("https://...")
    """

    def __init__(self, timeout: int = 25):
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None
        self._cc = None  # cloudscraper lazy

    async def __aenter__(self):
        import ssl as _ssl
        ctx = _ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = _ssl.CERT_NONE
        self._session = aiohttp.ClientSession(
            timeout=self._timeout,
            connector=aiohttp.TCPConnector(ssl=ctx, limit=10),
            headers={
                'User-Agent': get_random_ua(),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
            }
        )
        return self

    async def __aexit__(self, *args):
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    async def fetch(self, url: str, extra_headers: dict = None, timeout: int = 20) -> Optional[str]:
        if not self._session:
            return None
        kwargs = {}
        if extra_headers:
            kwargs['headers'] = extra_headers
        try:
            async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=timeout), **kwargs) as resp:
                return await resp.text() if resp.status in (200, 301, 302) else None
        except Exception as e:
            logger.debug(f"HTTP GET 失败: {url[:60]} - {e}")
            return None

    async def fetch_with_cc(self, url: str, timeout: int = 15) -> Optional[str]:
        """cloudscraper 兜底（用于 Cloudflare 站点）"""
        if self._cc is None:
            try:
                import cloudscraper
                self._cc = cloudscraper.create_scraper(
                    browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
                )
            except ImportError:
                logger.warning("cloudscraper 未安装，无法兜底")
                return None
        try:
            loop = asyncio.get_running_loop()
            r = await loop.run_in_executor(None, lambda: self._cc.get(url, timeout=timeout))
            return r.text if r.status_code == 200 else None
        except Exception as e:
            logger.debug(f"cloudscraper: {url[:60]} - {e}")
            return None