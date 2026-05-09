"""邮件周报模板 v2 — 独立编号 + AI总结升级 + 品牌分隔 + 缺失品牌标注"""
from templates.design_tokens import (
    PALETTE, SPACING, brand_badge_html, brand_color, DIMENSION_ICONS,
)
from v2.constants import BRAND_PATTERNS


def render_weekly_email(
    week_start: str, week_end: str, ai_summary: str,
    by_brand: dict, total: int, generated_at: str,
) -> str:
    P = PALETTE
    S = SPACING

    body_rows = ""
    all_brands = list(BRAND_PATTERNS.keys())

    for brand in all_brands:
        dims = by_brand.get(brand, {})
        badge = brand_badge_html(brand, "large")
        brand_total = sum(len(items) for items in dims.values())

        body_rows += f"""
<tr>
<td style="padding:{S['lg']}px 0 {S['xs']}px;">
<table role="presentation" cellpadding="0" cellspacing="0" width="100%">
<tr>
<td style="padding-bottom:{S['sm']}px;">
<table role="presentation" cellpadding="0" cellspacing="0">
<tr>
<td style="background:{brand_color(brand)};width:3px;height:20px;border-radius:2px;vertical-align:middle;"></td>
<td style="padding-left:10px;vertical-align:middle;">{badge}</td>
<td style="padding-left:8px;vertical-align:middle;">
<span style="font-size:12px;color:{P['text_tertiary']};">{brand_total}条</span>
</td>
</tr>
</table>
</td>
</tr>
</table>
</td>
</tr>"""

        if not dims:
            body_rows += f"""
<tr>
<td style="padding:{S['xs']}px 0 {S['md']}px {S['md']}px;border-bottom:1px solid {P['divider']};">
<span style="font-size:12px;color:{P['text_tertiary']};">本周暂无相关动态</span>
</td>
</tr>"""
            continue

        brand_num = 0
        for dim_name, items in dims.items():
            if not items:
                continue
            icon = DIMENSION_ICONS.get(dim_name, '')
            body_rows += f"""
<tr>
<td style="padding:{S['sm']}px 0 {S['xs']}px {S['md']}px;">
<span style="font-size:13px;font-weight:700;color:{P['text_primary']};background:{P['surface_hover']};padding:2px 8px;border-radius:4px;">{icon} {dim_name}</span>
</td>
</tr>"""
            for item in items:
                brand_num += 1
                title = item.get('title', '')
                summary = item.get('summary', '')
                source = item.get('source', '')
                created = item.get('created_at', '')
                url = item.get('url', '')
                time_part = created[:16] if created else ''
                meta_parts = []
                if time_part:
                    meta_parts.append(time_part)
                if source:
                    meta_parts.append(source)
                meta = ' · '.join(meta_parts)
                desc = (
                    f'<div style="font-size:12px;color:{P["text_secondary"]};'
                    f'margin-top:4px;line-height:1.6;overflow:hidden;'
                    f'display:-webkit-box;-webkit-box-orient:vertical;'
                    f'-webkit-line-clamp:2;">{summary}</div>'
                    if summary else ''
                )
                body_rows += f"""
<tr>
<td style="padding:{S['xs']}px 0 {S['sm']}px {S['lg']}px;border-bottom:1px solid {P['divider']};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr>
<td style="vertical-align:top;width:28px;padding-top:1px;">
<span style="font-size:12px;font-weight:700;color:{P['text_tertiary']};">{brand_num}.</span>
</td>
<td style="vertical-align:top;">
<a href="{url}" target="_blank" style="font-size:14px;color:{P['text_primary']};text-decoration:none;font-weight:600;line-height:1.6;">{title}</a>
{desc}
<div style="margin-top:4px;font-size:11px;color:{P['text_tertiary']};">{meta}</div>
</td>
</tr>
</table>
</td>
</tr>"""

    wp = week_start[5:] if len(week_start) >= 10 else week_start
    we = week_end[5:] if len(week_end) >= 10 else week_end

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
<h1 style="margin:0;font-size:20px;font-weight:700;color:{P['white']};letter-spacing:0.5px;">
上周汽车行业10个品牌舆情汇总 {wp}-{we}
</h1>
</td>
<td align="right" style="vertical-align:middle;">
<span style="font-size:13px;color:rgba(255,255,255,0.65);">{week_start} ~ {week_end}</span>
</td>
</tr>
</table>
</td>
</tr>

<tr><td style="background:{P['blue_link']};height:3px;font-size:0;">&nbsp;</td></tr>

<tr><td style="background:{P['surface']};padding:{S['xl']}px {S['xl']}px {S['md']}px;">

<!-- AI Summary -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:{S['xl']}px;">
<tr>
<td style="background:linear-gradient(135deg,{P['blue_bg']} 0%,{P['surface']} 100%);border-left:5px solid {P['blue_link']};border-radius:0 12px 12px 0;padding:{S['lg']}px {S['xl']}px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr>
<td style="padding-bottom:{S['sm']}px;">
<span style="font-size:15px;font-weight:700;color:{P['navy_dark']};">📊 上周核心洞察</span>
<span style="font-size:11px;color:{P['text_tertiary']};margin-left:8px;">AI 生成 · 仅供参考</span>
</td>
</tr>
<tr>
<td>
<span style="font-size:13px;color:{P['text_primary']};line-height:1.9;">{ai_summary or '本周暂无核心动态总结。'}</span>
</td>
</tr>
</table>
</td>
</tr>
</table>

<!-- Articles -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:{S['md']}px;">
<tr><td style="padding-bottom:{S['md']}px;">
<table role="presentation" cellpadding="0" cellspacing="0">
<tr>
<td style="background:{P['green_dot']};width:4px;height:22px;border-radius:2px;"></td>
<td style="padding-left:12px;">
<span style="font-size:17px;font-weight:700;color:{P['text_primary']};">🚗 汽车行业周度热点资讯</span>
<span style="font-size:12px;color:{P['text_tertiary']};margin-left:8px;">总计 {total} 条</span>
</td>
</tr>
</table>
</td></tr>
{body_rows}
</table>

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
