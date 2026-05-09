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
        logger.info(f"采集: RSS {len(rss_items)} + Web {len(web_items)} + 垂媒 {len(auto_items)} + PW {len(pw_items)}")
        all_items = rss_items + web_items + auto_items + pw_items
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
                        # V5.3: LLM也失败时不丢弃，使用 other 维度
                        dim = 'other'
                        logger.info(f"[DIM:FALLBACK] {title[:60]} | 品牌={brand} | 关键词+LLM均未命中 → other维度")
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
        logger.info(f"""📥 入库 {enriched} 条
=== 采集漏斗报告 ===
  原始捕获: {funnel.raw_captured}
  品牌命中: {funnel.brand_hit}
  评分丢弃: {funnel.score_discarded}
  维度通过: {funnel.dimension_pass}
  金融过滤: {funnel.financial_filtered}
  去重过滤: {funnel.dedup_filtered}
  实际入库: {enriched}
===================""")
        funnel.log_report()
    except Exception as e:
        logger.error(f"采集异常: {e}")
        funnel.errors += 1


async def weibo_collect_job():
    """独立的微博热搜采集任务（调度器自动管理间隔）"""
    logger.info(f"🔥 微博热搜采集: {datetime.now().strftime('%H:%M')}")
    try:
        sess = await get_weibo_session()
        items = await weibo_collect(sess)
        logger.info(f"微博热搜采集: {len(items)} 条品牌命中")

        if not items:
            logger.warning("本轮微博热搜：0条品牌命中")
            return

        saved = 0
        for it in items:
            try:
                result = await db.upsert_weibo_event(
                    keyword=it['keyword'], brand=it['brand'],
                    link=it.get('link', ''), label=it.get('label', ''),
                    heat=it.get('heat', 0))
                if result and result.get('is_new'):
                    saved += 1
            except Exception as e:
                logger.error(f"微博入库失败: {e}")

        await db.end_stale_events(hours=24)
        logger.info(f"微博热搜: {saved} 新事件 / {len(items)} 命中")
    except Exception as e:
        logger.error(f"微博采集任务异常: {e}")


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
    """启动自检：验证所有关键依赖 + 环境变量 + 目录权限，逐项打印 ✅/❌"""
    results = []
    all_ok = True

    def ok(msg: str):
        results.append(f"    ✅  {msg}")
        return True

    def fail(msg: str):
        nonlocal all_ok
        all_ok = False
        results.append(f"    ❌  {msg}")
        return False

    # ── 1. pip 依赖检查 ──
    deps = [
        ('aiohttp', 'aiohttp'),
        ('aiosqlite', 'aiosqlite'),
        ('feedparser', 'feedparser'),
        ('bs4', 'beautifulsoup4'),
        ('simhash', 'simhash'),
        ('jieba', 'jieba'),
        ('apscheduler', 'apscheduler'),
        ('fastapi', 'fastapi'),
        ('uvicorn', 'uvicorn'),
        ('yaml', 'pyyaml'),
        ('dotenv', 'python-dotenv'),
    ]
    for name, pkg in deps:
        try:
            __import__(name)
            ok(f'依赖 [{name}] 已安装')
        except ImportError:
            fail(f'依赖 [{name}] 未安装 (pip install {pkg})')

    # ── 2. data/ 目录检查 ──
    from config import DATA_DIR, LOG_DIR
    for label, d in [('data/', DATA_DIR), ('logs/', LOG_DIR)]:
        if d.exists():
            try:
                test_file = d / '._startup_test'
                test_file.touch()
                test_file.unlink()
                ok(f'目录 [{label}] 存在且可写 ({d})')
            except Exception as e:
                fail(f'目录 [{label}] 不可写 ({d}): {e}')
        else:
            try:
                d.mkdir(parents=True, exist_ok=True)
                ok(f'目录 [{label}] 已创建 ({d})')
            except Exception as e:
                fail(f'目录 [{label}] 创建失败 ({d}): {e}')

    # ── 3. 关键环境变量检查 ──
    env_vars = [
        ('FEISHU_WEBHOOK_URL', FEISHU_WEBHOOK_URL, '飞书推送 (缺少则日报/周报/月报无法推送)'),
        ('AI_API_KEY', AI_API_KEY, 'AI 总结 (缺少则 LLM 分类 & 周报总结不可用)'),
        ('EMAIL_SENDER', EMAIL_SENDER, '邮件推送 (缺少则邮件报告不可用)'),
        ('EMAIL_PASSWORD', EMAIL_PASSWORD, '邮件密码'),
        ('EMAIL_RECIPIENTS', EMAIL_RECIPIENTS, '邮件收件人'),
    ]
    for var_name, var_val, hint in env_vars:
        if var_name == 'EMAIL_RECIPIENTS':
            present = bool(var_val)
        else:
            present = bool(var_val and var_val.strip())
        if present:
            masked = var_val[:4] + '***' if isinstance(var_val, str) and len(var_val) > 4 else '***'
            ok(f'环境变量 [{var_name}] = {masked}')
        else:
            fail(f'环境变量 [{var_name}] 未设置 — {hint}')

    # ── 4. 数据库文件检查 ──
    for label, db_path in [('MySQL DB (articles)', DB_PATH), ('Weibo DB', WEIBO_DB_PATH)]:
        db_file = Path(db_path)
        if db_file.exists():
            try:
                with open(db_path, 'a') as f:
                    pass
                ok(f'数据库 [{db_path}] 存在且可写')
            except Exception as e:
                fail(f'数据库 [{db_path}] 不可写: {e}')
        else:
            ok(f'数据库 [{db_path}] 将自动创建')

    # ── 5. 打印汇总 ──
    passed = sum(1 for r in results if '✅' in r)
    failed = sum(1 for r in results if '❌' in r)
    logger.info("启动自检: 开始")
    for line in results:
        logger.info(line)
    logger.info(f"启动自检: 完成 — ✅ {passed} 项通过 / ❌ {failed} 项失败")
    return all_ok


