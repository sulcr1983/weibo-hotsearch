#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
汽车行业舆情监控系统 V2.0 - 统一入口
架构: V1.0(Sidecar) + V2.0(新闻监控) 并行运行
"""

import asyncio
import gc
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from v2.logger import get_logger
from v2.storage import DataVault
from v2.processor import process_article, cluster_article
from v2.fetcher import SmartFetcher
from v2.reporter import Reporter

logger = get_logger('main')

from config import (
    DATABASE_PATH, AI_API_KEY, AI_API_URL, AI_MODEL,
    FEISHU_WEBHOOK_URL, EMAIL_SENDER, EMAIL_PASSWORD,
    EMAIL_RECIPIENTS, SMTP_SERVER, SMTP_PORT,
)

V2_DB_PATH = os.path.join(os.path.dirname(__file__), 'news_articles.db')

vault = DataVault(V2_DB_PATH)
fetcher = SmartFetcher()
reporter = Reporter(vault, {
    'ai_api_key': AI_API_KEY,
    'ai_api_url': AI_API_URL,
    'ai_model': AI_MODEL,
    'feishu_webhook': FEISHU_WEBHOOK_URL,
    'email_sender': EMAIL_SENDER,
    'email_password': EMAIL_PASSWORD,
    'email_recipients': EMAIL_RECIPIENTS,
    'smtp_server': SMTP_SERVER,
    'smtp_port': SMTP_PORT,
})

scheduler = AsyncIOScheduler()

_processed_count = 0


async def news_collection_task():
    global _processed_count
    logger.info(f"[V2.0] 新闻采集任务启动: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        rss_articles = await fetcher.fetch_all_rss()
        if not rss_articles:
            logger.info("[V2.0] RSS 无品牌相关文章")
            return

        enriched_count = 0
        for i, raw_article in enumerate(rss_articles):
            try:
                article = process_article(raw_article)
                if not article:
                    continue

                exists = await vault.article_exists(article['url_hash'])
                if exists:
                    continue

                enriched = await fetcher.enrich_article(article)
                article['content'] = enriched.get('content', '')
                article['extraction_method'] = enriched.get('extraction_method', '')

                reprocessed = process_article(article)
                if reprocessed:
                    reprocessed['extraction_method'] = article.get('extraction_method', '')
                    article = reprocessed

                event_id = await cluster_article(article, vault)
                article['event_id'] = event_id

                if vault.insert_article(article):
                    enriched_count += 1

                _processed_count += 1
                if _processed_count % 50 == 0:
                    gc.collect()
                    logger.info(f"[V2.0] 已处理 {_processed_count} 条，触发 GC")

            except Exception as e:
                logger.error(f"[V2.0] 文章处理失败: {e}")
                continue

        logger.info(f"[V2.0] 新闻采集完成: RSS {len(rss_articles)} 条，入库 {enriched_count} 条")

    except Exception as e:
        logger.error(f"[V2.0] 新闻采集任务异常: {e}")


async def daily_report_task():
    logger.info(f"[V2.0] 每日日报任务启动: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        report = await reporter.generate_daily_report()

        weibo_count = len(report.get('weibo', []))
        news_count = len(report.get('news', []))
        logger.info(f"[V2.0] 日报数据: 微博 {weibo_count} 条, 新闻 {news_count} 条")

        await reporter.send_daily_feishu(report)
        await reporter.send_daily_email(report)
        await reporter.mark_all_pushed(report)
        vault.clean_old_data()

    except Exception as e:
        logger.error(f"[V2.0] 日报任务异常: {e}")


async def weekly_report_task():
    logger.info(f"[V2.0] 每周周报任务启动: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        report = await reporter.generate_weekly_report()

        total = report.get('total_events', 0)
        brands = len(report.get('by_brand', {}))
        logger.info(f"[V2.0] 周报数据: {total} 个事件, {brands} 个品牌")

        await reporter.send_weekly_feishu(report)
        await reporter.send_weekly_email(report)

    except Exception as e:
        logger.error(f"[V2.0] 周报任务异常: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await vault.start()
    logger.info("[V2.0] DataVault 启动")

    scheduler.add_job(
        news_collection_task,
        trigger=IntervalTrigger(hours=1),
        id='v2_news_collection',
        name='V2.0 新闻采集任务',
        replace_existing=True,
    )

    scheduler.add_job(
        daily_report_task,
        trigger=CronTrigger(hour=9, minute=0),
        id='v2_daily_report',
        name='V2.0 每日日报',
        replace_existing=True,
    )

    scheduler.add_job(
        weekly_report_task,
        trigger=CronTrigger(day_of_week='mon', hour=8, minute=0),
        id='v2_weekly_report',
        name='V2.0 每周周报',
        replace_existing=True,
    )

    scheduler.start()
    logger.info("[V2.0] 调度器启动")

    await news_collection_task()

    yield

    scheduler.shutdown()
    await fetcher.close()
    await vault.stop()
    logger.info("[V2.0] 系统关闭")


app = FastAPI(
    title='汽车行业舆情监控系统 V2.0',
    description='V1.0微博监控 + V2.0新闻监控 并行运行',
    version='2.0.0',
    lifespan=lifespan,
)


@app.get('/', summary='系统状态')
async def root():
    return {
        'status': 'running',
        'version': '2.0.0',
        'message': '汽车行业舆情监控系统 V2.0 运行中',
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }


@app.get('/v2/articles', summary='获取新闻文章')
async def get_articles(brand: str = None, hours: int = 24, limit: int = 50):
    articles = await vault.get_articles(brand=brand, hours=hours, limit=limit)
    return {'status': 'success', 'data': articles, 'count': len(articles)}


@app.get('/v2/events', summary='获取事件聚类')
async def get_events(brand: str = None, days: int = 7, limit: int = 50):
    events = await vault.get_events(brand=brand, days=days, limit=limit)
    return {'status': 'success', 'data': events, 'count': len(events)}


@app.post('/v2/collect', summary='手动触发采集')
async def manual_collect():
    asyncio.create_task(news_collection_task())
    return {'status': 'triggered', 'message': '新闻采集任务已触发'}


@app.post('/v2/report/daily', summary='手动触发日报')
async def manual_daily_report():
    asyncio.create_task(daily_report_task())
    return {'status': 'triggered', 'message': '日报推送任务已触发'}


@app.post('/v2/report/weekly', summary='手动触发周报')
async def manual_weekly_report():
    asyncio.create_task(weekly_report_task())
    return {'status': 'triggered', 'message': '周报推送任务已触发'}


if __name__ == '__main__':
    import uvicorn
    logger.info('[V2.0] 正在启动应用...')
    try:
        uvicorn.run(
            'main:app',
            host='127.0.0.1',
            port=8001,
            reload=True,
        )
    except Exception as e:
        logger.exception(f'[V2.0] 启动失败: {e}')
