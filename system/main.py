#!/usr/bin/env python3
"""汽车行业舆情监控 V4.0 — 统一入口"""
import asyncio
import gc
import json
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from config import (
    SYSTEM_DIR, DB_PATH, WEIBO_DB_PATH,
    AI_API_KEY, AI_API_URL, AI_MODEL,
    FEISHU_WEBHOOK_URL, EMAIL_SENDER, EMAIL_PASSWORD,
    EMAIL_RECIPIENTS, SMTP_SERVER, SMTP_PORT,
)
from storage.database import Database
from collector.rss_fetcher import RssFetcher
from collector.web_scraper import WebScraper
from collector.weibo_collector import collect as weibo_collect
from collector.auto_media import AutoScraper
from processor.brand_matcher import match_brand, strip_html, is_financial_brief, is_digest, is_ugc, is_opinion
from processor.keyworder import extract_keywords
from processor.deduplicator import compute_simhash, cluster_article
from processor.classifier import classify_dimension
from processor.llm_classifier import classify_with_llm
from reporter.builder import ReportBuilder
from reporter.feishu import send_daily as feishu_daily, send_weekly as feishu_weekly, send_monthly as feishu_monthly
from reporter.emailer import Emailer
from reporter.ai_writer import weekly_summary, monthly_summary
from reporter.health import SourceHealth
from v2.logger import get_logger

logger = get_logger('main')
db = Database(DB_PATH, WEIBO_DB_PATH)
rss = RssFetcher()
web = WebScraper()
auto = AutoScraper()
health = SourceHealth(db)
builder = ReportBuilder(db)
emailer = Emailer(EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENTS, SMTP_SERVER, SMTP_PORT)
scheduler = AsyncIOScheduler()
_session: 'aiohttp.ClientSession | None' = None


async def get_weibo_session():
    global _session
    if _session is None or _session.closed:
        import aiohttp
        _session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
    return _session


async def news_collect():
    logger.info(f"📥 新闻采集: {datetime.now().strftime('%H:%M')}")
    try:
        rss_items = await rss.fetch_all()
        health.record_rss('RSS聚合', len(rss_items))
        web_items = await web.scrape_all()
        health.record_web('Web抓取', len(web_items))
        auto_items = await auto.scrape_all()
        health.record_auto('汽车垂媒', len(auto_items))
        all_items = rss_items + web_items + auto_items
        logger.info(f"采集: RSS {len(rss_items)} + Web {len(web_items)} + 垂媒 {len(auto_items)} = {len(all_items)}")
        enriched = 0
        for raw in all_items:
            try:
                if not isinstance(raw, dict):
                    continue
                title = raw.get('title', '').strip()
                content_raw = raw.get('content', '') or raw.get('rss_summary', '')
                content = strip_html(content_raw)
                brand, _ = match_brand(title, content)
                if not brand:
                    continue
                if is_digest(title):
                    continue
                if is_ugc(title):
                    continue
                if is_opinion(title, raw.get('source', '')):
                    continue
                dim = classify_dimension(title, content)
                if not dim:
                    dim = await classify_with_llm(title, content, AI_API_KEY, AI_API_URL, AI_MODEL)
                if not dim:
                    continue
                if is_financial_brief(title, content):
                    continue
                uh = db.compute_url_hash(raw['url'])
                if await db.article_exists(uh):
                    continue
                kws = extract_keywords(title + ' ' + content)
                sh = compute_simhash(title[:200] + ' ' + content[:300])
                art_time = raw.get('published') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                article = {
                    'url_hash': uh, 'title': title, 'url': raw['url'],
                    'source': raw['source'], 'source_level': raw.get('source_level', 3),
                    'brand': brand, 'keywords': json.dumps(kws, ensure_ascii=False) if kws else '[]',
                    'content': content[:800],
                    'simhash': sh, 'event_id': None, 'summary': None,
                    'created_at': art_time,
                }
                eid = await cluster_article(article, db)
                article['event_id'] = eid
                db.enqueue('insert_article', article)
                enriched += 1
            except Exception as e:
                logger.error(f"处理失败: {e}")
        logger.info(f"📥 入库 {enriched} 条")
    except Exception as e:
        logger.error(f"采集异常: {e}")


