"""微博月报模板 V5 — Apple 精约科技风 · 品牌卡片 + 热词云 + 趋势洞察"""

from urllib.parse import quote
from templates.design_tokens import PALETTE, SPACING, brand_color, email_shell


def render_monthly_email(report: dict) -> str:
    P = PALETTE
    S = SPACING
    label = report.get('label', '')
    brands = report.get('brands', [])
    total = report.get('total_appears', report.get('total_mentions', 0))
    total_events = report.get('total_events', 0)
    ai = report.get('ai_summary', '')
    gen = report.get('generated_at', '')

    # ═══════ 统计概览卡 ═══════
    stats_card = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:{S['lg']}px;">
<tr>
<td style="background:linear-gradient(135deg, #1A1A2E 0%, #16213E 50%, #0F3460 100%);border-radius:14px;padding:{S['lg']}px {S['xl']}px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr>
<td style="text-align:center;padding:0 16px;border-right:1px solid rgba(255,255,255,0.1);">
<div style="font-size:36px;font-weight:800;color:{P['amber_accent']};line-height:1.1;">{total}</div>
<div style="font-size:11px;color:rgba(255,255,255,0.5);margin-top:4px;">热搜总出现</div>
</td>
<td style="text-align:center;padding:0 16px;border-right:1px solid rgba(255,255,255,0.1);">
<div style="font-size:36px;font-weight:800;color:#FF6B35;line-height:1.1;">{total_events}</div>
<div style="font-size:11px;color:rgba(255,255,255,0.5);margin-top:4px;">独立事件</div>
</td>
<td style="text-align:center;padding:0 16px;">
<div style="font-size:36px;font-weight:800;color:#4ECDC4;line-height:1.1;">{len(brands)}</div>
<div style="font-size:11px;color:rgba(255,255,255,0.5);margin-top:4px;">上榜品牌</div>
</td>
</tr>
</table>
</td>
</tr>
</table>"""

    # ═══════ AI 月度洞察卡 ═══════
    ai_card = ''
    if ai:
        ai_card = f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:{S['xl']}px;">
<tr><td style="background:linear-gradient(135deg, #FFF8F0 0%, #FFF3E6 100%);border-radius:12px;border-left:4px solid {P['amber_accent']};padding:{S['lg']}px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr><td style="padding-bottom:{S['sm']}px;">
<span style="font-size:14px;font-weight:700;color:{P['text_primary']};">💡 月度舆情洞察</span>
<span style="font-size:10px;color:{P['text_tertiary']};margin-left:6px;">AI · 仅供参考</span>
</td></tr>
<tr><td style="font-size:12px;color:{P['text_primary']};line-height:1.9;">
{ai}
</td></tr>
</table>
</td></tr></table>"""

    # ═══════ 品牌曝光卡片 ═══════
    brand_cards = ''
    max_cnt = max((b.get('count', b.get('total_appears', 0)) for b in brands), default=1)
    medals = ['🥇', '🥈', '🥉']

    for i, b in enumerate(brands):
        brand_name = b['brand']
        bc = brand_color(brand_name)
        cnt = b.get('count', b.get('total_appears', 0))
        events = b.get('event_count', len(b.get('items', [])))
        pct = int(cnt / max_cnt * 100) if max_cnt > 0 else 0
        medal = medals[i] if i < 3 else f'{i+1}'

        # 热搜标签
        items = b.get('items', [])
        tags_html = ''
        for it in items[:8]:
            kw = it.get('keyword', it.get('title', ''))
            if not kw:
                continue
            url = f"https://s.weibo.com/weibo?q={quote(kw)}"
            count = it.get('appear_count', 1)
            count_badge = f'<sup style="font-size:9px;color:{P["text_tertiary"]};">×{count}</sup>' if count > 1 else ''
            tags_html += (
                f'<a href="{url}" target="_blank" '
                f'style="display:inline-block;background:#F0F0F3;color:{P["text_primary"]};'
                f'border-radius:16px;padding:4px 12px;margin:3px 5px 3px 0;'
                f'font-size:11px;text-decoration:none;line-height:1.4;'
                f'border:1px solid #E5E5EA;">'
                f'{kw}{count_badge}</a>'
            )

        indicator_bg = ''
        if i == 0:
            indicator_bg = 'linear-gradient(90deg, #FFD700 0%, #FFA500 100%)'
        elif i == 1:
            indicator_bg = 'linear-gradient(90deg, #C0C0C0 0%, #A8A8A8 100%)'
        elif i == 2:
            indicator_bg = 'linear-gradient(90deg, #CD7F32 0%, #A0522D 100%)'
        else:
            indicator_bg = f'{bc}'

        brand_cards += f"""
<tr><td style="padding:6px 0;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{P['surface']};border-radius:10px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,0.04);{'border:2px solid ' + bc if i < 3 else ''};">
<tr>
<td style="width:4px;background:{indicator_bg};font-size:0;" rowspan="3">&nbsp;</td>
<td style="padding:10px 14px 4px;vertical-align:top;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr>
<td style="vertical-align:middle;">
<span style="font-size:22px;margin-right:6px;vertical-align:middle;">{medal}</span>
<span style="font-size:{'15' if i < 3 else '14'}px;font-weight:700;color:{bc};vertical-align:middle;">{brand_name}</span>
</td>
<td align="right" style="vertical-align:middle;">
<table role="presentation" cellpadding="0" cellspacing="0">
<tr>
<td style="text-align:center;padding:0 10px;border-right:1px solid {P['divider']};">
<div style="font-size:20px;font-weight:800;color:{P['text_primary']};">{cnt}</div>
<div style="font-size:9px;color:{P['text_tertiary']};">出现次数</div>
</td>
<td style="text-align:center;padding:0 10px;">
<div style="font-size:20px;font-weight:800;color:{bc};">{events}</div>
<div style="font-size:9px;color:{P['text_tertiary']};">事件数</div>
</td>
</tr>
</table>
</td>
</tr>
</table>
</td>
</tr>
<tr>
<td style="padding:4px 14px 4px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr>
<td style="background:#F0F0F3;border-radius:4px;height:6px;width:100%;font-size:0;">
<td style="background:{bc};border-radius:4px;height:6px;width:{pct}%;font-size:0;">&nbsp;</td>
<td style="width:{100-pct}%;font-size:0;"></td>
</td>
</tr>
</table>
</td>
</tr>
<tr>
<td style="padding:4px 14px 10px;line-height:1.8;">
{tags_html if tags_html else '<span style="font-size:11px;color:' + P['text_tertiary'] + ';">本月暂未监测到相关热搜</span>'}
</td>
</tr>
</table>
</td></tr>"""

    # ═══════ 组装 ═══════
    body = stats_card + ai_card + f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:{S['sm']}px;">
<tr><td style="padding-bottom:{S['sm']}px;">
<span style="font-size:15px;font-weight:700;color:{P['text_primary']};">🏆 品牌热搜排行榜</span>
</td></tr>
</table>
{brand_cards}
"""

    return email_shell(
        title=f'🔥 微博热搜 · 月度报告 {label}',
        accent_color=P['amber_accent'],
        body_content=body,
        generated_at=gen,
    )
