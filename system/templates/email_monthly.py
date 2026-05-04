"""邮件月报模板 — 品牌频次榜 + 热搜词表格 + AI总结"""
from templates.design_tokens import PALETTE, SPACING, brand_color


def render_monthly_email(report: dict) -> str:
    P = PALETTE
    S = SPACING
    label = report.get('label', '')
    brands = report.get('brands', [])
    total = report.get('total_mentions', 0)
    ai = report.get('ai_summary', '')
    gen = report.get('generated_at', '')
    ym = report.get('year_month', '')

    # ── 品牌频次榜 ──
    rank_rows = ''
    max_cnt = max((b['count'] for b in brands), default=1)
    for i, b in enumerate(brands):
        bc = brand_color(b['brand'])
        pct = int(b['count'] / max_cnt * 100) if max_cnt > 0 else 0
        rank_rows += f"""
<tr>
<td style="padding:{S['xs']}px 0;width:28px;text-align:right;">
<span style="font-size:14px;font-weight:700;color:{P['text_tertiary']};">{i + 1}.</span>
</td>
<td style="padding:{S['xs']}px {S['sm']}px;width:80px;">
<span style="font-size:13px;font-weight:600;color:{bc};">{b['brand']}</span>
</td>
<td style="padding:{S['xs']}px {S['sm']}px;width:100%;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr>
<td style="background:{bc};height:16px;border-radius:3px;width:{pct}%;font-size:0;">&nbsp;</td>
<td style="width:{100 - pct}%;"></td>
</tr>
</table>
</td>
<td style="padding:{S['xs']}px 0;text-align:right;width:50px;">
<span style="font-size:16px;font-weight:800;color:{P['text_primary']};">{b['count']}</span>
<span style="font-size:11px;color:{P['text_tertiary']};">次</span>
</td>
</tr>"""

    # ── 热搜词表格 ──
    kw_rows = ''
    for b in brands:
        bc = brand_color(b['brand'])
        items = b.get('items', [])
        if not items:
            continue
        keywords_html = ''
        for it in items[:15]:
            date = it.get('date', '')[-5:] if it.get('date') else ''
            keywords_html += (
                f'<span style="display:inline-block;border:1px solid {P["divider"]};'
                f'border-radius:4px;padding:2px 8px;margin:2px 4px 2px 0;'
                f'font-size:12px;color:{P["text_primary"]};background:{P["surface_hover"]};">'
                f'{it["title"]}'
                f'<span style="color:{P["text_tertiary"]};font-size:10px;margin-left:4px;">{date}</span>'
                f'</span>'
            )
        kw_rows += f"""
<tr>
<td style="padding:{S['sm']}px {S['sm']}px {S['xs']}px;vertical-align:top;width:80px;">
<span style="font-size:12px;font-weight:700;color:{bc};">{b['brand']}</span>
</td>
<td style="padding:{S['sm']}px 0 {S['xs']}px;line-height:1.8;">
{keywords_html}
</td>
</tr>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:{P['bg_primary']};font-family:'Microsoft YaHei','PingFang SC','Helvetica Neue',Arial,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{P['bg_primary']};">
<tr><td align="center" style="padding:{S['lg']}px {S['sm']}px;">

<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.06);">

<tr>
<td style="background:linear-gradient(135deg,{P['navy_dark']} 0%,{P['navy_mid']} 100%);padding:{S['lg']}px {S['xl']}px;">
<h1 style="margin:0;font-size:20px;font-weight:700;color:{P['white']};">📅 微博月度舆情报告 {label}</h1>
</td>
</tr>

<tr><td style="background:{P['blue_link']};height:3px;font-size:0;">&nbsp;</td></tr>

<tr><td style="background:{P['surface']};padding:{S['xl']}px {S['xl']}px {S['md']}px;">

<!-- 数据概览 -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:{S['lg']}px;">
<tr><td style="background:{P['surface_hover']};border-radius:10px;padding:{S['md']}px {S['lg']}px;text-align:center;">
<span style="font-size:15px;color:{P['text_primary']};">{label} 共监测到 <b style="color:{P['blue_link']};font-size:20px;">{total}</b> 条汽车品牌热搜</span>
</td></tr>
</table>

<!-- AI月度总结 -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:{S['xl']}px;">
<tr><td style="background:linear-gradient(135deg,{P['blue_bg']} 0%,{P['surface']} 100%);border-left:5px solid {P['blue_link']};border-radius:0 12px 12px 0;padding:{S['lg']}px {S['xl']}px;">
<div style="font-size:15px;font-weight:700;color:{P['navy_dark']};margin-bottom:{S['sm']}px;">📊 AI月度总结</div>
<div style="font-size:13px;color:{P['text_primary']};line-height:1.9;">{ai or '暂无AI月度总结'}</div>
</td></tr>
</table>

<!-- 品牌曝光频次榜 -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:{S['lg']}px;">
<tr><td style="padding-bottom:{S['md']}px;">
<span style="font-size:17px;font-weight:700;color:{P['text_primary']};">📈 品牌曝光频次榜</span>
</td></tr>
{rank_rows}
</table>

<!-- 热搜词列表 -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:{S['md']}px;">
<tr><td style="padding-bottom:{S['md']}px;border-top:1px solid {P['divider_bold']};padding-top:{S['md']}px;">
<span style="font-size:17px;font-weight:700;color:{P['text_primary']};">🔤 热搜词列表</span>
</td></tr>
{kw_rows}
</table>

</td></tr>

<tr><td style="background:{P['surface']};padding:{S['md']}px {S['xl']}px {S['lg']}px;">
<span style="font-size:11px;color:{P['text_tertiary']};">生成时间：{gen} | 汽车行业舆情监控系统</span>
</td></tr>

</table>
</td></tr></table>
</body></html>"""
    return html
