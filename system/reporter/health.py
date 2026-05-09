"""来源健康仪表盘 V5.0 — 重构：移除私有属性访问，record方法统一"""
from datetime import datetime, timedelta
from typing import Dict, Optional

import aiosqlite

from storage.database import Database
from v2.logger import get_logger

logger = get_logger('health')


class SourceHealth:
    def __init__(self, db: Database):
        self.db = db
        self._results: Dict[str, dict] = {}

    def _record(self, source_type: str, name: str, items: int, error: Optional[str] = None):
        self._results[name] = {
            'name': name, 'type': source_type, 'items': items,
            'status': 'ok' if error is None else 'fail',
            'error': error or '', 'time': datetime.now().strftime('%H:%M:%S'),
        }

    def record_rss(self, name: str, items: int, error: Optional[str] = None):
        self._record('RSS', name, items, error)

    def record_web(self, name: str, items: int, error: Optional[str] = None):
        self._record('Web', name, items, error)

    def record_auto(self, name: str, items: int, error: Optional[str] = None):
        self._record('垂媒', name, items, error)

    def record_pw(self, name: str, items: int, error: Optional[str] = None):
        self._record('Playwright', name, items, error)

    def record_stealth(self, name: str, items: int, error: Optional[str] = None):
        self._record('SuperStealth', name, items, error)

    def summary(self) -> dict:
        all_sources = list(self._results.values())
        ok = [s for s in all_sources if s['status'] == 'ok']
        fail = [s for s in all_sources if s['status'] == 'fail']
        return {
            'total_sources': len(all_sources),
            'ok': len(ok), 'fail': len(fail),
            'total_items': sum(s['items'] for s in ok),
            'ok_sources': [s['name'] for s in ok],
            'fail_sources': [s['name'] for s in fail],
            'by_type': {
                'RSS': [s for s in all_sources if s['type'] == 'RSS'],
                'Web': [s for s in all_sources if s['type'] == 'Web'],
                '垂媒': [s for s in all_sources if s['type'] == '垂媒'],
                'Playwright': [s for s in all_sources if s['type'] == 'Playwright'],
                'SuperStealth': [s for s in all_sources if s['type'] == 'SuperStealth'],
            },
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }

    async def db_stats(self) -> dict:
        result = {'articles_24h': 0, 'by_brand': [], 'queue_size': 0, 'queue_maxsize': 500}
        try:
            async with aiosqlite.connect(self.db.db_path) as c:
                c.row_factory = aiosqlite.Row
                cur = await c.execute(
                    "SELECT brand, COUNT(*) as cnt FROM articles WHERE created_at >= ? GROUP BY brand ORDER BY cnt DESC",
                    ((datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S'),))
                rows = await cur.fetchall()
                result['articles_24h'] = sum(r['cnt'] for r in rows)
                result['by_brand'] = [{'brand': r['brand'], 'count': r['cnt']} for r in rows]
        except Exception:
            pass
        try:
            result['queue_size'] = getattr(self.db, 'queue_size', 0)
            result['queue_maxsize'] = 500
        except Exception:
            pass
        return result