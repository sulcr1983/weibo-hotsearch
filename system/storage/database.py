"""统一数据库 — SQLite(WAL) + 异步写入队列 (V3)"""
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

SQL_WEIBO = '''CREATE TABLE IF NOT EXISTS weibo_hot (
    id INTEGER PRIMARY KEY AUTOINCREMENT, brand_group TEXT NOT NULL,
    title TEXT NOT NULL, link TEXT, label TEXT, is_hotgov INT DEFAULT 0,
    rank INT, created_at TEXT NOT NULL)'''

SQL_MONTHLY = '''CREATE TABLE IF NOT EXISTS monthly_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT, year_month TEXT NOT NULL,
    brand TEXT NOT NULL, keyword TEXT NOT NULL, count INT DEFAULT 1,
    created_at TEXT NOT NULL)'''

INDEXES_ARTICLES = [
    'CREATE INDEX IF NOT EXISTS idx_articles_brand ON articles(brand)',
    'CREATE INDEX IF NOT EXISTS idx_articles_event ON articles(event_id)',
    'CREATE INDEX IF NOT EXISTS idx_articles_created ON articles(created_at)',
    'CREATE INDEX IF NOT EXISTS idx_articles_pushed ON articles(is_pushed)',
    'CREATE INDEX IF NOT EXISTS idx_events_event ON events(event_id)',
]

INDEXES_WEIBO = [
    'CREATE INDEX IF NOT EXISTS idx_weibo_brand ON weibo_hot(brand_group)',
    'CREATE INDEX IF NOT EXISTS idx_weibo_created ON weibo_hot(created_at)',
    'CREATE INDEX IF NOT EXISTS idx_monthly_ym ON monthly_snapshot(year_month)',
    'CREATE INDEX IF NOT EXISTS idx_monthly_brand ON monthly_snapshot(brand)',
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
        await self._init_db(self.weibo_path, [SQL_WEIBO, SQL_MONTHLY], INDEXES_WEIBO)
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
            w = await db.execute('DELETE FROM weibo_hot WHERE created_at<?', (wcut,))
            await db.commit()
            logger.info(f"清理微博{w.rowcount}条")

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

    async def insert_weibo(self, item: dict):
        async with aiosqlite.connect(self.weibo_path) as db:
            # 去重：同品牌+同标题 24小时内只保留一条
            dup_cut = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
            cur = await db.execute(
                'SELECT 1 FROM weibo_hot WHERE brand_group=? AND title=? AND created_at>=? LIMIT 1',
                (item['brand_group'], item['title'], dup_cut))
            if await cur.fetchone():
                return
            await db.execute(
                'INSERT INTO weibo_hot (brand_group,title,link,label,is_hotgov,rank,created_at) VALUES (?,?,?,?,?,?,?)',
                (item['brand_group'], item['title'], item.get('link', ''), item.get('label', ''),
                 int(item.get('is_hotgov', False)), item.get('rank', 0), item['created_at']))
            await db.commit()

    async def get_weibo(self, hours: int = 24, limit: int = 200) -> List[dict]:
        cutoff = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
        async with aiosqlite.connect(self.weibo_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute('SELECT * FROM weibo_hot WHERE created_at>=? ORDER BY created_at DESC LIMIT ?', (cutoff, limit))
            return [dict(r) for r in await cur.fetchall()]

    async def get_weibo_monthly(self, year_month: str) -> List[dict]:
        async with aiosqlite.connect(self.weibo_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT brand_group,title,created_at FROM weibo_hot WHERE created_at LIKE ? || '%' ORDER BY created_at DESC", (year_month,))
            return [dict(r) for r in await cur.fetchall()]

    async def get_weibo_brand_stats(self, year_month: str) -> List[dict]:
        async with aiosqlite.connect(self.weibo_path) as db:
            cur = await db.execute(
                "SELECT brand_group, COUNT(*) as cnt FROM weibo_hot WHERE created_at LIKE ? || '%' GROUP BY brand_group ORDER BY cnt DESC",
                (year_month,))
            return [{'brand': r[0], 'count': r[1]} for r in await cur.fetchall()]

    @staticmethod
    def compute_url_hash(url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()
