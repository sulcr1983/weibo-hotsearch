"""飞书卡片推送"""
from typing import Optional

import aiohttp

from templates.feishu_cards import render_daily_feishu, render_weekly_feishu, render_monthly_feishu
from v2.logger import get_logger

logger = get_logger('feishu')


async def send_card(webhook: str, title: str, template: str, elements: list):
    if not webhook:
        return
    payload = {'msg_type': 'interactive', 'card': {'header': {'title': {'tag': 'plain_text', 'content': title}, 'template': template}, 'elements': elements}}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(webhook, json=payload, headers={'Content-Type': 'application/json'}, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    logger.info(f"飞书推送成功: {title}")
                else:
                    logger.error(f"飞书推送失败 {resp.status}: {await resp.text()}")
    except Exception as e:
        logger.error(f"飞书推送异常: {e}")


async def send_daily(webhook: str, report: dict):
    els = render_daily_feishu(
        report.get('weibo', []), report.get('news', []),
        report.get('date', ''), report.get('generated_at', ''))
    await send_card(webhook, '🚗 昨日汽车行业舆情热点新闻', 'wathet', els)


async def send_weekly(webhook: str, report: dict):
    ws = report.get('week_start', '')[5:]
    we = report.get('week_end', '')[5:]
    els = render_weekly_feishu(
        report.get('week_start', ''), report.get('week_end', ''),
        report.get('ai_summary', ''), report.get('by_brand', {}),
        report.get('total_items', 0), report.get('generated_at', ''))
    await send_card(webhook, f'📊 上周汽车行业10个品牌舆情汇总 {ws}-{we}', 'turquoise', els)


async def send_monthly(webhook: str, report: dict):
    els = render_monthly_feishu(report)
    await send_card(webhook, f'📅 微博月度舆情报告 {report.get("label","")}', 'blue', els)
