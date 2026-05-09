"""邮件日报模板 v2 — 品牌分组 + 摘要 + 数据统计栏"""
from typing import List
from collections import OrderedDict

from templates.design_tokens import (
    PALETTE, SPACING, brand_badge_html, stat_card_html,
)


def _group_by_brand(items: List[dict], brand_key: str = "brand") -> OrderedDict:
    grouped = OrderedDict()
    for item in items:
        brand = item.get(brand_key, '') or '其他'
        if brand not in grouped:
            grouped[brand] = []
        grouped[brand].append(item)
    return grouped


def render_daily_email(
    weibo: List[dict], news: List[dict], date_str: str, generated_at: str
) -> str:
    P = PALETTE
    S = SPACING
    w_count = len(weibo)
    n_count = len(news)
    total = w_count + n_count

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta name="color-scheme" content="light">
<meta name="supported-color-schemes" content="light">
</head>
<body style="margin:0;padding:0;background:{P['bg_primary']};font-family:'Microsoft YaHei','PingFang SC','Helvetica Neue',Arial,sans-serif;-webkit-font-smoothing:antialiased;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{P['bg_primary']};">
<tr><td align="center" style="padding:{S['lg']}px {S['sm']}px;">

<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.06);">

<tr>
<td style="background:linear-gradient(135deg,{P['navy_dark']} 0%,{P['navy_mid']} 100%);padding:{S['lg']}px {S['xl']}px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr>
<td style="vertical-align:middle;">
<h1 style="margin:0;font-size:20px;font-weight:700;color:{P['white']};letter-spacing:0.5px;">昨日汽车行业舆情热点新闻</h1>
</td>
<td align="right" style="vertical-align:middle;">
<span style="font-size:13px;color:rgba(255,255,255,0.65);">{date_str}</span>
</td>
</tr>
</table>
</td>
</tr>

<tr><td style="background:{P['amber_accent']};height:3px;font-size:0;">&nbsp;</td></tr>

<tr><td style="background:{P['surface']};padding:{S['xl']}px {S['xl']}px {S['md']}px;">

<!-- 数据统计栏 -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:{S['lg']}px;">
<tr>
<td style="background:{P['surface_hover']};border-radius:10px;padding:{S['md']}px {S['lg']}px;text-align:center;">
<table role="presentation" cellpadding="0" cellspacing="0" align="center">
<tr>
<td style="padding:0 20px;text-align:center;border-right:1px solid {P['divider']};">
<div style="font-size:24px;font-weight:800;color:{P['navy_mid']};line-height:1.2;">{total}</div>
<div style="font-size:11px;color:{P['text_tertiary']};margin-top:2px;">总计监测</div>
</td>
<td style="padding:0 20px;text-align:center;border-right:1px solid {P['divider']};">
<div style="font-size:24px;font-weight:800;color:{P['amber_accent']};line-height:1.2;">{n_count}</div>
<div style="font-size:11px;color:{P['text_tertiary']};margin-top:2px;">新闻热点</div>
</td>
<td style="padding:0 20px;text-align:center;">
<div style="font-size:24px;font-weight:800;color:#E74C3C;line-height:1.2;">{w_count}</div>
<div style="font-size:11px;color:{P['text_tertiary']};margin-top:2px;">微博热搜</div>
</td>
</tr>
</table>
</td>
</tr>
</table>"""

    has_content = False

    # ── 微博热搜板块 ──
    if weibo:
        has_content = True
        html += f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:{S['lg']}px;">
<tr><td style="padding-bottom:{S['md']}px;">
<table role="presentation" cellpadding="0" cellspacing="0">
<tr>
<td style="background:{P['amber_accent']};width:4px;height:22px;border-radius:2px;"></td>
<td style="padding-left:12px;">
<span style="font-size:17px;font-weight:700;color:{P['text_primary']};">🔥 微博热搜</span>
<span style="font-size:12px;color:{P['text_tertiary']};margin-left:8px;">{w_count}条</span>
</td>
</tr>
</table>
</td></tr>"""
        grouped = _group_by_brand(weibo, 'brand_group')
        for brand, items in grouped.items():
            badge = brand_badge_html(brand, "large")
            html += f"""
<tr><td style="padding:{S['sm']}px 0 {S['xs']}px;">{badge}</td></tr>"""
            for item in items[:5]:
                time_part = (
                    item.get('created_at', '')[11:16]
                    if item.get('created_at') else ''
                )
                title = item.get('title', '')
                link = item.get('link', '')
                html += f"""
<tr><td style="padding:{S['xs']}px 0 {S['xs']}px {S['md']}px;border-bottom:1px solid {P['divider']};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr>
<td style="vertical-align:top;width:44px;white-space:nowrap;padding-top:2px;">
<span style="font-size:11px;color:{P['text_tertiary']};font-variant-numeric:tabular-nums;">{time_part}</span>
</td>
<td style="vertical-align:top;">
<a href="{link}" target="_blank" style="font-size:14px;color:{P['text_primary']};text-decoration:none;font-weight:500;line-height:1.6;">{title}</a>
</td>
</tr>
</table>
</td></tr>"""
        html += "</table>"

    # ── 新闻热点板块 ──
    if news:
        if has_content:
            html += (
                f'<table role="presentation" width="100%" cellpadding="0" '
                f'cellspacing="0"><tr><td style="height:{S["lg"]}px;">'
                f'</td></tr></table>'
            )
        has_content = True
        html += f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:{S['lg']}px;">
