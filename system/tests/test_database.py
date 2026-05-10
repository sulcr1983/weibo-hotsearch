"""数据库模块单元测试 — 覆盖 CRUD/去重/统计/清理（内存 SQLite）"""

import asyncio
import json
import pytest
from datetime import datetime, timedelta


async def _direct_insert(db, record):
    """绕过 worker 直接插入（避免异步队列时序问题）"""
    import aiosqlite
    async with aiosqlite.connect(db.db_path) as conn:
        await conn.execute(
            'INSERT OR IGNORE INTO articles (url_hash,title,url,source,source_level,brand,keywords,content,simhash,event_id,summary,score,score_tier,is_pushed,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (record['url_hash'], record['title'], record['url'], record['source'],
             record.get('source_level', 1), record['brand'], record.get('keywords'),
             record.get('content'), record.get('simhash'), record.get('event_id'),
             record.get('summary'), record.get('score', 50), record.get('score_tier', 'weak'),
             0, record.get('created_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))))
        await conn.commit()


class TestDatabaseLifecycle:
    @pytest.mark.asyncio
    async def test_start_creates_tables(self, in_memory_db):
        import aiosqlite
        async with aiosqlite.connect(in_memory_db.db_path) as db:
            cur = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = [r[0] for r in await cur.fetchall()]
        assert 'articles' in tables
        assert 'events' in tables

    @pytest.mark.asyncio
    async def test_insert_and_count(self, in_memory_db, article_record):
        await _direct_insert(in_memory_db, article_record)
        cnt = await in_memory_db.count_articles()
        assert cnt >= 1

    @pytest.mark.asyncio
    async def test_article_exists(self, in_memory_db, article_record):
        await _direct_insert(in_memory_db, article_record)
        assert await in_memory_db.article_exists(article_record['url_hash']) is True
        assert await in_memory_db.article_exists('nonexistent') is False

    @pytest.mark.asyncio
    async def test_queue_worker(self, in_memory_db, article_record):
        """验证 worker 队列能正常消费"""
        in_memory_db.enqueue('insert_article', article_record)
        await asyncio.sleep(0.5)
        cnt = await in_memory_db.count_articles()
        assert cnt >= 1


class TestWeiboEvents:
    @pytest.mark.asyncio
    async def test_upsert_new(self, in_memory_db):
        r = await in_memory_db.upsert_weibo_event(
            keyword="比亚迪秦L",
            brand="比亚迪",
            link="https://s.weibo.com/123",
            label="热门",
            heat=2580000,
        )
        assert r['is_new'] is True

    @pytest.mark.asyncio
    async def test_upsert_existing(self, in_memory_db):
        await in_memory_db.upsert_weibo_event("比亚迪秦L", "比亚迪")
        r = await in_memory_db.upsert_weibo_event("比亚迪秦L", "比亚迪")
        assert r['is_new'] is False

    @pytest.mark.asyncio
    async def test_count_weibo_events(self, in_memory_db):
        await in_memory_db.upsert_weibo_event("比亚迪秦L", "比亚迪")
        await in_memory_db.upsert_weibo_event("小米SU7", "小米")
        cnt = await in_memory_db.count_weibo_events()
        assert cnt >= 2


class TestQueryAndStats:
    @pytest.mark.asyncio
    async def test_get_articles_by_brand(self, in_memory_db):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        rec = {
            'url_hash': 'test_hash_get_articles',
            'title': '比亚迪秦L销量突破2万辆',
            'url': 'https://test.com/1',
            'source': '新浪汽车', 'source_level': 1, 'brand': '比亚迪',
            'content': '比亚迪秦L销量',
            'created_at': now,
        }
        await _direct_insert(in_memory_db, rec)
        arts = await in_memory_db.get_articles(brand='比亚迪')
        assert len(arts) >= 1
        assert arts[0]['title'] == rec['title']

    @pytest.mark.asyncio
    async def test_count_methods(self, in_memory_db, article_record):
        await _direct_insert(in_memory_db, article_record)
        await in_memory_db.upsert_weibo_event("比亚迪秦L", "比亚迪")
        assert await in_memory_db.count_articles() >= 1
        assert await in_memory_db.count_weibo_events() >= 1


class TestCleanup:
    @pytest.mark.asyncio
    async def test_end_stale_events(self, in_memory_db):
        from datetime import datetime as dt
        import aiosqlite
        now = dt.now().strftime('%Y-%m-%d %H:%M:%S')
        async with aiosqlite.connect(in_memory_db.weibo_path) as db:
            await db.execute(
                "INSERT INTO hotsearch_events (keyword,brand,first_seen_at,last_seen_at,status) VALUES (?,?,?,?,?)",
                ("stale_event", "比亚迪", "2026-01-01 00:00:00", "2026-01-01 00:00:00", "active"))
            await db.commit()
        await in_memory_db.end_stale_events(hours=0)
        events = await in_memory_db.get_weibo_events(status='ended', hours=0)
        assert len(events) >= 1