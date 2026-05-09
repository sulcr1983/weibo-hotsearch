#!/usr/bin/env python3
"""汽车行业舆情监控 V4.3 — 统一入口 + 超级反爬"""
import asyncio
import gc
import json
import random
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

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
from collector.playwright_scraper import PlaywrightScraper
from collector.stealth_scraper import SuperStealthScraper
from collector.ai_scraper import AIScraper
from processor.brand_matcher import match_brand, strip_html, is_financial_brief, is_digest, is_ugc, is_opinion
from processor.scoring import calc_article_score, score_tier
from processor.keyworder import extract_keywords
from processor.deduplicator import compute_simhash, cluster_article
from processor.classifier import classify_dimension
from processor.llm_classifier import classify_with_llm
from processor.observability import (
    new_trace_id, get_funnel, DropReason,
    log_trace,
)
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
pw = PlaywrightScraper()
stealth = SuperStealthScraper()  # 新增超级反爬采集器
ai_scraper = AIScraper({'api_key': AI_API_KEY, 'api_url': AI_API_URL, 'model': AI_MODEL})
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
    funnel = get_funnel()
    funnel.reset()
    try:
        rss_items = await rss.fetch_all()
        web_items = await web.scrape_all()
        auto_items = await auto.scrape_all()
        pw_items = await pw.scrape_all()
        stealth_items = await stealth.scrape_all()  # 新增超级反爬采集
        # 源级别统计 — 从各采集器获取实际源数量
        from v2.constants import RSS_FEEDS, WEB_FEEDS
        from sources import get_auto_feeds, get_playwright_feeds
        _auto_feeds = get_auto_feeds()
        _playwright_feeds = get_playwright_feeds()
        funnel.rss_sources = len(RSS_FEEDS)
        funnel.web_sources = len(WEB_FEEDS)
        funnel.auto_sources = len(_auto_feeds)
        funnel.pw_sources = len(_playwright_feeds)
        funnel.rss_success = funnel.rss_sources if rss_items else 0
        funnel.web_success = funnel.web_sources if web_items else 0
        funnel.auto_success = funnel.auto_sources if auto_items else 0
        funnel.pw_success = funnel.pw_sources if pw_items else 0

        health.record_rss('RSS聚合', len(rss_items))
        health.record_web('Web抓取', len(web_items))
        health.record_auto('汽车垂媒', len(auto_items))
        health.record_pw('Playwright', len(pw_items))
        health.record_stealth('超级反爬', len(stealth_items))
        ai_items = await ai_scraper.scrape_all()
        logger.info(f"AI爬虫采集: {len(ai_items)} 条")
        logger.info(f"采集: RSS {len(rss_items)} + Web {len(web_items)} + 垂媒 {len(auto_items)} + PW {len(pw_items)} + SuperStealth {len(stealth_items)} + AI {len(ai_items)}")
        all_items = rss_items + web_items + auto_items + pw_items + stealth_items + ai_items
        funnel.raw_captured = len(all_items)
        enriched = 0
        for raw in all_items:
            tid = new_trace_id()
            try:
                if not isinstance(raw, dict):
                    funnel.count_drop(DropReason.INVALID_DATA)
                    log_trace(tid, '[RAW_FAIL]', '非dict数据')
                    continue
                title = raw.get('title', '').strip()
                content_raw = raw.get('content', '') or raw.get('rss_summary', '')
                content = strip_html(content_raw)
                log_trace(tid, '[RAW]', title)

                brand, _ = match_brand(title, content)
                if not brand:
                    funnel.count_drop(DropReason.NO_BRAND_MATCH)
                    log_trace(tid, '[BRAND_FAIL]', title, 'no_brand_match')
                    continue
                funnel.brand_hit += 1
                log_trace(tid, '[BRAND]', title, brand)

                if is_digest(title):
                    funnel.count_drop(DropReason.DIGEST)
                    funnel.digest_filtered += 1
                    log_trace(tid, '[FILTER:DIGEST]', title)
                    continue
                if is_ugc(title):
                    funnel.count_drop(DropReason.UGC)
                    funnel.ugc_filtered += 1
                    log_trace(tid, '[FILTER:UGC]', title)
                    continue
                if is_opinion(title, raw.get('source', '')):
                    funnel.count_drop(DropReason.OPINION)
                    funnel.opinion_filtered += 1
                    log_trace(tid, '[FILTER:OPINION]', title)
                    continue

                # 评分
                title_hit = match_brand(title, '')[0] is not None
                score_info = calc_article_score(
                    title, content, raw.get('source', ''),
                    brand_hit_title=title_hit,
                    source_level=raw.get('source_level', 3))
                tier = score_tier(score_info['score'])
                if tier == 'discard':
                    funnel.count_drop(DropReason.SCORE_DISCARD)
                    funnel.score_discarded += 1
                    log_trace(tid, '[FILTER:SCORE]', title, f'score={score_info["score"]}')
                    continue

                # 维度分类
                dim = classify_dimension(title, content)
                if not dim:
                    logger.info(f"[DIM:LLM] {title[:50]} | 关键词未命中 → LLM分类")
                    dim = await classify_with_llm(title, content, AI_API_KEY, AI_API_URL, AI_MODEL)
                    if not dim:
                        funnel.count_drop(DropReason.NO_DIMENSION)
                        logger.info(f"[DIM:DROP] {title[:60]} | 品牌={brand} | 四维度未命中(关键词+LLM均失败)")
                        log_trace(tid, '[FILTER:NO_DIM]', title)
                        continue
                funnel.dimension_pass += 1
                if dim:
                    logger.info(f"[DIM:PASS] {dim} | {title[:50]}")

                if is_financial_brief(title, content):
                    funnel.count_drop(DropReason.FINANCIAL_BRIEF)
                    funnel.financial_filtered += 1
                    log_trace(tid, '[FILTER:FINANCIAL]', title)
                    continue

                uh = db.compute_url_hash(raw['url'])
                if await db.article_exists(uh):
                    funnel.count_drop(DropReason.DUPLICATE)
                    funnel.dedup_filtered += 1
                    log_trace(tid, '[FILTER:DEDUP]', title, 'url_exists')
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
                    'score': score_info['score'], 'score_tier': tier,
                    'created_at': art_time,
                }
                eid = await cluster_article(article, db)
                article['event_id'] = eid
                db.enqueue('insert_article', article)
                funnel.db_inserted += 1
                enriched += 1
                log_trace(tid, '[DB]', title, f'score={score_info["score"]} tier={tier}')
            except Exception as e:
                funnel.count_drop(DropReason.PARSE_FAILED)
                funnel.errors += 1
                log_trace(tid, '[ERROR]', str(e)[:100])
                logger.error(f"处理失败: {e}")
        logger.info(f"📥 入库 {enriched} 条")
        funnel.log_report()
    except Exception as e:
        logger.error(f"采集异常: {e}")
        funnel.errors += 1


