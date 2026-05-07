"""飞书卡片模板 v2 — 优化视觉层级，去除空格缩进，利用原生元素"""
import re
from typing import List
from urllib.parse import quote

from templates.design_tokens import (
    PALETTE, brand_badge_feishu, brand_color, DIMENSION_ICONS,
)
from processor.brand_matcher import strip_html
from v2.constants import BRAND_PATTERNS

_VALID_URL_RE = re.compile(r'^https?://(?!.*mock)(?!.*localhost)[^\s]+$')
_SAFE_CHARS = ':/?#[]@!$&\'()*+,;=%'


def _encode_url(url: str) -> str:
    """URL编码含中文/特殊字符的链接，防止飞书lark_md解析失败"""
    if not url:
        return ''
    try:
        return quote(url, safe=_SAFE_CHARS)
    except Exception:
        return url


def _valid_url(url: str) -> str:
    if not url:
        return ''
    clean = url.strip()
    if not _VALID_URL_RE.match(clean):
        return ''
    return _encode_url(clean)


def render_daily_feishu(
    weibo: List[dict], news: List[dict], date_str: str, generated_at: str
) -> List[dict]:
    P = PALETTE
    elements: List[dict] = []
    w_count = len(weibo)
    n_count = len(news)

    elements.append({
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": (
                f"**昨日汽车行业舆情热点新闻**\n"
                f"<font color=\"{P['text_tertiary']}\">{date_str}</font>"
            )
        }
    })

    elements.append({"tag": "hr"})

    # 数据统计行
    elements.append({
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": (
                f"📊 总计监测 **{w_count + n_count}** 条　|　"
                f"📰 新闻 <font color=\"{P['amber_accent']}\">**{n_count}**</font> 条　|　"
                f"🔥 热搜 <font color=\"#E74C3C\">**{w_count}**</font> 条"
            )
        }
    })
    elements.append({"tag": "hr"})

    if weibo:
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**🔥 微博热搜 · {len(weibo)}条**"
            }
        })
        for item in weibo[:8]:
            brand = item.get('brand', '')
            keyword = item.get('keyword', '')
            raw_link = item.get('link', '')
            link = _valid_url(raw_link)
            label = item.get('label', '')
            appear = item.get('appear_count', 1)
            brand_tag = brand_badge_feishu(brand) if brand else ''
            label_str = f'<font color="#FF4D4F">{label}</font>' if label in ('爆','热','新','沸','置顶') else label
            count_hint = f' 🕐×{appear}' if appear > 1 else ''
            if link:
                line = f"{brand_tag} **{keyword}** [🔗]({link}){count_hint}"
            else:
                line = f"{brand_tag} **{keyword}**{count_hint}"
            if label_str:
                line += f' {label_str}'
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": line}
            })
        elements.append({"tag": "hr"})

    if news:
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**📰 新闻热点 · {n_count}条**"
            }
        })
        # 按品牌分组 → 按维度分组
        from processor.classifier import classify_dimension
        brand_dim: dict[str, dict[str, list]] = {}
        for item in news:
            b = item.get('brand', '')
            if not b:
                continue
            d = classify_dimension(item.get('title', ''), item.get('content', '') or '')
            if not d:
                d = '其他'
            brand_dim.setdefault(b, {}).setdefault(d, []).append(item)

        all_brands = list(BRAND_PATTERNS.keys())
        for brand in all_brands:
            dims = brand_dim.get(brand, {})
            if not dims:
                continue
            brand_tag = brand_badge_feishu(brand)
            bc = brand_color(brand)
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"{brand_tag} <font color=\"{P['text_tertiary']}\">{sum(len(v) for v in dims.values())}条</font>"
                }
            })
            for dim_name, items in dims.items():
                if not items:
                    continue
                icon = DIMENSION_ICONS.get(dim_name, '')
                elements.append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**{icon} {dim_name}**"
                    }
                })
                for item in items:
                    title = item.get('title', '')
                    url = _valid_url(item.get('url', ''))
                    source = item.get('source', '')
                    time_part = item.get('created_at', '')[:16] if item.get('created_at') else ''
                    summary = item.get('summary', '')
                    if not summary:
                        summary = strip_html(item.get('content', '') or '')[:40].strip()
                    if url:
                        line = f"• [{title}]({url})"
                    else:
                        line = f"• {title}"
                    elements.append({
                        "tag": "div",
                        "text": {"tag": "lark_md", "content": line}
                    })
                    meta_parts = []
                    if summary:
                        meta_parts.append(summary)
                    if source:
                        meta_parts.append(source)
                    if time_part:
                        meta_parts.append(time_part)
                    elements.append({
                        "tag": "note",
                        "elements": [{"tag": "plain_text", "content": ' · '.join(meta_parts)}]
                    })
    else:
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"<font color=\"{P['text_tertiary']}\">📭 暂无新闻热点</font>"
            }
        })

    elements.append({"tag": "hr"})
    elements.append({
        "tag": "note",
        "elements": [{
            "tag": "plain_text",
            "content": f"生成时间：{generated_at} | 汽车行业舆情监控系统"
        }]
    })

    return elements


