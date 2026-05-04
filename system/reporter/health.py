"""来源健康仪表盘（V4.0）：成功/失败统计 + 详情"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import aiosqlite

from storage.database import Database
from v2.logger import get_logger

logger = get_logger('health')


class SourceHealth:
    def __init__(self, db: Database):
        self.db = db
        self._rss_results: Dict[str, dict] = {}
        self._web_results: Dict[str, dict] = {}
        self._auto_results: Dict[str, dict] = {}

    def record_rss(self, name: str, items: int, error: Optional[str] = None):
        self._rss_results[name] = {
            'name': name, 'type': 'RSS', 'items': items,
            'status': 'ok' if error is None else 'fail',
            'error': error or '', 'time': datetime.now().strftime('%H:%M:%S'),
        }

    def record_web(self, name: str, items: int, error: Optional[str] = None):
        self._web_results[name] = {
            'name': name, 'type': 'Web', 'items': items,
            'status': 'ok' if error is None else 'fail',
            'error': error or '', 'time': datetime.now().strftime('%H:%M:%S'),
        }

    def record_auto(self, name: str, items: int, error: Optional[str] = None):
        self._auto_results[name] = {
            'name': name, 'type': '垂媒', 'items': items,
            'status': 'ok' if error is None else 'fail',
            'error': error or '', 'time': datetime.now().strftime('%H:%M:%S'),
        }

    def summary(self) -> dict:
        all_sources = list(self._rss_results.values()) + list(self._web_results.values()) + list(self._auto_results.values())
        ok = [s for s in all_sources if s['status'] == 'ok']
        fail = [s for s in all_sources if s['status'] == 'fail']
        total_items = sum(s['items'] for s in ok)
        total_fail = len(fail)
        ok_names = [s['name'] for s in ok]
        fail_names = [s['name'] for s in fail]
        return {
            'total_sources': len(all_sources),
            'ok': len(ok),
            'fail': total_fail,
            'total_items': total_items,
            'ok_sources': ok_names,
            'fail_sources': fail_names,
            'by_type': {
                'RSS': [s for s in all_sources if s['type'] == 'RSS'],
                'Web': [s for s in all_sources if s['type'] == 'Web'],
                '垂媒': [s for s in all_sources if s['type'] == '垂媒'],
            },
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

    async def db_stats(self) -> dict:
        """从 DB 统计实际入库的品牌分布"""
        try:
            async with aiosqlite.connect(self.db.db_path) as c:
                c.row_factory = aiosqlite.Row
                cur = await c.execute("SELECT brand, COUNT(*) as cnt FROM articles WHERE created_at >= ? GROUP BY brand ORDER BY cnt DESC",
                                      ((datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S'),))
                rows = await cur.fetchall()
                return {
                    'articles_24h': sum(r['cnt'] for r in rows),
                    'by_brand': [{'brand': r['brand'], 'count': r['cnt']} for r in rows],
                }
        except Exception:
            return {'articles_24h': 0, 'by_brand': []}