async def weibo_collect_task():
    logger.info(f"🐦 微博采集: {datetime.now().strftime('%H:%M')}")
    try:
        sess = await get_weibo_session()
        items = await weibo_collect(sess)
        new_count = 0
        for it in items:
            result = await db.upsert_weibo_event(
                keyword=it['keyword'], brand=it['brand'],
                link=it.get('link', ''), label=it.get('label', ''),
                heat=it.get('heat', 0))
            if result['is_new']:
                new_count += 1
        await db.end_stale_events(hours=24)
        if len(items) == 0:
            logger.info(f"微博热搜: 本轮无汽车品牌上榜（51条热搜中0条命中，正常现象）")
        else:
            logger.info(f"微博热搜: {new_count} 新事件 / {len(items)} 命中")
            if new_count > 0:
                logger.info(f"🔥 微博新热搜: {new_count} 条首次出现（已推送）")
    except Exception as e:
        logger.error(f"微博采集异常: {e}")
    finally:
        next_min = random.randint(57, 67)
        try:
            try:
                scheduler.reschedule_job('weibo', trigger=IntervalTrigger(minutes=next_min))
            except Exception:
                scheduler.add_job(weibo_collect_task, IntervalTrigger(minutes=next_min), id='weibo',
                                  max_instances=1, coalesce=True, replace_existing=True)
        except Exception:
            logger.error(f"微博调度异常: 将在 {next_min} 分钟后由守护进程重试")
        logger.info(f"微博下次采集: {next_min} 分钟后")


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


