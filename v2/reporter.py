import asyncio
import json
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from typing import List, Optional

import aiohttp

from v2.logger import get_logger
from v2.storage import DataVault

logger = get_logger('reporter')

# ─── Design System: Brand Color Mapping ───────────────────────────────────────
BRAND_COLORS = {
    "小米汽车": "#FF6900",
    "鸿蒙智行": "#CE0E2D",
    "零跑汽车": "#0052D9",
    "理想汽车": "#4A90D9",
    "蔚来汽车": "#2E6BE6",
    "极氪汽车": "#00B2A9",
    "阿维塔":   "#6C5CE7",
    "智己汽车": "#E84393",
    "比亚迪":   "#C0392B",
    "特斯拉":   "#E74C3C",
}

DEFAULT_BRAND_COLOR = "#16213e"

# ─── Design System: Color Palette ─────────────────────────────────────────────
PALETTE = {
    "navy_dark":    "#1a1a2e",   # Header background
    "navy_mid":     "#16213e",   # Accent / section headers
    "navy_light":   "#0f3460",   # Secondary accent
    "amber":        "#e94560",   # Highlight / alert
    "amber_soft":   "#f5a623",   # Warm accent
    "white":        "#ffffff",
    "gray_50":      "#f8f9fc",   # Card background
    "gray_100":     "#eef0f5",   # Divider
    "gray_200":     "#d5d9e2",   # Border
    "gray_400":     "#8b92a5",   # Muted text
    "gray_500":     "#6b7280",   # Secondary text
    "gray_600":     "#4b5563",   # Body text
    "gray_800":     "#1f2937",   # Primary text
    "blue_link":    "#2563eb",   # Link color
}


def _brand_color(brand: str) -> str:
    """Get the hex color for a brand, falling back to default."""
    return BRAND_COLORS.get(brand, DEFAULT_BRAND_COLOR)


def _brand_badge_html(brand: str) -> str:
    """Render a colored pill/badge for a brand name in HTML email."""
    color = _brand_color(brand)
    return (
        f'<span style="display:inline-block;background:{color}14;'
        f'color:{color};font-size:11px;font-weight:600;'
        f'padding:1px 7px;border-radius:3px;'
        f'border:1px solid {color}30;'
        f'vertical-align:middle;letter-spacing:0.3px;'
        f'font-family:\'Microsoft YaHei\',Arial,sans-serif;">'
        f'{brand}</span>'
    )


def _brand_badge_feishu(brand: str) -> str:
    """Render a colored brand tag in Feishu lark_md format."""
    color = _brand_color(brand)
    return f'<font color="{color}">[{brand}]</font>'


