#!/usr/bin/env python3
"""本地全流程：采集 → 清洗 → 报告 → 邮件推送（一站式）"""
import asyncio
import json
import os
import sys
import random
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / 'system'))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / '.env')

from config import (
    DB_PATH, WEIBO_DB_PATH,
    AI_API_KEY, AI_API_URL, AI_MODEL,
    EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENTS,
    SMTP_SERVER, SMTP_PORT,
)
from storage.database import Database
from collector.rss_fetcher import RssFetcher
from collector.web_scraper import WebScraper
from collector.auto_media import AutoScraper
from collector.weibo_collector import collect as weibo_collect
from v2.logger import get_logger
from processor.brand_matcher import match_brand, strip_html, is_financial_brief, is_digest, is_ugc, is_opinion
from processor.scoring import calc_article_score, score_tier
from processor.keyworder import extract_keywords
from processor.deduplicator import compute_simhash, cluster_article
from processor.classifier import classify_dimension
from processor.llm_classifier import classify_with_llm
from processor.observability import new_trace_id, get_funnel, DropReason, log_trace
from reporter.builder import ReportBuilder
from reporter.emailer import Emailer
from reporter.health import SourceHealth

logger = get_logger('local_pipeline')
db = Database(DB_PATH, WEIBO_DB_PATH)
rss = RssFetcher()
web = WebScraper()
auto = AutoScraper()


async def safe_collect(collector, name: str) -> list:
    """安全执行采集，失败时返回空列表"""
    try:
        items = await collector
        logger.info(f"[{name}] 采集完成: {len(items)}条")
        return items
    except Exception as e:
        logger.warning(f"[{name}] 采集跳过: {e}")
        return []