def _setup_scheduler():
    """配置并启动调度器，所有任务注册失败时优雅降级"""
    try:
        scheduler.add_job(
            news_collect,
            IntervalTrigger(seconds=3600),
            id='news_collect',
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300,
        )
    except Exception as e:
        logger.error(f"news_collect 任务注册失败: {e}")

    try:
        scheduler.add_job(
            weibo_collect_job,
            IntervalTrigger(seconds=random.randint(3420, 4020)),
            id='weibo_collect',
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=600,
        )
    except Exception as e:
        logger.error(f"weibo_collect 任务注册失败: {e}")

    try:
        scheduler.add_job(
            daily_report, CronTrigger(hour=9, minute=0),
            id='daily_report', replace_existing=True, max_instances=1,
            coalesce=True, misfire_grace_time=600,
        )
    except Exception as e:
        logger.error(f"daily_report 任务注册失败: {e}")

    try:
        scheduler.add_job(
            weekly_report, CronTrigger(day_of_week='mon', hour=8, minute=0),
            id='weekly_report', replace_existing=True, max_instances=1,
            coalesce=True, misfire_grace_time=3600,
        )
    except Exception as e:
        logger.error(f"weekly_report 任务注册失败: {e}")

    try:
        scheduler.add_job(
            monthly_report, CronTrigger(day=1, hour=8, minute=0),
            id='monthly_report', replace_existing=True, max_instances=1,
            coalesce=True, misfire_grace_time=7200,
        )
    except Exception as e:
        logger.error(f"monthly_report 任务注册失败: {e}")

    try:
        scheduler.add_job(
            clean_task, CronTrigger(hour=9, minute=5),
            id='clean_task', replace_existing=True, max_instances=1,
            coalesce=True, misfire_grace_time=600,
        )
    except Exception as e:
        logger.error(f"clean_task 任务注册失败: {e}")

    scheduler.start()
    logger.info("✅ 调度器启动完成")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.start()
    ok = _startup_check()
    if not ok:
        logger.error("启动自检失败，请检查 system/requirements.txt 安装状态")
    else:
        logger.info("[V4.3] Database started")

    _setup_scheduler()
    logger.info("[V4.3] Scheduler: 新闻/60m, 微博/57~67m(随机), 日报/09:00, 周报/周一08:00, 月报/每月1日08:00")

    asyncio.create_task(news_collect())
    asyncio.create_task(weibo_collect_job())

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


@app.get('/status')
async def status():
    """详细系统状态（运维用）"""
    import os
    try:
        import psutil
        proc = psutil.Process(os.getpid())
    except Exception:
        proc = None

    jobs = []
    for job in scheduler.get_jobs():
        next_run = str(job.next_run_time) if job.next_run_time else 'N/A'
        jobs.append({'id': job.id, 'next_run': next_run})

    try:
        article_count = await db.count_articles()
        weibo_count = await db.count_weibo_events()
    except Exception:
        article_count = weibo_count = -1

    return {
        'version': 'V4.3',
        'time': datetime.now().isoformat(),
        'scheduler_jobs': jobs,
        'db': {'articles': article_count, 'weibo_events': weibo_count},
        'config': {
            'feishu': bool(FEISHU_WEBHOOK_URL),
            'email': bool(EMAIL_SENDER),
            'ai': bool(AI_API_KEY),
        }
    }


@app.post('/collect')
async def api_collect():
    asyncio.create_task(news_collect())
    asyncio.create_task(weibo_collect_job())
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


@app.post('/test/email')
async def test_email():
    """邮件连通性测试"""
    try:
        emailer._send("测试邮件", "<h1>连通性测试</h1><p>邮件发送正常</p>")
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


if __name__ == '__main__':
    import json
    import uvicorn
    logger.info('[V4.3] Starting...')
    uvicorn.run('main:app', host='0.0.0.0', port=8001, reload=False)




