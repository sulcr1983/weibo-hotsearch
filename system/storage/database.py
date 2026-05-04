"""统一数据库 — SQLite(WAL) + 异步写入队列 (V4.1)"""
import asyncio
import hashlib
import json
from datetime import datetime, timedelta
from typing import List, Optional

import aiosqlite

from config import NEWS_RETENTION_DAYS, WEIBO_RETENTION_DAYS
from v2.logger import get_logger

logger = get_logger('db')

SQL_ARTICLES = '''CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT, url_hash TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL, url TEXT NOT NULL, source TEXT NOT NULL,
    source_level INT DEFAULT 1, brand TEXT NOT NULL, keywords TEXT,
    content TEXT, simhash TEXT, event_id TEXT, summary TEXT,
    is_pushed INT DEFAULT 0, push_date TEXT, created_at TEXT NOT NULL)'''

SQL_EVENTS = '''CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL,
    brand TEXT NOT NULL, title TEXT NOT NULL, keywords TEXT,
    article_count INT DEFAULT 1, sources TEXT,
    first_seen TEXT NOT NULL, last_seen TEXT NOT NULL)'''

SQL_WEIBO = '''CREATE TABLE IF NOT EXISTS hotsearch_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL, brand TEXT NOT NULL,
    link TEXT, label TEXT, heat INT DEFAULT 0,
    first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
    appear_count INT DEFAULT 1, status TEXT DEFAULT "active",
    UNIQUE(keyword, brand))'''

INDEXES_ARTICLES = [
    'CREATE INDEX IF NOT EXISTS idx_articles_brand ON articles(brand)',
    'CREATE INDEX IF NOT EXISTS idx_articles_event ON articles(event_id)',
    'CREATE INDEX IF NOT EXISTS idx_articles_created ON articles(created_at)',
    'CREATE INDEX IF NOT EXISTS idx_articles_pushed ON articles(is_pushed)',
    'CREATE INDEX IF NOT EXISTS idx_events_event ON events(event_id)',
]

INDEXES_WEIBO = [
    'CREATE INDEX IF NOT EXISTS idx_he_brand ON hotsearch_events(brand)',
    'CREATE INDEX IF NOT EXISTS idx_he_status ON hotsearch_events(status)',
    'CREATE INDEX IF NOT EXISTS idx_he_first ON hotsearch_events(first_seen_at)',
]

PRAGMAS = [
    'PRAGMA journal_mode=WAL',
    'PRAGMA synchronous=NORMAL',
    'PRAGMA cache_size=-64000',
    'PRAGMA temp_store=MEMORY',
]


