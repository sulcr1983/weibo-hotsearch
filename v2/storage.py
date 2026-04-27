import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional

import aiosqlite

from v2.constants import DATA_RETENTION_DAYS, QUEUE_MAXSIZE
from v2.logger import get_logger

logger = get_logger('storage')

SQL_CREATE_ARTICLES = '''
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_hash TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    source TEXT NOT NULL,
    source_level INT DEFAULT 1,
    brand TEXT NOT NULL,
    keywords TEXT,
    content TEXT,
    simhash TEXT,
    event_id TEXT,
    summary TEXT,
    is_pushed INT DEFAULT 0,
    push_date TEXT,
    created_at TEXT NOT NULL
)
'''

SQL_CREATE_EVENTS = '''
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE NOT NULL,
    brand TEXT NOT NULL,
    title TEXT NOT NULL,
    keywords TEXT,
    article_count INT DEFAULT 1,
    sources TEXT,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL
)
'''

SQL_INDEXES = [
    'CREATE INDEX IF NOT EXISTS idx_articles_brand ON articles(brand)',
    'CREATE INDEX IF NOT EXISTS idx_articles_event_id ON articles(event_id)',
    'CREATE INDEX IF NOT EXISTS idx_articles_simhash ON articles(simhash)',
    'CREATE INDEX IF NOT EXISTS idx_articles_created_at ON articles(created_at)',
    'CREATE INDEX IF NOT EXISTS idx_articles_is_pushed ON articles(is_pushed)',
    'CREATE INDEX IF NOT EXISTS idx_events_brand ON events(brand)',
    'CREATE INDEX IF NOT EXISTS idx_events_event_id ON events(event_id)',
]

SQL_PRAGMAS = [
    'PRAGMA journal_mode=WAL',
    'PRAGMA synchronous=NORMAL',
    'PRAGMA cache_size=-64000',
    'PRAGMA temp_store=MEMORY',
]