def _startup_check() -> bool:
    """启动自检：验证运行时关键依赖可用 + 关键环境变量"""
    failed = []
    # 1. 依赖检查
    for name, import_path in [
        ('aiohttp', 'aiohttp'),
        ('aiosqlite', 'aiosqlite'),
        ('feedparser', 'feedparser'),
        ('bs4 (BeautifulSoup)', 'bs4'),
        ('simhash', 'simhash'),
        ('jieba', 'jieba'),
        ('apscheduler', 'apscheduler'),
        ('fastapi', 'fastapi'),
        ('uvicorn', 'uvicorn'),
        ('yaml', 'yaml'),
        ('dotenv', 'dotenv'),
    ]:
        try:
            __import__(import_path)
        except ImportError:
            logger.error(f"  缺少依赖: {name} (pip install {import_path})")
            failed.append(name)

    # 2. 关键环境变量检查
    env_warnings = []
    if not AI_API_KEY:
        env_warnings.append('AI_API_KEY (AI总结将不可用)')
    if not FEISHU_WEBHOOK_URL:
        env_warnings.append('FEISHU_WEBHOOK_URL (飞书推送将不可用)')
    if not EMAIL_SENDER:
        env_warnings.append('EMAIL_SENDER (邮件推送将不可用)')
    if env_warnings:
        logger.warning(f"缺少可选环境变量: {', '.join(env_warnings)}")

    # 3. 数据库路径检查
    from config import PROJECT_ROOT
    db_dir = Path(DB_PATH).parent
    if not db_dir.exists():
        try:
            db_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"无法创建数据库目录 {db_dir}: {e}")

    if failed:
        logger.error(f"启动自检: {len(failed)} 项失败 - {', '.join(failed)}")
        return False
    # 预初始化 jieba 分词器
    try:
        import jieba
        jieba.initialize()
    except Exception:
        pass
    logger.info(f"启动自检: 所有依赖可用 (0 失败) | 环境警告: {len(env_warnings)}")
    return len(failed) == 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.start()
    # 启动自检：验证关键依赖可用
    ok = _startup_check()
    if not ok:
        logger.error("启动自检失败，请检查 system/requirements.txt 安装状态")
    else:
        logger.info("[V4.3] Database started")

    scheduler.add_job(news_collect, IntervalTrigger(hours=1), id='news',
                      replace_existing=True, max_instances=1, coalesce=True)
    first_weibo_min = random.randint(57, 67)
    scheduler.add_job(weibo_collect_task, IntervalTrigger(minutes=first_weibo_min), id='weibo',
                      replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(daily_report, CronTrigger(hour=9, minute=0), id='daily',
                      replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(weekly_report, CronTrigger(day_of_week='mon', hour=8, minute=0), id='weekly',
                      replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(monthly_report, CronTrigger(day=1, hour=8, minute=0), id='monthly',
                      replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(clean_task, CronTrigger(hour=9, minute=5), id='clean',
                      replace_existing=True, max_instances=1, coalesce=True)
    scheduler.start()
    logger.info("[V4.3] Scheduler: 新闻/60m, 微博/57~67m(随机), 日报/09:00, 周报/周一08:00, 月报/每月1日08:00")

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
    logger.info("[V4.3] Shutdown")


app = FastAPI(title='汽车行业舆情监控 V4.3', version='4.3.0', lifespan=lifespan)


@app.get('/')
async def root():
    return {'status': 'running', 'version': '4.3.0', 'message': '汽车行业舆情监控 V4.3 (超级反爬)', 'updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}


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
    logger.info('[V4.3] Starting...')
    uvicorn.run('main:app', host='0.0.0.0', port=8001, reload=False)