<tr><td style="padding-bottom:{S['md']}px;">
<table role="presentation" cellpadding="0" cellspacing="0">
<tr>
<td style="background:{P['blue_link']};width:4px;height:22px;border-radius:2px;"></td>
<td style="padding-left:12px;">
<span style="font-size:17px;font-weight:700;color:{P['text_primary']};">📰 新闻热点</span>
<span style="font-size:12px;color:{P['text_tertiary']};margin-left:8px;">{n_count}条</span>
</td>
</tr>
</table>
</td></tr>"""
        grouped = _group_by_brand(news, 'brand')
        for brand, items in grouped.items():
            badge = brand_badge_html(brand, "large")
            html += f"""
<tr><td style="padding:{S['sm']}px 0 {S['xs']}px;">{badge}</td></tr>"""
            for item in items[:8]:
                time_part = (
                    item.get('created_at', '')[11:16]
                    if item.get('created_at') else ''
                )
                title = item.get('title', '')
                link = item.get('url', '')
                source = item.get('source', '')
                summary = item.get('summary', '') or item.get('content', '')
                if summary:
                    summary = summary[:120].strip()
                desc_html = (
                    f'<div style="font-size:12px;color:{P["text_secondary"]};'
                    f'margin-top:4px;line-height:1.6;overflow:hidden;'
                    f'display:-webkit-box;-webkit-box-orient:vertical;'
                    f'-webkit-line-clamp:2;">{summary}</div>'
                    if summary else ''
                )
                meta_parts = []
                if source:
                    meta_parts.append(
                        f'<span style="font-size:11px;color:{P["text_tertiary"]};">'
                        f'{source}</span>'
                    )
                if time_part:
                    meta_parts.append(
                        f'<span style="font-size:11px;color:{P["text_tertiary"]};">'
                        f'{time_part}</span>'
                    )
                meta = ' · '.join(meta_parts)
                html += f"""
<tr><td style="padding:{S['sm']}px 0 {S['sm']}px {S['md']}px;border-bottom:1px solid {P['divider']};">
<a href="{link}" target="_blank" style="font-size:14px;color:{P['text_primary']};text-decoration:none;font-weight:600;line-height:1.6;">{title}</a>
{desc_html}
<div style="margin-top:6px;">{meta}</div>
</td></tr>"""
        html += "</table>"

    if not has_content:
        html += f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr><td style="padding:{S['xxl']}px 0;text-align:center;">
<div style="font-size:48px;margin-bottom:{S['md']}px;">📭</div>
<div style="font-size:15px;color:{P['text_secondary']};font-weight:500;">昨日暂无关注的品牌舆情</div>
<div style="font-size:12px;color:{P['text_tertiary']};margin-top:4px;">系统将持续监测，有动态将第一时间推送</div>
</td></tr>
</table>"""

    html += f"""
</td></tr>

<tr><td style="background:{P['surface']};padding:{S['md']}px {S['xl']}px {S['lg']}px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr><td style="border-top:1px solid {P['divider_bold']};padding-top:{S['md']}px;">
<span style="font-size:11px;color:{P['text_tertiary']};">生成时间：{generated_at}　|　汽车行业舆情监控系统</span>
</td></tr>
</table>
</td></tr>

</table>
</td></tr></table>
</body></html>"""

    return html
