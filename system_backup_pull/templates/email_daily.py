"""邮件日报模板 v6 — 苹果简约科技风 · 微博紧凑表格 + 新闻四维度分类"""
from typing import List
from collections import OrderedDict
from urllib.parse import quote

from templates.design_tokens import PALETTE, SPACING, brand_badge_html


def _group_by_brand(items: List[dict], brand_key: str = "brand") -> OrderedDict:
    grouped = OrderedDict()
    for item in items:
        brand = item.get(brand_key, '') or '其他'
        if brand not in grouped:
            grouped[brand] = []
        grouped[brand].append(item)
    return grouped


def _group_by_category(items: List[dict]) -> OrderedDict:
    categories = OrderedDict([
        ('🎨 创意营销/公关事件', []),
        ('📤 投放与合作', []),
        ('🌟 明星与IP合作', []),
        ('⚙️ 核心活动', []),
        ('📰 其他', []),
    ])

    keywords = {
        '🎨 创意营销/公关事件': [
            '跨界联名', '官方声明', '公关', '危机', '声明', '回应',
            '热搜', '互动营销', '促销联动', '降价', '优惠', '补贴',
            '创意营销', '用户活动', '社区活动', '品牌日', '体验日',
            '粉丝节', '周年庆', '打卡', '挑战赛', '快闪', '抽奖',
        ],
        '📤 投放与合作': [
            'KOL', '商单', '开屏投放', '商圈大屏', '快闪店', '垂媒合作',
            '付费投放', '线下投放', '场景投放', '媒体合作',
            '签约', '战略合作', '合作协议', '达成合作', '签署', '携手',
            '生态合作', '渠道合作', '共建', '入驻', '合资', '入股',
            '出海', '海外市场', '全球化', '出口', '海外工厂',
            '海外发布', '欧洲上市', '东南亚', '中东', '拉美',
            '投资', '供应链', '采购', '供应商', '扩建', '产能',
            '融资', '估值', '充电网络', '充电联盟', '超充网络', '换电网络',
        ],
        '🌟 明星与IP合作': [
            '品牌代言人', '明星代言', '官宣代言', '品牌大使', '品牌挚友',
            '品牌代言', '新代言人', '全球代言人',
            '综艺植入', 'IP联名', 'IP 联名', '联名款', '联名', '合作款',
            '限定款', 'IP合作', '赛事赞助', '冠名', '赞助', '独家冠名',
        ],
        '⚙️ 核心活动': [
            '新车上市', '技术发布会', '品牌主题', '发布会', '车展',
            '核心技术', '战略发布', '品牌活动', '全球首发', '上市发布会',
            '交付', '量产', '下线', '投产', '预售', '亮相',
            '发布', '首发', '上市', '开售', '试驾', '路试',
            'OTA升级', '智驾', '自动驾驶', '自研', '专利', '技术突破',
            '财报', '业绩', '营收', '交付量', '订单量', '销量',
            '毛利率', '工厂', '基地', '超级工厂', '制造', '生产线',
            '充电站', '充电桩', '换电站', '固态电池', '安全',
            '市场份额', '配置', '智能化', '座舱', '底盘', '悬架',
        ],
    }

    for item in items:
        title = item.get('title', '') + ' ' + (item.get('content', '') or '')[:100]
        matched = False
        for cat, keys in keywords.items():
            for key in keys:
                if key in title:
                    categories[cat].append(item)
                    matched = True
                    break
            if matched:
                break
        if not matched:
            categories['📰 其他'].append(item)
    return categories