class Reporter:
    def __init__(self, vault: DataVault, config: dict):
        self.vault = vault
        self.config = config
        self.ai_api_key = config.get('ai_api_key', '')
        self.ai_api_url = config.get('ai_api_url', '')
        self.ai_model = config.get('ai_model', 'glm-4-flash')
        self.feishu_webhook = config.get('feishu_webhook', '')
        self.email_sender = config.get('email_sender', '')
        self.email_password = config.get('email_password', '')
        self.email_recipients = config.get('email_recipients', [])
        self.smtp_server = config.get('smtp_server', 'smtp.qq.com')
        self.smtp_port = config.get('smtp_port', 587)

    async def generate_daily_report(self) -> dict:
        yesterday_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        weibo_articles = await self._get_weibo_data()
        news_articles = await self.vault.get_articles(hours=24, is_pushed=0)

        return {
            'date': yesterday_date,
            'weibo': weibo_articles,
            'news': news_articles,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
        }

    async def generate_weekly_report(self) -> dict:
        week_start = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        week_end = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        events = await self.vault.get_events(days=7)
        by_brand = {}
        for event in events:
            brand = event.get('brand', '其他')
            if brand not in by_brand:
                by_brand[brand] = []
            by_brand[brand].append(event)

        for brand in by_brand:
            by_brand[brand] = by_brand[brand][:10]

        total = sum(len(v) for v in by_brand.values())
        if total > 60:
            for brand in by_brand:
                by_brand[brand] = by_brand[brand][:6]

        ai_analysis = ''
        if self.ai_api_key and events:
            try:
                ai_analysis = await self._generate_ai_analysis(events, week_start, week_end)
            except Exception as e:
                logger.error(f"AI 周报分析失败: {e}")
                ai_analysis = f"本周共监测到 {len(events)} 个汽车行业事件，AI 分析暂不可用。"

        return {
            'week_start': week_start,
            'week_end': week_end,
            'ai_analysis': ai_analysis,
            'by_brand': by_brand,
            'total_events': len(events),
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
        }

    async def _get_weibo_data(self) -> List[dict]:
        try:
            import aiosqlite
            from config import DATABASE_PATH
            past_24h = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
            async with aiosqlite.connect(DATABASE_PATH) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    'SELECT * FROM weibo_hot_search WHERE created_at >= ? AND is_pushed = 0 ORDER BY created_at DESC',
                    (past_24h,)
                ) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"获取微博数据失败: {e}")
            return []

    async def _generate_ai_analysis(self, events: list, week_start: str, week_end: str) -> str:
        event_summaries = []
        for event in events[:20]:
            brand = event.get('brand', '')
            title = event.get('title', '')
            count = event.get('article_count', 1)
            event_summaries.append(f"[{brand}] {title} ({count}篇报道)")

        prompt = f"""请根据以下本周（{week_start} 至 {week_end}）汽车行业舆情事件，撰写一段 150-200 字的行业分析摘要。
要求：客观、专业、不编造事实，重点分析趋势和关键事件。

事件列表：
{chr(10).join(event_summaries)}"""

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.ai_api_key}',
        }
        data = {
            'model': self.ai_model,
            'messages': [
                {'role': 'system', 'content': '你是一个专业的汽车行业分析师，擅长从舆情数据中提炼行业趋势。'},
                {'role': 'user', 'content': prompt},
            ],
            'temperature': 0.3,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(self.ai_api_url, headers=headers, json=data, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    choices = result.get('choices', [])
                    if choices:
                        return choices[0].get('message', {}).get('content', '').strip()
                return ''

    # ─── Daily Feishu Card ────────────────────────────────────────────────────
    async def send_daily_feishu(self, report: dict):
        if not self.feishu_webhook:
            return

        elements = []
        weibo = report.get('weibo', [])
        news = report.get('news', [])
        date_str = report.get('date', '')

        # Date subtitle
        elements.append({
            'tag': 'div',
            'text': {
                'tag': 'lark_md',
                'content': f'<font color="{PALETTE["gray_400"]}">昨日汽车舆情热搜汇总</font>  <font color="{PALETTE["gray_800"]}">**{date_str}**</font>'
            }
        })
        elements.append({'tag': 'hr'})

        if weibo:
            elements.append({
                'tag': 'div',
                'text': {
                    'tag': 'lark_md',
                    'content': '**🔥 微博热搜**'
                }
            })
            for item in weibo[:15]:
                time_part = item.get('created_at', '')[11:16] if item.get('created_at') else ''
                brand = item.get('brand_group', '')
                title = item.get('title', '')
                link = item.get('link', '')
                heat = item.get('heat', '') or item.get('hot_num', '')
                brand_tag = _brand_badge_feishu(brand) if brand else ''
                heat_str = f'  <font color="{PALETTE["amber"]}">🔥{heat}</font>' if heat else ''
                content_str = f'<font color="{PALETTE["gray_400"]}">{time_part}</font>  {brand_tag}  [{title}]({link}){heat_str}'
                elements.append({
                    'tag': 'div',
                    'text': {
                        'tag': 'lark_md',
                        'content': content_str
                    }
                })
            elements.append({'tag': 'hr'})

        if news:
            elements.append({
                'tag': 'div',
                'text': {
                    'tag': 'lark_md',
                    'content': '**📰 新闻热点**'
                }
            })
            for item in news[:15]:
                time_part = item.get('created_at', '')[11:16] if item.get('created_at') else ''
                brand = item.get('brand', '')
                title = item.get('title', '')
                link = item.get('url', '')
                source = item.get('source', '')
                summary = item.get('summary', '') or item.get('content', '')
                if summary and len(summary) > 120:
                    summary = summary[:120] + '...'

                brand_tag = _brand_badge_feishu(brand) if brand else ''
                content_str = f'<font color="{PALETTE["gray_400"]}">{time_part}</font>  {brand_tag}  [{title}]({link})'
                if source:
                    content_str += f'  <font color="{PALETTE["gray_500"]}">· {source}</font>'
                if summary:
                    content_str += f'\n<font color="{PALETTE["gray_400"]}">  {summary}</font>'

                elements.append({
                    'tag': 'div',
                    'text': {
                        'tag': 'lark_md',
                        'content': content_str
                    }
                })
        elif not weibo:
            elements.append({
                'tag': 'div',
                'text': {
                    'tag': 'lark_md',
                    'content': f'<font color="{PALETTE["gray_400"]}">📭 昨日暂无关注的品牌舆情</font>'
                }
            })

        elements.append({'tag': 'hr'})
        elements.append({
            'tag': 'div',
            'text': {
                'tag': 'lark_md',
                'content': f'<font color="{PALETTE["gray_400"]}">生成时间：{report.get("generated_at", "")}</font>'
            }
        })

        payload = {
            'msg_type': 'interactive',
            'card': {
                'header': {
                    'title': {'tag': 'plain_text', 'content': '🚗 昨日汽车舆情热搜汇总'},
                    'template': 'wathet',
                },
                'elements': elements,
            }
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.feishu_webhook,
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        logger.info("飞书日报推送成功")
                    else:
                        error_text = await resp.text()
                        logger.error(f"飞书日报推送失败: {resp.status} {error_text}")
        except Exception as e:
            logger.error(f"飞书推送异常: {e}")

    # ─── Daily Email ──────────────────────────────────────────────────────────
    async def send_daily_email(self, report: dict):
        if not self.email_sender or not self.email_password:
            return

        weibo = report.get('weibo', [])
        news = report.get('news', [])
        date_str = report.get('date', '')
        generated_at = report.get('generated_at', '')

        P = PALETTE

        # ── Header Banner ──
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:{P["gray_50"]};font-family:'Microsoft YaHei','PingFang SC','Helvetica Neue',Arial,sans-serif;-webkit-font-smoothing:antialiased;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{P["gray_50"]};"><tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

<!-- Header Banner -->
<tr><td style="background:linear-gradient(135deg,{P["navy_dark"]} 0%,{P["navy_mid"]} 100%);background-color:{P["navy_dark"]};padding:28px 32px 24px 32px;border-radius:0;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
<td style="vertical-align:middle;">
<h1 style="margin:0;font-size:22px;font-weight:700;color:{P["white"]};letter-spacing:1px;">🚗 昨日汽车舆情热搜汇总</h1>
</td>
<td align="right" style="vertical-align:middle;">
<span style="font-size:13px;color:{P["gray_400"]};font-weight:400;">{date_str}</span>
</td>
</tr></table>
</td></tr>

<!-- Accent Line -->
<tr><td style="background:{P["amber"]};height:3px;font-size:0;line-height:0;">&nbsp;</td></tr>

<!-- Content Body -->
<tr><td style="background:{P["white"]};padding:24px 28px 8px 28px;">"""

        # ── Section 1: Weibo Hot Search ──
        if weibo:
            html += f"""
<!-- Section: Weibo -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr><td style="padding-bottom:12px;">
<table role="presentation" cellpadding="0" cellspacing="0"><tr>
<td style="background:{P["amber"]};width:4px;height:20px;border-radius:2px;"></td>
<td style="padding-left:10px;"><span style="font-size:16px;font-weight:700;color:{P["navy_dark"]};">🔥 微博热搜</span></td>
</tr></table>
</td></tr>"""

            for item in weibo[:15]:
                time_part = item.get('created_at', '')[11:16] if item.get('created_at') else ''
                brand = item.get('brand_group', '')
                title = item.get('title', '')
                link = item.get('link', '')
                heat = item.get('heat', '') or item.get('hot_num', '')
                badge = _brand_badge_html(brand) if brand else ''
                heat_html = f'<span style="font-size:11px;color:{P["amber"]};margin-left:6px;">🔥{heat}</span>' if heat else ''

                html += f"""
<tr><td style="padding:10px 0;border-bottom:1px solid {P["gray_100"]};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
<td style="vertical-align:middle;width:48px;white-space:nowrap;">
<span style="font-size:12px;color:{P["gray_400"]};font-variant-numeric:tabular-nums;">{time_part}</span>
</td>
<td style="vertical-align:middle;padding-right:8px;">
{badge}
</td>
<td style="vertical-align:middle;">
<a href="{link}" target="_blank" style="font-size:14px;color:{P["gray_800"]};text-decoration:none;font-weight:500;line-height:1.5;">{title}</a>{heat_html}
</td>
</tr></table>
</td></tr>"""

            html += """</table>"""

        # ── Section 2: News ──
        if news:
            if weibo:
                html += f"""
<!-- Spacer between sections -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
<td style="height:24px;"></td>
</tr></table>"""

            html += f"""
<!-- Section: News -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr><td style="padding-bottom:12px;">
<table role="presentation" cellpadding="0" cellspacing="0"><tr>
<td style="background:{P["navy_mid"]};width:4px;height:20px;border-radius:2px;"></td>
<td style="padding-left:10px;"><span style="font-size:16px;font-weight:700;color:{P["navy_dark"]};">📰 新闻热点</span></td>
</tr></table>
</td></tr>"""

            for item in news[:15]:
                time_part = item.get('created_at', '')[11:16] if item.get('created_at') else ''
                brand = item.get('brand', '')
                title = item.get('title', '')
                link = item.get('url', '')
                source = item.get('source', '')
                summary = item.get('summary', '') or item.get('content', '')
                if summary and len(summary) > 120:
                    summary = summary[:120] + '...'
                badge = _brand_badge_html(brand) if brand else ''

                source_html = ''
                if source:
                    source_html = f'<span style="font-size:11px;color:{P["gray_500"]};margin-left:6px;">· {source}</span>'

                summary_html = ''
                if summary:
                    summary_html = f'<div style="margin-top:4px;font-size:12px;color:{P["gray_400"]};line-height:1.6;padding-left:0;">{summary}</div>'

                html += f"""
<tr><td style="padding:10px 0;border-bottom:1px solid {P["gray_100"]};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
<td style="vertical-align:top;width:48px;white-space:nowrap;">
<span style="font-size:12px;color:{P["gray_400"]};font-variant-numeric:tabular-nums;">{time_part}</span>
</td>
<td style="vertical-align:top;padding-right:8px;">
{badge}
</td>
<td style="vertical-align:top;">
<a href="{link}" target="_blank" style="font-size:14px;color:{P["gray_800"]};text-decoration:none;font-weight:500;line-height:1.5;">{title}</a>{source_html}{summary_html}
</td>
</tr></table>
</td></tr>"""

            html += """</table>"""

        # ── Empty State ──
        if not weibo and not news:
            html += f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
<td style="padding:40px 0;text-align:center;">
<span style="font-size:14px;color:{P["gray_400"]};">📭 昨日暂无关注的品牌舆情</span>
</td>
</tr></table>"""

        # ── Footer ──
        html += f"""
</td></tr>

<!-- Footer -->
<tr><td style="background:{P["white"]};padding:16px 28px 24px 28px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr><td style="border-top:1px solid {P["gray_200"]};padding-top:16px;">
<span style="font-size:11px;color:{P["gray_400"]};">生成时间：{generated_at}　|　汽车行业舆情监控系统</span>
</td></tr>
</table>
</td></tr>

</table>
</td></tr></table>
</body></html>"""

        await asyncio.to_thread(
            self._send_email_sync,
            f'昨日汽车舆情热搜汇总 - {date_str}',
            html,
        )

    # ─── Weekly Feishu Card ───────────────────────────────────────────────────
    async def send_weekly_feishu(self, report: dict):
        if not self.feishu_webhook:
            return

        elements = []
        week_start = report.get('week_start', '')
        week_end = report.get('week_end', '')
        ai_analysis = report.get('ai_analysis', '')
        by_brand = report.get('by_brand', {})
        total = report.get('total_events', 0)

        elements.append({
            'tag': 'div',
            'text': {
                'tag': 'lark_md',
                'content': f'<font color="{PALETTE["gray_400"]}">汽车行业周报</font>  <font color="{PALETTE["gray_800"]}">**{week_start} 至 {week_end}**</font>'
            }
        })
        elements.append({'tag': 'hr'})

        if ai_analysis:
            elements.append({
                'tag': 'div',
                'text': {
                    'tag': 'lark_md',
                    'content': f'**🤖 AI 行业分析**\n\n<font color="{PALETTE["gray_600"]}">{ai_analysis}</font>'
                }
            })
            elements.append({'tag': 'hr'})

        elements.append({
            'tag': 'div',
            'text': {
                'tag': 'lark_md',
                'content': f'**📋 品牌分类明细** (共 <font color="{PALETTE["amber"]}">{total}</font> 个事件)'
            }
        })

        for brand, events in by_brand.items():
            brand_tag = _brand_badge_feishu(brand)
            elements.append({
                'tag': 'div',
                'text': {
                    'tag': 'lark_md',
                    'content': f'\n{brand_tag} **{brand}**'
                }
            })
            for i, event in enumerate(events, 1):
                title = event.get('title', '')
                sources = event.get('sources', '[]')
                try:
                    src_list = json.loads(sources) if isinstance(sources, str) else sources
                    src_str = ' / '.join(src_list[:3])
                except (json.JSONDecodeError, TypeError):
                    src_str = str(sources)
                count = event.get('article_count', 1)
                elements.append({
                    'tag': 'div',
                    'text': {
                        'tag': 'lark_md',
                        'content': f"　{i}. {title}  <font color=\"{PALETTE['gray_400']}\">【{src_str}】{count}篇</font>"
                    }
                })

        elements.append({'tag': 'hr'})
        elements.append({
            'tag': 'div',
            'text': {
                'tag': 'lark_md',
                'content': f'<font color="{PALETTE["gray_400"]}">生成时间：{report.get("generated_at", "")}</font>'
            }
        })

        payload = {
            'msg_type': 'interactive',
            'card': {
                'header': {
                    'title': {'tag': 'plain_text', 'content': '📊 汽车行业周报'},
                    'template': 'turquoise',
                },
                'elements': elements,
            }
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.feishu_webhook,
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        logger.info("飞书周报推送成功")
                    else:
                        error_text = await resp.text()
                        logger.error(f"飞书周报推送失败: {resp.status} {error_text}")
        except Exception as e:
            logger.error(f"飞书推送异常: {e}")

    # ─── Weekly Email ─────────────────────────────────────────────────────────
    async def send_weekly_email(self, report: dict):
        if not self.email_sender or not self.email_password:
            return

        week_start = report.get('week_start', '')
        week_end = report.get('week_end', '')
        ai_analysis = report.get('ai_analysis', '')
        by_brand = report.get('by_brand', {})
        total = report.get('total_events', 0)
        generated_at = report.get('generated_at', '')

        P = PALETTE

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:{P["gray_50"]};font-family:'Microsoft YaHei','PingFang SC','Helvetica Neue',Arial,sans-serif;-webkit-font-smoothing:antialiased;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{P["gray_50"]};"><tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

<!-- Header Banner -->
<tr><td style="background:linear-gradient(135deg,{P["navy_dark"]} 0%,{P["navy_light"]} 100%);background-color:{P["navy_dark"]};padding:28px 32px 24px 32px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
<td style="vertical-align:middle;">
<h1 style="margin:0;font-size:22px;font-weight:700;color:{P["white"]};letter-spacing:1px;">📊 汽车行业周报</h1>
</td>
<td align="right" style="vertical-align:middle;">
<span style="font-size:13px;color:{P["gray_400"]};font-weight:400;">{week_start} 至 {week_end}</span>
</td>
</tr></table>
</td></tr>

<!-- Accent Line -->
<tr><td style="background:{P["amber_soft"]};height:3px;font-size:0;line-height:0;">&nbsp;</td></tr>

<!-- Content Body -->
<tr><td style="background:{P["white"]};padding:24px 28px 8px 28px;">"""

        # ── AI Analysis Section ──
        if ai_analysis:
            html += f"""
<!-- AI Analysis -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr><td style="background:{P["gray_50"]};border-left:4px solid {P["navy_mid"]};border-radius:0 6px 6px 0;padding:16px 20px;margin-bottom:20px;">
<table role="presentation" cellpadding="0" cellspacing="0"><tr>
<td style="padding-bottom:8px;"><span style="font-size:14px;font-weight:700;color:{P["navy_dark"]};">🤖 AI 行业分析</span></td>
</tr><tr>
<td><span style="font-size:13px;color:{P["gray_600"]};line-height:1.8;">{ai_analysis}</span></td>
</tr></table>
</td></tr>
</table>"""

        # ── Brand Events Section ──
        html += f"""
<!-- Section: Brand Events -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr><td style="padding-bottom:12px;">
<table role="presentation" cellpadding="0" cellspacing="0"><tr>
<td style="background:{P["navy_mid"]};width:4px;height:20px;border-radius:2px;"></td>
<td style="padding-left:10px;"><span style="font-size:16px;font-weight:700;color:{P["navy_dark"]};">📋 品牌分类明细</span></td>
<td style="padding-left:8px;"><span style="font-size:13px;color:{P["gray_400"]};">(共 <span style="color:{P["amber"]};font-weight:600;">{total}</span> 个事件)</span></td>
</tr></table>
</td></tr>"""

        for brand, events in by_brand.items():
            badge = _brand_badge_html(brand)
            html += f"""
<tr><td style="padding:14px 0 6px 0;">
{badge}
</td></tr>"""

            for i, event in enumerate(events, 1):
                title = event.get('title', '')
                sources = event.get('sources', '[]')
                try:
                    src_list = json.loads(sources) if isinstance(sources, str) else sources
                    src_str = ' / '.join(src_list[:3])
                except (json.JSONDecodeError, TypeError):
                    src_str = str(sources)
                count = event.get('article_count', 1)

                html += f"""
<tr><td style="padding:6px 0 6px 16px;border-bottom:1px solid {P["gray_100"]};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
<td style="vertical-align:top;width:22px;">
<span style="font-size:12px;color:{P["gray_400"]};">{i}.</span>
</td>
<td>
<span style="font-size:13px;color:{P["gray_800"]};font-weight:500;line-height:1.5;">{title}</span>
<div style="margin-top:2px;">
<span style="font-size:11px;color:{P["gray_400"]};">【{src_str}】{count}篇报道</span>
</div>
</td>
</tr></table>
</td></tr>"""

        html += """</table>"""

        # ── Footer ──
        html += f"""
</td></tr>

<!-- Footer -->
<tr><td style="background:{P["white"]};padding:16px 28px 24px 28px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr><td style="border-top:1px solid {P["gray_200"]};padding-top:16px;">
<span style="font-size:11px;color:{P["gray_400"]};">生成时间：{generated_at}　|　汽车行业舆情监控系统</span>
</td></tr>
</table>
</td></tr>

</table>
</td></tr></table>
</body></html>"""

        await asyncio.to_thread(
            self._send_email_sync,
            f'汽车行业周报 - {week_start} 至 {week_end}',
            html,
        )

    def _send_email_sync(self, subject: str, html_content: str):
        try:
            message = MIMEMultipart()
            message['From'] = self.email_sender
            message['To'] = ','.join(self.email_recipients)
            message['Subject'] = Header(subject, 'utf-8')
            message.attach(MIMEText(html_content, 'html', 'utf-8'))

            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=30) as server:
                try:
                    server.starttls()
                except smtplib.SMTPNotSupportedError:
                    pass
                server.login(self.email_sender, self.email_password)
                server.sendmail(self.email_sender, self.email_recipients, message.as_string())
            logger.info(f"邮件发送成功: {subject}")
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            raise

    async def mark_all_pushed(self, report: dict):
        news = report.get('news', [])
        if news:
            ids = [a['id'] for a in news if 'id' in a]
            if ids:
                self.vault.mark_pushed(ids)

        try:
            import aiosqlite
            from config import DATABASE_PATH
            weibo = report.get('weibo', [])
            if weibo:
                weibo_ids = [a['id'] for a in weibo if 'id' in a]
                if weibo_ids:
                    async with aiosqlite.connect(DATABASE_PATH) as db:
                        placeholders = ','.join(['?'] * len(weibo_ids))
                        await db.execute(
                            f'UPDATE weibo_hot_search SET is_pushed = 1 WHERE id IN ({placeholders})',
                            weibo_ids
                        )
                        await db.commit()
        except Exception as e:
            logger.error(f"标记微博已推送失败: {e}")