async def process_articles(all_items: list) -> int:
    """处理采集数据：品牌匹配 → 过滤 → 评分 → 去重 → 入库"""
    funnel = get_funnel()
    funnel.reset()
    enriched = 0

    for raw in all_items:
        tid = new_trace_id()
        try:
            if not isinstance(raw, dict):
                funnel.count_drop(DropReason.INVALID_DATA)
                continue
            title = raw.get('title', '').strip()
            content_raw = raw.get('content', '') or raw.get('rss_summary', '')
            content = strip_html(content_raw)

            brand, _ = match_brand(title, content)
            if not brand:
                funnel.count_drop(DropReason.NO_BRAND_MATCH)
                continue
            funnel.brand_hit += 1

            if is_digest(title):
                funnel.count_drop(DropReason.DIGEST)
                continue
            if is_ugc(title):
                funnel.count_drop(DropReason.UGC)
                continue
            if is_opinion(title, raw.get('source', '')):
                funnel.count_drop(DropReason.OPINION)
                continue

            title_hit = match_brand(title, '')[0] is not None
            score_info = calc_article_score(
                title, content, raw.get('source', ''),
                brand_hit_title=title_hit,
                source_level=raw.get('source_level', 3))
            tier = score_tier(score_info['score'])
            if tier == 'discard':
                funnel.count_drop(DropReason.SCORE_DISCARD)
                continue

            dim = classify_dimension(title, content)
            if not dim:
                dim = await classify_with_llm(title, content, AI_API_KEY, AI_API_URL, AI_MODEL)
                if not dim:
                    dim = 'other'
            funnel.dimension_pass += 1

            if is_financial_brief(title, content):
                funnel.count_drop(DropReason.FINANCIAL_BRIEF)
                continue

            uh = db.compute_url_hash(raw['url'])
            if await db.article_exists(uh):
                funnel.count_drop(DropReason.DUPLICATE)
                continue

            kws = extract_keywords(title + ' ' + content)
            sh = compute_simhash(title[:200] + ' ' + content[:300])
            art_time = raw.get('published') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            article = {
                'url_hash': uh, 'title': title, 'url': raw['url'],
                'source': raw['source'], 'source_level': raw.get('source_level', 3),
                'brand': brand,
                'keywords': json.dumps(kws, ensure_ascii=False) if kws else '[]',
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
        except Exception as e:
            funnel.count_drop(DropReason.PARSE_FAILED)
            logger.error(f"[处理异常] {title}: {e}")

    logger.info(f"""
=== 采集漏斗报告 ===
  原始捕获: {funnel.raw_captured}
  品牌命中: {funnel.brand_hit}
  评分丢弃: {funnel.score_discarded}
  维度通过: {funnel.dimension_pass}
  金融过滤: {funnel.financial_filtered}
  去重过滤: {funnel.dedup_filtered}
  实际入库: {enriched}
===================""")
    return enriched


async def main():
    logger.info("=" * 50)
    logger.info("🚀 开始全流程：采集 → 清洗 → 报告 → 邮件推送")
    logger.info("=" * 50)

    # ── 第一步：初始化数据库 ──
    logger.info("[DB] 初始化数据库...")
    await db.start()
    logger.info("[DB] 数据库就绪")

    # ── 第二步：检查邮件配置 ──
    logger.info(f"[配置] EMAIL_SENDER={EMAIL_SENDER}")
    logger.info(f"[配置] EMAIL_RECIPIENTS={EMAIL_RECIPIENTS}")
    logger.info(f"[配置] SMTP={SMTP_SERVER}:{SMTP_PORT}")
    if not EMAIL_SENDER or not EMAIL_PASSWORD:
        logger.error("❌ 邮件未配置，无法发送")
        return
    emailer = Emailer(EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENTS, SMTP_SERVER, SMTP_PORT)

    # ── 第三步：采集 ──
    logger.info("\n📡 开始采集...")
    rss_task = safe_collect(rss.fetch_all(), 'RSS')
    web_task = safe_collect(web.scrape_all(), 'Web')
    auto_task = safe_collect(auto.scrape_all(), 'AutoMedia')
    results = await asyncio.gather(rss_task, web_task, auto_task, return_exceptions=True)
    rss_items, web_items, auto_items = [r if isinstance(r, list) else [] for r in results]
    logger.info(f"采集汇总: RSS={len(rss_items)} Web={len(web_items)} 垂媒={len(auto_items)}")

    # ── 第四步：微博采集（单独 session）──
    import aiohttp
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as sess:
            weibo_items = await safe_collect(weibo_collect(sess), 'Weibo')
    except Exception as e:
        weibo_items = []
        logger.warning(f"[Weibo] 采集跳过: {e}")
    logger.info(f"微博采集: {len(weibo_items)}条")

    all_raw = rss_items + web_items + auto_items + weibo_items
    logger.info(f"\n原始采集总计: {len(all_raw)}条")

    if not all_raw:
        logger.warning("⚠️ 未采集到任何数据，使用测试数据...")
        all_raw = [
            {'title': '比亚迪发布全新刀片电池2.0，续航突破1000公里',
             'url': 'https://example.com/byd-1', 'source': '汽车之家',
             'source_level': 1, 'published': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
             'content': '比亚迪今日正式发布刀片电池2.0技术，能量密度提升50%，续航突破1000公里大关。'},
            {'title': '小鹏汽车G9改款车型售价下调5万元',
             'url': 'https://example.com/xpeng-1', 'source': '易车网',
             'source_level': 2, 'published': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
             'content': '小鹏汽车宣布G9改款车型全系降价5万元，起售价25.99万元。'},
            {'title': '特斯拉上海超级工厂年产突破100万辆',
             'url': 'https://example.com/tesla-1', 'source': '新浪汽车',
             'source_level': 2, 'published': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
             'content': '特斯拉上海超级工厂2025年产量突破100万辆，占全球产能40%。'},
            {'title': '小米SU7单月交付突破2万台',
             'url': 'https://example.com/xiaomi-1', 'source': '36氪',
             'source_level': 1, 'published': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
             'content': '小米汽车宣布SU7单月交付量突破2万台，创中国新势力纪录。'},
            {'title': '蔚来汽车与宁德时代联合开发固态电池',
             'url': 'https://example.com/nio-1', 'source': '第一电动',
             'source_level': 2, 'published': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
             'content': '蔚来汽车与宁德时代宣布联合开发固态电池，计划2027年量产。'},
        ]

    # ── 第五步：清洗处理 ──
    logger.info("\n🔧 开始数据清洗...")
    funnel = get_funnel()
    funnel.raw_captured = len(all_raw)
    enriched = await process_articles(all_raw)
    logger.info(f"清洗完成: 入库 {enriched}条")

    # 等待数据库写入完成
    await asyncio.sleep(3)

    # ── 第六步：构建报告 ──
    logger.info("\n📊 构建日报...")
    builder = ReportBuilder(db)
    report = await builder.build_daily()
    logger.info(f"日报: {len(report.get('news', []))}条新闻, {len(report.get('weibo', []))}条微博")

    if not report.get('news') and not report.get('weibo'):
        logger.warning("报告为空，尝试使用48小时数据")
        news = await db.get_articles(hours=48)
        report['news'] = news[:15]
        report['weibo'] = report.get('weibo', [])
        logger.info(f"48小时扩展: {len(news)}条")

    # ── 第七步：发送邮件 ──
    logger.info("\n📧 发送邮件...")
    try:
        await emailer.send_daily(report)
        logger.info("✅ 邮件推送成功!")
    except Exception as e:
        logger.error(f"❌ 邮件推送失败: {e}")
        # 尝试直接发送
        try:
            from templates.email_daily import render_daily_email
            html = render_daily_email(
                report.get('weibo', []),
                report.get('news', []),
                report.get('date', datetime.now().strftime('%Y-%m-%d')),
                report.get('generated_at', datetime.now().strftime('%Y-%m-%d %H:%M')))
            emailer._send(f"汽车舆情日报 {datetime.now().strftime('%Y-%m-%d')}", html)
            logger.info("✅ 邮件（直发）成功!")
        except Exception as e2:
            logger.error(f"❌ 邮件（直发）也失败: {e2}")

    # ── 第八步：清理 ──
    await db.stop()
    logger.info("\n🏁 全流程完成!")
    logger.info(f"采集: RSS={len(rss_items)} Web={len(web_items)} 垂媒={len(auto_items)} 微博={len(weibo_items)}")
    logger.info(f"入库: {enriched}条")
    logger.info(f"报告: {len(report.get('news', []))}条新闻")
    logger.info(f"推送: sulcr@qq.com")


if __name__ == '__main__':
    asyncio.run(main())