async def weibo_collect_task():
    logger.info(f"🐦 微博采集: {datetime.now().strftime('%H:%M')}")
    try:
        sess = await get_weibo_session()
        items = await weibo_collect(sess)
        for it in items:
            await db.insert_weibo(it)
    except Exception as e:
        logger.error(f"微博采集异常: {e}")


async def daily_report():
    logger.info(f"📋 日报: {datetime.now().strftime('%H:%M')}")
    try:
        report = await builder.build_daily()
        await feishu_daily(FEISHU_WEBHOOK_URL, report)
        await emailer.send_daily(report)
        ids = [n['id'] for n in report.get('news', []) if n.get('id')]
        if ids:
            db.enqueue('mark_pushed', {'ids': ids, 'push_date': datetime.now().strftime('%Y-%m-%d')})
    except Exception as e:
        logger.error(f"日报异常: {e}")


async def weekly_report():
    logger.info(f"📋 周报: {datetime.now().strftime('%H:%M')}")
    try:
        report = await builder.build_weekly()
        ai = await weekly_summary(AI_API_KEY, AI_API_URL, AI_MODEL, report['by_brand'], report['week_start'], report['week_end'], report['total_items'])
        report['ai_summary'] = ai
        await feishu_weekly(FEISHU_WEBHOOK_URL, report)
        await emailer.send_weekly(report)
    except Exception as e:
        logger.error(f"周报异常: {e}")


async def monthly_report():
    logger.info(f"📋 月报: {datetime.now().strftime('%H:%M')}")
    try:
        report = await builder.build_monthly()
        ai = await monthly_summary(AI_API_KEY, AI_API_URL, AI_MODEL, report)
        report['ai_summary'] = ai
        await feishu_monthly(FEISHU_WEBHOOK_URL, report)
        await emailer.send_monthly(report)
    except Exception as e:
        logger.error(f"月报异常: {e}")


async def clean_task():
    db.enqueue('clean', {})


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.start()
    logger.info("[V3.0] Database started")

    scheduler.add_job(news_collect, IntervalTrigger(hours=1), id='news', replace_existing=True)
    scheduler.add_job(weibo_collect_task, IntervalTrigger(minutes=120), id='weibo', replace_existing=True)
    scheduler.add_job(daily_report, CronTrigger(hour=9, minute=0), id='daily', replace_existing=True)
    scheduler.add_job(weekly_report, CronTrigger(day_of_week='mon', hour=8, minute=0), id='weekly', replace_existing=True)
    scheduler.add_job(monthly_report, CronTrigger(day=1, hour=8, minute=0), id='monthly', replace_existing=True)
    scheduler.add_job(clean_task, CronTrigger(hour=9, minute=5), id='clean', replace_existing=True)
    scheduler.start()
    logger.info("[V4.0] Scheduler: 新闻/60m, 微博/60m, 日报/09:00, 周报/周一08:00, 月报/每月1日08:00")

    asyncio.create_task(news_collect())
    asyncio.create_task(weibo_collect_task())

    yield

    scheduler.shutdown()
    await rss.close()
    await web.close()
    await auto.close()
    await db.stop()
    global _session
    if _session and not _session.closed:
        await _session.close()
    logger.info("[V3.0] Shutdown")


app = FastAPI(title='汽车行业舆情监控 V4.0', version='4.0.0', lifespan=lifespan)


@app.get('/')
async def root():
    return {'status': 'running', 'version': '4.0.0', 'message': '汽车行业舆情监控 V4.0', 'updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}


@app.get('/health')
async def api_health():
    summary = health.summary()
    db_stats = await health.db_stats()
    return {'status': 'running', 'sources': summary, 'database': db_stats}


@app.post('/collect')
async def api_collect():
    asyncio.create_task(news_collect())
    asyncio.create_task(weibo_collect_task())
    return {'status': 'triggered', 'tasks': ['news', 'weibo']}


@app.post('/report/daily')
async def api_daily():
    asyncio.create_task(daily_report())
    return {'status': 'triggered'}


@app.post('/report/weekly')
async def api_weekly():
    asyncio.create_task(weekly_report())
    return {'status': 'triggered'}


@app.post('/report/monthly')
async def api_monthly():
    asyncio.create_task(monthly_report())
    return {'status': 'triggered'}


if __name__ == '__main__':
    import json
    import uvicorn
    logger.info('[V3.0] Starting...')
    uvicorn.run('main:app', host='0.0.0.0', port=8001, reload=False)