def _weibo_compact_table(weibo: List[dict], P: dict, S: dict) -> str:
    if not weibo:
        return ''

    rows = ''
    for idx, item in enumerate(weibo[:10]):
        keyword = item.get('keyword', '')
        brand = item.get('brand', '')
        heat = item.get('heat', 0)
        label = item.get('label', '')
        first_seen = item.get('first_seen_at', '')[11:16] if item.get('first_seen_at') else ''

        weibo_url = f"https://s.weibo.com/weibo?q={quote(keyword)}"
        heat_str = f"{heat:,}" if heat > 0 else '—'

        label_styles = {
            '爆': 'bg:#FF3B30;color:#FFF',
            '沸': 'bg:#FF3B30;color:#FFF',
            '热': 'bg:#FF6B35;color:#FFF',
            '新': 'bg:#34C759;color:#FFF',
        }
        ls = label_styles.get(label, 'bg:#AEAEB2;color:#FFF')
        label_tag = f'<span style="{ls};padding:1px 6px;border-radius:3px;font-size:10px;font-weight:600;">{label}</span>' if label else '—'

        bg = '#FAFAFA' if idx % 2 == 0 else '#FFF'
        rows += f"""
<tr style="background:{bg};">
<td style="padding:6px 10px;text-align:center;width:32px;">
<span style="font-size:11px;font-weight:600;color:{'#0071E3' if idx < 3 else '#AEAEB2'};">{idx+1}</span>
</td>
<td style="padding:6px 8px;">
<a href="{weibo_url}" target="_blank" style="font-size:13px;color:#1D1D1F;font-weight:600;text-decoration:none;line-height:1.3;">{keyword}</a>
</td>
<td style="padding:6px 6px;text-align:center;white-space:nowrap;">{label_tag}</td>
<td style="padding:6px 8px;white-space:nowrap;">
<span style="font-size:11px;font-weight:600;color:{P['text_secondary']};">{brand}</span>
</td>
<td style="padding:6px 6px;text-align:right;white-space:nowrap;">
<span style="font-size:12px;font-weight:700;color:{P['red_accent']};">{heat_str}</span>
</td>
<td style="padding:6px 10px;text-align:right;white-space:nowrap;">
<span style="font-size:11px;color:{P['text_tertiary']};">{first_seen}</span>
</td>
</tr>"""

    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:{S['lg']}px;">
<tr><td style="padding-bottom:{S['sm']}px;">
<span style="font-size:15px;font-weight:700;color:{P['text_primary']};">
🔥 微博热搜
<span style="font-size:12px;color:{P['text_tertiary']};margin-left:6px;">{len(weibo)}条</span>
</span>
</td></tr>
<tr><td style="background:{P['surface']};border-radius:10px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.04);">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr style="background:{P['navy_dark']};">
<td style="padding:8px 10px;text-align:center;width:32px;">
<span style="font-size:10px;font-weight:600;color:rgba(255,255,255,0.6);">#</span>
</td>
<td style="padding:8px 8px;">
<span style="font-size:10px;font-weight:600;color:rgba(255,255,255,0.6);">热搜词</span>
</td>
<td style="padding:8px 6px;text-align:center;width:50px;">
<span style="font-size:10px;font-weight:600;color:rgba(255,255,255,0.6);">标签</span>
</td>
<td style="padding:8px 8px;width:70px;">
<span style="font-size:10px;font-weight:600;color:rgba(255,255,255,0.6);">品牌</span>
</td>
<td style="padding:8px 6px;text-align:right;width:56px;">
<span style="font-size:10px;font-weight:600;color:rgba(255,255,255,0.6);">热度</span>
</td>
<td style="padding:8px 10px;text-align:right;width:48px;">
<span style="font-size:10px;font-weight:600;color:rgba(255,255,255,0.6);">时间</span>
</td>
</tr>
{rows}
</table>
</td></tr>
</table>"""


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
<body style="margin:0;padding:0;background:{P['bg_primary']};font-family:'PingFang SC','Microsoft YaHei','Helvetica Neue',sans-serif;-webkit-font-smoothing:antialiased;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{P['bg_primary']};">
<tr><td align="center" style="padding:{S['lg']}px {S['sm']}px;">

<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;border-radius:14px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.06);">

<tr>
<td style="background:linear-gradient(135deg,{P['accent_gradient_from']} 0%,{P['accent_gradient_to']} 100%);padding:{S['lg']}px {S['xl']}px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr>
<td style="vertical-align:middle;">
<h1 style="margin:0;font-size:19px;font-weight:700;color:{P['white']};letter-spacing:0.3px;">🚗 汽车行业舆情 · 日报</h1>
</td>
<td align="right" style="vertical-align:middle;">
<span style="font-size:12px;color:rgba(255,255,255,0.55);">{date_str}</span>
</td>
</tr>
</table>
</td>
</tr>

<tr><td style="background:{P['blue_link']};height:3px;font-size:0;">&nbsp;</td></tr>

<tr><td style="background:{P['surface']};padding:{S['lg']}px {S['xl']}px {S['sm']}px;">

<!-- 统计概览 -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:{S['lg']}px;">
<tr><td style="background:{P['surface_hover']};border-radius:10px;padding:{S['sm']}px 0;">
<table role="presentation" cellpadding="0" cellspacing="0" align="center">
<tr>
<td style="padding:6px 24px;text-align:center;border-right:1px solid {P['divider']};">
<div style="font-size:22px;font-weight:700;color:{P['text_primary']};">{total}</div>
<div style="font-size:10px;color:{P['text_tertiary']};">📋 总计监测</div>
</td>
<td style="padding:6px 24px;text-align:center;border-right:1px solid {P['divider']};">
<div style="font-size:22px;font-weight:700;color:{P['blue_link']};">{n_count}</div>
<div style="font-size:10px;color:{P['text_tertiary']};">📰 新闻热点</div>
</td>
<td style="padding:6px 24px;text-align:center;">
<div style="font-size:22px;font-weight:700;color:{P['red_accent']};">{w_count}</div>
<div style="font-size:10px;color:{P['text_tertiary']};">🔥 微博热搜</div>
</td>
</tr>
</table>
</td></tr>
</table>"""

    has_content = False

    # ── 微博热搜 — 紧凑表格 ──
    if weibo:
        has_content = True
        html += _weibo_compact_table(weibo, P, S)

    # ── 新闻热点 — 四维度分类 ──
    if news:
        if has_content:
            html += f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td style="height:{S["md"]}px;"></td></tr></table>'

        has_content = True
        grouped = _group_by_category(news)

        cat_config = {
            '🎨 创意营销/公关事件': {'color': '#FF6B35', 'bg': '#FFF5F0'},
            '📤 投放与合作': {'color': '#0071E3', 'bg': '#F0F6FF'},
            '🌟 明星与IP合作': {'color': '#AF52DE', 'bg': '#F8F0FF'},
            '⚙️ 核心活动': {'color': '#34C759', 'bg': '#F0FFF4'},
            '📰 其他': {'color': '#AEAEB2', 'bg': '#F2F2F4'},
        }

        for cat, items in grouped.items():
            if not items:
                continue

            cfg = cat_config.get(cat, cat_config['📰 其他'])
            color = cfg['color']
            bg = cfg['bg']

            html += f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:{S['md']}px;">