class Database:
    def __init__(self, db_path: str, weibo_path: str):
        self.db_path = db_path
        self.weibo_path = weibo_path
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._running = False
        self._writer: Optional[asyncio.Task] = None

    async def start(self):
        await self._init_db(self.db_path, [SQL_ARTICLES, SQL_EVENTS], INDEXES_ARTICLES)
        await self._init_db(self.weibo_path, [SQL_WEIBO], INDEXES_WEIBO)
        self._running = True
        self._writer = asyncio.create_task(self._worker())
        logger.info("数据库启动 (WAL模式)")

    async def stop(self):
        self._running = False
        await self._queue.put(None)
        if self._writer:
            try:
                await asyncio.wait_for(self._writer, timeout=10)
            except asyncio.TimeoutError:
                self._writer.cancel()

    async def _init_db(self, path: str, tables: list, indexes: list):
        async with aiosqlite.connect(path) as db:
            for pragma in PRAGMAS:
                await db.execute(pragma)
            for sql in tables + indexes:
                await db.execute(sql)
            await db.commit()

    async def _worker(self):
        while self._running:
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            if item is None:
                break
            op, data = item.get('op'), item.get('data')
            try:
                if op == 'insert_article':
                    await self._do_insert(data)
                elif op == 'update_event':
                    await self._do_event(data)
                elif op == 'mark_pushed':
                    await self._do_mark_pushed(data)
                elif op == 'clean':
                    await self._do_clean(data)
            except Exception as e:
                logger.error(f"写操作失败 [{op}]: {e}")

    async def _do_insert(self, a: dict):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'INSERT OR IGNORE INTO articles (url_hash,title,url,source,source_level,brand,keywords,content,simhash,event_id,summary,is_pushed,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (a['url_hash'], a['title'], a['url'], a['source'], a.get('source_level', 1),
                 a['brand'], a.get('keywords'), a.get('content'), a.get('simhash'),
                 a.get('event_id'), a.get('summary'), 0, a.get('created_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))))
            await db.commit()
        logger.info(f"入库: [{a['brand']}] {a['title'][:30]}")

    async def _do_event(self, d: dict):
        eid = d['event_id']
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute('SELECT id,article_count,sources FROM events WHERE event_id=?', (eid,))
            row = await cur.fetchone()
            if row:
                nc = row[1] + 1
                ss = json.loads(row[2]) if row[2] else []
                ns = d.get('source', '')
                if ns and ns not in ss:
                    ss.append(ns)
                await db.execute('UPDATE events SET article_count=?,sources=?,last_seen=? WHERE event_id=?',
                                 (nc, json.dumps(ss, ensure_ascii=False), datetime.now().strftime('%Y-%m-%d %H:%M:%S'), eid))
            else:
                await db.execute(
                    'INSERT OR IGNORE INTO events (event_id,brand,title,keywords,article_count,sources,first_seen,last_seen) VALUES (?,?,?,?,?,?,?,?)',
                    (eid, d['brand'], d['title'], d.get('keywords'), 1,
                     json.dumps([d.get('source', '')], ensure_ascii=False),
                     datetime.now().strftime('%Y-%m-%d %H:%M:%S'), datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            await db.commit()

    async def _do_mark_pushed(self, d: dict):
        ids = d.get('ids', [])
        if not ids:
            return
        async with aiosqlite.connect(self.db_path) as db:
            ph = ','.join(['?'] * len(ids))
            await db.execute(f'UPDATE articles SET is_pushed=1,push_date=? WHERE id IN ({ph})',
                             [d.get('push_date', datetime.now().strftime('%Y-%m-%d'))] + ids)
            await db.commit()
        logger.info(f"标记已推送: {len(ids)}条")

    async def _do_clean(self, d: dict):
        cutoff = (datetime.now() - timedelta(days=NEWS_RETENTION_DAYS)).strftime('%Y-%m-%d %H:%M:%S')
        async with aiosqlite.connect(self.db_path) as db:
            a = await db.execute('DELETE FROM articles WHERE created_at<?', (cutoff,))
            e = await db.execute('DELETE FROM events WHERE last_seen<?', (cutoff,))
            await db.commit()
            logger.info(f"清理文章{a.rowcount}条,事件{e.rowcount}条")
        wcut = (datetime.now() - timedelta(days=WEIBO_RETENTION_DAYS)).strftime('%Y-%m-%d %H:%M:%S')
        async with aiosqlite.connect(self.weibo_path) as db:
            w = await db.execute("DELETE FROM hotsearch_events WHERE status='ended' AND last_seen_at<?", (wcut,))
            await db.commit()
            logger.info(f"清理已结束微博事件 {w.rowcount} 条")

    def enqueue(self, op: str, data: dict):
        try:
            self._queue.put_nowait({'op': op, 'data': data})
        except asyncio.QueueFull:
            logger.warning("写入队列满，丢弃")

    def update_event(self, event_id: str, brand: str, title: str,
                     source: str = '', keywords: str = None):
        """cluster_article 直接调用的同步接口"""
        self.enqueue('update_event', {
            'event_id': event_id, 'brand': brand, 'title': title,
            'source': source, 'keywords': keywords,
        })

    async def article_exists(self, url_hash: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute('SELECT 1 FROM articles WHERE url_hash=? LIMIT 1', (url_hash,))
            return await cur.fetchone() is not None

    async def get_articles(self, brand: str = None, hours: int = 24, is_pushed: int = None, limit: int = 100) -> List[dict]:
        cutoff = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
        conds, params = ['created_at>=?'], [cutoff]
        if brand:
            conds.append('brand=?'); params.append(brand)
        if is_pushed is not None:
            conds.append('is_pushed=?'); params.append(is_pushed)
        params.append(limit)
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(f'SELECT * FROM articles WHERE {" AND ".join(conds)} ORDER BY created_at DESC LIMIT ?', params)
            return [dict(r) for r in await cur.fetchall()]

    async def get_similar_articles(self, brand: str, hours: int = 48) -> List[dict]:
        cutoff = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute('SELECT id,title,simhash,event_id FROM articles WHERE brand=? AND created_at>=?', (brand, cutoff))
            return [dict(r) for r in await cur.fetchall()]

    async def upsert_weibo_event(self, keyword: str, brand: str, link: str = '',
                                   label: str = '', heat: int = 0) -> dict:
        """微博热搜事件 upsert。返回 {'is_new': bool, 'event': dict}"""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        async with aiosqlite.connect(self.weibo_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                'SELECT id,appear_count,status FROM hotsearch_events WHERE keyword=? AND brand=?',
                (keyword, brand))
            existing = await cur.fetchone()
            if existing:
                await db.execute(
                    'UPDATE hotsearch_events SET last_seen_at=?,appear_count=?,status="active" WHERE id=?',
                    (now, existing['appear_count'] + 1, existing['id']))
                await db.commit()
                return {'is_new': False, 'event': dict(existing)}
            else:
                await db.execute(
                    'INSERT INTO hotsearch_events (keyword,brand,link,label,heat,first_seen_at,last_seen_at,appear_count,status) VALUES (?,?,?,?,?,?,?,1,"active")',
                    (keyword, brand, link, label, heat, now, now))
                await db.commit()
                cur2 = await db.execute('SELECT * FROM hotsearch_events WHERE rowid=last_insert_rowid()')
                return {'is_new': True, 'event': dict(await cur2.fetchone())}

    async def end_stale_events(self, hours: int = 3):
        """将超过 hours 小时未再出现的 active 事件标记为 ended"""
        cutoff = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
        async with aiosqlite.connect(self.weibo_path) as db:
            cur = await db.execute(
                'UPDATE hotsearch_events SET status="ended" WHERE status="active" AND last_seen_at<?',
                (cutoff,))
            await db.commit()
            if cur.rowcount:
                logger.info(f"微博事件收尾: {cur.rowcount} 条标记为 ended")

    async def get_weibo_events(self, hours: int = 24, status: str = None, limit: int = 200) -> List[dict]:
        """获取微博热搜事件列表"""
        conds = []
        params = []
        if hours:
            cutoff = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
            conds.append('first_seen_at>=?')
            params.append(cutoff)
        if status:
            conds.append('status=?')
            params.append(status)
        params.append(limit)
        where = f'WHERE {" AND ".join(conds)}' if conds else ''
        async with aiosqlite.connect(self.weibo_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                f'SELECT * FROM hotsearch_events {where} ORDER BY first_seen_at DESC LIMIT ?', params)
            return [dict(r) for r in await cur.fetchall()]

    async def get_weibo_monthly(self, year_month: str) -> List[dict]:
        """月度统计：按品牌、关键词聚合，含 appear_count 和持续时长"""
        async with aiosqlite.connect(self.weibo_path) as db:
            cur = await db.execute(
                "SELECT keyword, brand, link, appear_count, first_seen_at, last_seen_at, status "
                "FROM hotsearch_events WHERE first_seen_at LIKE ? || '%' "
                "ORDER BY appear_count DESC", (year_month,))
            return [{'keyword': r[0], 'brand': r[1], 'link': r[2],
                     'appear_count': r[3], 'first_seen_at': r[4],
                     'last_seen_at': r[5], 'status': r[6]} for r in await cur.fetchall()]

    async def get_weibo_brand_stats(self, year_month: str) -> List[dict]:
        """品牌维度月度统计"""
        async with aiosqlite.connect(self.weibo_path) as db:
            cur = await db.execute(
                "SELECT brand, COUNT(*) as event_count, SUM(appear_count) as total_appears "
                "FROM hotsearch_events WHERE first_seen_at LIKE ? || '%' "
                "GROUP BY brand ORDER BY total_appears DESC", (year_month,))
            return [{'brand': r[0], 'event_count': r[1], 'total_appears': r[2]}
                    for r in await cur.fetchall()]

    @staticmethod
    def compute_url_hash(url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()
