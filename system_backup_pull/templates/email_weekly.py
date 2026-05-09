"""邮件周报模板 v3 — 苹果简约科技风 · 独立编号 + AI核心洞察 + 品牌分组"""
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

    wp = week_start[5:] if len(week_start) >= 10 else week_start
    we = week_end[5:] if len(week_end) >= 10 else week_end

    body_rows = ""
    all_brands = list(BRAND_PATTERNS.keys())

    for brand in all_brands:
        dims = by_brand.get(brand, {})
        badge = brand_badge_html(brand, "large")
        brand_total = sum(len(items) for items in dims.values())

        body_rows += f"""
<tr>
<td style="padding:{S['md']}px 0 {S['xs']}px;">
<table role="presentation" cellpadding="0" cellspacing="0" width="100%">
<tr>
<td style="padding-bottom:{S['sm']}px;">
<table role="presentation" cellpadding="0" cellspacing="0">
<tr>
<td style="background:{brand_color(brand)};width:3px;height:18px;border-radius:2px;vertical-align:middle;"></td>
<td style="padding-left:8px;vertical-align:middle;">{badge}</td>
<td style="padding-left:6px;vertical-align:middle;">
<span style="font-size:11px;color:{P['text_tertiary']};">{brand_total}条</span>
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
<span style="font-size:11px;color:{P['text_tertiary']};">本周暂无相关动态</span>
</td></tr>"""
            continue

        brand_num = 0
        for dim_name, items in dims.items():
            if not items:
                continue
            icon = DIMENSION_ICONS.get(dim_name, '')
            body_rows += f"""
<tr>
<td style="padding:{S['xs']}px 0 {S['xs']}px {S['md']}px;">
<span style="font-size:12px;font-weight:600;color:{P['text_primary']};">{icon} {dim_name}</span>
</td></tr>"""
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
                    f'<div style="font-size:11px;color:{P["text_secondary"]};'
                    f'margin-top:2px;line-height:1.5;overflow:hidden;'
                    f'display:-webkit-box;-webkit-box-orient:vertical;'
                    f'-webkit-line-clamp:2;">{summary}</div>'
                    if summary else ''
                )
                body_rows += f"""
<tr>
<td style="padding:2px 0 {S['sm']}px {S['lg']}px;border-bottom:1px solid {P['divider']};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr>
<td style="vertical-align:top;width:24px;padding-top:2px;">
<span style="font-size:11px;font-weight:600;color:{P['text_tertiary']};">{brand_num}.</span>
</td>
<td style="vertical-align:top;">
<a href="{url}" target="_blank" style="font-size:13px;color:{P['text_primary']};text-decoration:none;font-weight:600;line-height:1.5;">{title}</a>
{desc}
<div style="margin-top:3px;font-size:10px;color:{P['text_tertiary']};">{meta}</div>
</td>
</tr>
</table>
</td></tr>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta name="color-scheme" content="light">
<meta name="supported-color-schemes" content="light">
</head>
<body style="margin:0;padding:0;background:{P['bg_primary']};font-family:'PingFang SC','Microsoft YaHei','Helvetica Neue',sans-serif;-webkit-font-smoothing:antialiased;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{P['bg_primary']};">
<tr><td align="center" style="padding:{S['lg']}px {S['sm']}px;">

<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;border-radius:14px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.06);">

<tr>
<td style="background:linear-gradient(135deg,{P['accent_gradient_from']} 0%,{P['accent_gradient_to']} 100%);padding:{S['lg']}px {S['xl']}px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr>
<td style="vertical-align:middle;">
<h1 style="margin:0;font-size:18px;font-weight:700;color:{P['white']};letter-spacing:0.3px;">📊 汽车行业 · 周报 {wp}–{we}</h1>
</td>
<td align="right" style="vertical-align:middle;">
<span style="font-size:11px;color:rgba(255,255,255,0.5);">{week_start} ~ {week_end}</span>
</td>
</tr>
</table>
</td>
</tr>

<tr><td style="background:{P['blue_link']};height:3px;font-size:0;">&nbsp;</td></tr>

<tr><td style="background:{P['surface']};padding:{S['xl']}px {S['xl']}px {S['sm']}px;">

<!-- AI 核心洞察 -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:{S['xl']}px;">
<tr>
<td style="background:#F8F8FA;border-radius:12px;padding:{S['lg']}px {S['lg']}px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr>
<td style="padding-bottom:{S['sm']}px;">
<span style="font-size:14px;font-weight:700;color:{P['text_primary']};">💡 核心洞察</span>
<span style="font-size:10px;color:{P['text_tertiary']};margin-left:6px;">AI · 仅供参 考</span>
</td>
</tr>
<tr><td style="font-size:12px;color:{P['text_primary']};line-height:1.8;">
{ai_summary or '本周暂无核心动态总结'}
</td></tr>
</table>
</td></tr></table>

<!-- 热点资讯 -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:{S['md']}px;">
<tr><td style="padding-bottom:{S['sm']}px;">
<span style="font-size:15px;font-weight:700;color:{P['text_primary']};">🚗 周度热点资讯</span>
<span style="font-size:11px;color:{P['text_tertiary']};margin-left:6px;">{total}条</span>
</td></tr>
{body_rows}
</table>

</td></tr>

<tr><td style="background:{P['surface']};padding:{S['sm']}px {S['xl']}px {S['md']}px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr><td style="border-top:1px solid {P['divider']};padding-top:{S['sm']}px;">
<span style="font-size:10px;color:{P['text_tertiary']};">生成 {generated_at} · 汽车行业舆情监控系统</span>
</td></tr>
</table>
</td></tr>

</table>
</td></tr></table>
</body></html>"""

    return html