<tr><td style="padding-bottom:{S['sm']}px;">
<span style="font-size:14px;font-weight:700;color:{color};">{cat}</span>
<span style="font-size:11px;color:{P['text_tertiary']};margin-left:6px;">{len(items)}</span>
</td></tr>"""

            by_brand = _group_by_brand(items, 'brand')
            for brand, brand_items in by_brand.items():
                badge = brand_badge_html(brand, "large")
                html += f'<tr><td style="padding:2px 0 4px;">{badge}</td></tr>'

                for item in brand_items[:5]:
                    time_part = (item.get('published', '') or item.get('created_at', '')[11:16]) if item.get('published') or item.get('created_at') else ''
                    title = item.get('title', '')
                    link = item.get('url', '')
                    source = item.get('source', '')
                    summary = (item.get('summary', '') or item.get('content', '') or '')[:100].strip()

                    desc_html = (
                        f'<div style="font-size:12px;color:{P["text_secondary"]};margin-top:3px;line-height:1.5;overflow:hidden;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;">{summary}</div>'
                        if summary else ''
                    )
                    meta_parts = []
                    if source:
                        meta_parts.append(f'<span style="font-size:10px;color:{P["text_tertiary"]};">{source}</span>')
                    if time_part:
                        meta_parts.append(f'<span style="font-size:10px;color:{P["text_tertiary"]};">{time_part}</span>')
                    meta = ' · '.join(meta_parts)

                    html += f"""
<tr><td style="padding:4px 0 4px 8px;border-bottom:1px solid {P['divider']};">
<a href="{link}" target="_blank" style="font-size:13px;color:{P['text_primary']};text-decoration:none;font-weight:600;line-height:1.5;">{title}</a>
{desc_html}
<div style="margin-top:2px;">{meta}</div>
</td></tr>"""
            html += "</table>"

    if not has_content:
        html += f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr><td style="padding:{S['xxl']}px 0;text-align:center;">
<div style="font-size:40px;margin-bottom:{S['sm']}px;">📭</div>
<div style="font-size:14px;color:{P['text_secondary']};font-weight:500;">昨日暂无关注的品牌舆情</div>
<div style="font-size:11px;color:{P['text_tertiary']};margin-top:4px;">系统持续监测中，有动态将第一时间推送</div>
</td></tr>
</table>"""

    html += f"""
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