def render_monthly_feishu(report: dict) -> List[dict]:
    P = PALETTE
    elements: List[dict] = []
    label = report.get('label', '')
    brands = report.get('brands', [])
    total = report.get('total_appears', 0)
    ai = report.get('ai_summary', '')

    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": f"**📅 微博月度舆情报告 {label}**\n<font color=\"{P['text_tertiary']}\">共监测到 {total} 条汽车品牌热搜</font>"
        }
    })
    elements.append({"tag": "hr"})

    if ai:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**📊 AI月度总结**\n\n{ai}\n\n<font color=\"{P['text_tertiary']}\">—— AI生成 · 仅供参考</font>"}
        })
        elements.append({"tag": "hr"})

    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": "**📈 品牌曝光频次榜**"}
    })

    for i, b in enumerate(brands):
        bc = brand_color(b['brand'])
        bar = '█' * min(b.get('total_appears', b.get('count', 0)), 30)
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**{i + 1}.** <font color=\"{bc}\">**{b['brand']}**</font>  {bar} **{b.get('total_appears', b.get('count', 0))}次**"}
        })

    elements.append({"tag": "hr"})
    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": "**🔤 热搜词列表**"}
    })

    for b in brands:
        bc = brand_color(b['brand'])
        items = b.get('keywords', b.get('items', []))
        if not items:
            continue
        kw_list = '  '.join(
            f"<font color=\"{P['text_primary']}\">{it.get('keyword', it.get('title', ''))}</font>"
            f"<font color=\"{P['text_tertiary']}\">({(it.get('duration','') or it.get('date','') or '')[-5:]})</font>"
            for it in items[:12]
        )
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"<font color=\"{bc}\">**{b['brand']}**</font>：{kw_list}"}
        })

    elements.append({"tag": "hr"})
    elements.append({
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": f"生成时间：{report.get('generated_at','')} | 汽车行业舆情监控系统"}]
    })
    return elements


def render_weekly_feishu(
    week_start: str, week_end: str, ai_summary: str,
    by_brand: dict, total: int, generated_at: str,
) -> List[dict]:
    P = PALETTE
    elements: List[dict] = []

    wp = week_start[5:] if len(week_start) >= 10 else week_start
    we = week_end[5:] if len(week_end) >= 10 else week_end

    elements.append({
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": (
                f"**上周汽车行业10个品牌舆情汇总 {wp}-{we}**\n"
                f"<font color=\"{P['text_tertiary']}\">"
                f"{week_start} 至 {week_end} · 总计 {total} 条</font>"
            )
        }
    })
    elements.append({"tag": "hr"})

    # AI 总结
    if ai_summary:
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": (
                    f"**📊 上周核心洞察**\n\n"
                    f"{ai_summary}\n\n"
                    f"<font color=\"{P['text_tertiary']}\">"
                    f"—— AI 生成 · 仅供参考</font>"
                )
            }
        })
        elements.append({"tag": "hr"})

    elements.append({
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": f"**🚗 汽车行业周度热点资讯**"
        }
    })

    all_brands = list(BRAND_PATTERNS.keys())
    for brand in all_brands:
        dims = by_brand.get(brand, {})
        brand_tag = brand_badge_feishu(brand)
        brand_total = sum(len(items) for items in dims.values())
        bc = brand_color(brand)

        if not dims:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": (
                        f"{brand_tag} "
                        f"<font color=\"{P['text_tertiary']}\">"
                        f"本周暂无相关动态</font>"
                    )
                }
            })
            continue

        elements.append({"tag": "hr"})
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": (
                    f"{brand_tag} "
                    f"<font color=\"{P['text_tertiary']}\">"
                    f"{brand_total}条</font>"
                )
            }
        })

        brand_num = 0
        for dim_name, items in dims.items():
            if not items:
                continue
            icon = DIMENSION_ICONS.get(dim_name, '')
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**{icon} {dim_name}**"
                }
            })
            for item in items:
                brand_num += 1
                title = item.get('title', '')
                raw_url = item.get('url', '') or (item.get('urls', [''])[0] if item.get('urls') else '')
                url = _valid_url(raw_url)
                summary = item.get('summary', '')
                source = item.get('source', '')
                created = item.get('created_at', '')[:16]
                meta_parts = []
                if created:
                    meta_parts.append(created)
                if source:
                    meta_parts.append(source)
                meta = ' · '.join(meta_parts)
                if url:
                    content = f"**{brand_num}.** [{title}]({url})"
                else:
                    content = f"**{brand_num}.** {title}"
                if summary:
                    content += f"\n<font color=\"{P['text_secondary']}\">{summary}</font>"
                content += f"\n<font color=\"{P['text_tertiary']}\">{meta}</font>"
                elements.append({
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": content}
                })

    elements.append({"tag": "hr"})
    elements.append({
        "tag": "note",
        "elements": [{
            "tag": "plain_text",
            "content": f"生成时间：{generated_at} | 汽车行业舆情监控系统"
        }]
    })

    return elements