class DataVault:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
        self._writer_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        await self._init_db()
        self._running = True
        self._writer_task = asyncio.create_task(self._write_worker())
        logger.info("DataVault 启动成功")

    async def stop(self):
        if self._writer_task:
            await self._queue.put(None)
        self._running = False
        if self._writer_task:
            try:
                await asyncio.wait_for(self._writer_task, timeout=10)
            except asyncio.TimeoutError:
                self._writer_task.cancel()
        logger.info("DataVault 已停止")

    async def _init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            for pragma in SQL_PRAGMAS:
                await db.execute(pragma)
            await db.execute(SQL_CREATE_ARTICLES)
            await db.execute(SQL_CREATE_EVENTS)
            for idx_sql in SQL_INDEXES:
                await db.execute(idx_sql)
            await db.commit()
        logger.info("数据库初始化完成 (WAL模式)")

    async def _write_worker(self):
        while self._running:
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            if item is None:
                break

            op = item.get('op')
            data = item.get('data')
            try:
                if op == 'insert_article':
                    await self._do_insert_article(data)
                elif op == 'update_event':
                    await self._do_update_event(data)
                elif op == 'mark_pushed':
                    await self._do_mark_pushed(data)
                elif op == 'clean_old':
                    await self._do_clean_old(data)
                else:
                    logger.warning(f"未知写操作: {op}")
            except Exception as e:
                logger.error(f"写操作失败 [{op}]: {e}")

    async def _do_insert_article(self, article: dict, retries: int = 3):
        for attempt in range(retries):
            try:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute(
                        '''INSERT OR IGNORE INTO articles
                           (url_hash, title, url, source, source_level, brand, keywords,
                            content, simhash, event_id, summary, is_pushed, push_date, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (
                            article['url_hash'],
                            article['title'],
                            article['url'],
                            article['source'],
                            article.get('source_level', 1),
                            article['brand'],
                            article.get('keywords'),
                            article.get('content'),
                            article.get('simhash'),
                            article.get('event_id'),
                            article.get('summary'),
                            0,
                            None,
                            article.get('created_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                        )
                    )
                    await db.commit()
                logger.info(f"文章入库: [{article['brand']}] {article['title'][:30]}")
                return True
            except Exception as e:
                if attempt < retries - 1:
                    wait = 2 ** attempt
                    logger.warning(f"文章写入重试 ({attempt + 1}/{retries}): {e}")
                    await asyncio.sleep(wait)
                else:
                    logger.error(f"文章写入最终失败: {e}")
                    return False
        return False

    async def _do_update_event(self, data: dict):
        event_id = data['event_id']
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                'SELECT id, article_count, sources FROM events WHERE event_id = ?',
                (event_id,)
            )
            row = await cursor.fetchone()

            if row:
                new_count = row[1] + 1
                old_sources = json.loads(row[2]) if row[2] else []
                new_source = data.get('source', '')
                if new_source and new_source not in old_sources:
                    old_sources.append(new_source)

                await db.execute(
                    '''UPDATE events SET article_count = ?, sources = ?, last_seen = ?
                       WHERE event_id = ?''',
                    (new_count, json.dumps(old_sources, ensure_ascii=False),
                     datetime.now().strftime('%Y-%m-%d %H:%M:%S'), event_id)
                )
            else:
                await db.execute(
                    '''INSERT OR IGNORE INTO events
                       (event_id, brand, title, keywords, article_count, sources, first_seen, last_seen)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        event_id,
                        data['brand'],
                        data['title'],
                        data.get('keywords'),
                        1,
                        json.dumps([data.get('source', '')], ensure_ascii=False),
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    )
                )
            await db.commit()

    async def _do_mark_pushed(self, data: dict):
        ids = data.get('ids', [])
        push_date = data.get('push_date', datetime.now().strftime('%Y-%m-%d'))
        if not ids:
            return
        async with aiosqlite.connect(self.db_path) as db:
            placeholders = ','.join(['?'] * len(ids))
            await db.execute(
                f'UPDATE articles SET is_pushed = 1, push_date = ? WHERE id IN ({placeholders})',
                [push_date] + ids
            )
            await db.commit()
        logger.info(f"标记已推送: {len(ids)} 条文章")

    async def _do_clean_old(self, data: dict):
        days = data.get('days', DATA_RETENTION_DAYS)
        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        async with aiosqlite.connect(self.db_path) as db:
            cursor_a = await db.execute(
                'DELETE FROM articles WHERE created_at < ?', (cutoff,)
            )
            deleted_articles = cursor_a.rowcount

            cursor_e = await db.execute(
                'DELETE FROM events WHERE last_seen < ?', (cutoff,)
            )
            deleted_events = cursor_e.rowcount
            await db.commit()
        logger.info(f"清理 {days} 天前数据: 文章 {deleted_articles} 条, 事件 {deleted_events} 条")

    def insert_article(self, article: dict) -> bool:
        if self._queue.full():
            logger.warning("写入队列已满，丢弃文章")
            return False
        try:
            self._queue.put_nowait({'op': 'insert_article', 'data': article})
            return True
        except asyncio.QueueFull:
            return False

    async def insert_article_sync(self, article: dict) -> bool:
        return await self._do_insert_article(article)

    def update_event(self, event_id: str, brand: str, title: str,
                     source: str = '', keywords: str = None):
        try:
            self._queue.put_nowait({
                'op': 'update_event',
                'data': {
                    'event_id': event_id,
                    'brand': brand,
                    'title': title,
                    'source': source,
                    'keywords': keywords,
                }
            })
        except asyncio.QueueFull:
            logger.warning("写入队列已满，丢弃事件更新")

    def mark_pushed(self, ids: list, push_date: str = None):
        try:
            self._queue.put_nowait({
                'op': 'mark_pushed',
                'data': {'ids': ids, 'push_date': push_date}
            })
        except asyncio.QueueFull:
            logger.warning("写入队列已满，丢弃推送标记")

    def clean_old_data(self, days: int = DATA_RETENTION_DAYS):
        try:
            self._queue.put_nowait({'op': 'clean_old', 'data': {'days': days}})
        except asyncio.QueueFull:
            logger.warning("写入队列已满，丢弃清理任务")

    async def get_articles(self, brand: str = None, hours: int = 24,
                           is_pushed: int = None, limit: int = 100) -> List[dict]:
        cutoff = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            conditions = ['created_at >= ?']
            params = [cutoff]

            if brand:
                conditions.append('brand = ?')
                params.append(brand)
            if is_pushed is not None:
                conditions.append('is_pushed = ?')
                params.append(is_pushed)

            where = ' AND '.join(conditions)
            params.append(limit)

            async with db.execute(
                f'SELECT * FROM articles WHERE {where} ORDER BY created_at DESC LIMIT ?',
                params
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_events(self, brand: str = None, days: int = 7,
                         limit: int = 100) -> List[dict]:
        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            conditions = ['last_seen >= ?']
            params = [cutoff]

            if brand:
                conditions.append('brand = ?')
                params.append(brand)

            where = ' AND '.join(conditions)
            params.append(limit)

            async with db.execute(
                f'SELECT * FROM events WHERE {where} ORDER BY last_seen DESC LIMIT ?',
                params
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_similar_articles(self, brand: str, hours: int = 48) -> List[dict]:
        cutoff = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                'SELECT id, title, simhash, event_id FROM articles WHERE brand = ? AND created_at >= ?',
                (brand, cutoff)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def article_exists(self, url_hash: str) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                'SELECT 1 FROM articles WHERE url_hash = ? LIMIT 1', (url_hash,)
            ) as cursor:
                row = await cursor.fetchone()
                return row is not None

    @staticmethod
    def compute_url_hash(url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()
