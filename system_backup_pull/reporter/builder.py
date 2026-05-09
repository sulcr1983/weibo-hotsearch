"""报告构建器：日报/周报/月报数据组装 + 事件去重合并"""
import asyncio
import re
from datetime import datetime, timedelta
from typing import List

from storage.database import Database
from processor.classifier import classify_dimension
from v2.logger import get_logger
from processor.brand_matcher import normalize_brand
from processor.brand_matcher import strip_html

logger = get_logger('builder')

_TITLE_KW_RE = re.compile(r'[\d.]+万|元|起售|售价|万元|版|款|型')
_BRIEF_NEWS_RE = re.compile(r'^\d{1,2}点\d{0,2}[^\s]*?丨|^《[^》]+》\d+版|^【[^】]+】')


def _is_brief_news(title: str) -> bool:
    """判断是否为快讯类新闻（如36氪/虎嗅早报格式）：标题含｜或时间+媒体格式"""
    if not title:
        return False
    if '丨' in title or '｜' in title:
        return True
    if _BRIEF_NEWS_RE.match(title):
        return True
    segments = title.split('；')
    if len(segments) >= 3:
        return True
    return False


def _title_core(title: str) -> str:
    """提取标题核心词用于去重：去数字去价格去修饰"""
    t = _TITLE_KW_RE.sub('', title)
    t = re.sub(r'\s+', '', t)
    return t[:20]


def _merge_by_event(articles: List[dict]) -> List[dict]:
    if not articles:
        return articles
    # 第一轮：event_id 分组
    groups: dict[str, list] = {}
    solo = []
    for a in articles:
        eid = a.get('event_id', '')
        if eid:
            groups.setdefault(eid, []).append(a)
        else:
            solo.append(a)

    # 第二轮：标题相似度兜底（同一品牌下标题核心词相同 → 合并）
    brand_title_map: dict[str, dict[str, list]] = {}
    for eid, group in groups.items():
        brand = group[0].get('brand', '')
        tc = _title_core(group[0].get('title', ''))
        if brand and tc:
            brand_title_map.setdefault(brand, {}).setdefault(tc, []).append(eid)

    merged_eids = set()
    for brand, tmap in brand_title_map.items():
        for tc, eids in tmap.items():
            if len(eids) <= 1:
                continue
            # 合并同标题核心的多个event
            first = eids[0]
            for dup in eids[1:]:
                groups[first].extend(groups[dup])
                merged_eids.add(dup)

    for dup in merged_eids:
        del groups[dup]

    merged = []
    for eid, group in groups.items():
        if len(group) == 1:
            merged.append(group[0])
            continue
        group.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        best = dict(group[0])
        times = sorted(set(a.get('created_at', '')[:16] for a in group), reverse=True)
        sources = sorted(set(a.get('source', '') for a in group if a.get('source')))
        urls = set(a.get('url', '') for a in group)
        best['merged_times'] = times
        best['merged_sources'] = sources
        best['merged_urls'] = list(urls)
        best['is_merged'] = True
        if len(sources) > 1:
            best['source'] = '、'.join(sources[:3]) + (f'等{len(sources)}个来源' if len(sources) > 3 else '')
        if len(times) > 1:
            best['created_at'] = f"{times[-1][:10]} {times[-1][11:16]}~{times[0][11:16]}"
        merged.append(best)
    merged.extend(solo)
    merged.sort(key=lambda x: str(x.get('created_at', '')).replace('~', ' '), reverse=True)
    return merged


class ReportBuilder:
    def __init__(self, db: Database):
        self.db = db

    async def build_daily(self) -> dict:
        date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        news = await self.db.get_articles(date=date)
        weibo = await self.db.get_weibo_events(date=date, status=None)
        news = _merge_by_event(news)
        # 日报：score>=65 且有维度分类；不足则从 score>=35 补充
        strong = [n for n in news if n.get('score', 0) >= 65 and classify_dimension(n.get('title', ''), n.get('content', '') or '')]
        strong.sort(key=lambda x: x.get('score', 0), reverse=True)
        if len(strong) < 3:
            weak = [
                n for n in news
                if n.get('score', 0) >= 35
                and classify_dimension(n.get('title', ''), n.get('content', '') or '')
                and n not in strong
            ]
            weak.sort(key=lambda x: x.get('score', 0), reverse=True)
            strong.extend(weak[:8 - len(strong)])
        for n in strong:
            clean_content = strip_html(n.get('content', '') or '')
            n['summary'] = clean_content[:80].strip() if clean_content else ''
        return {'date': date, 'weibo': weibo, 'news': strong, 'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M')}

    async def build_weekly(self) -> dict:
        ws = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        we = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        articles = await self.db.get_articles(hours=24 * 7)
        # 周报：score>=35，排除快讯类新闻
        articles = [a for a in articles if not _is_brief_news(a.get('title', '')) and a.get('score', 0) >= 35]
        articles = _merge_by_event(articles)
        by_brand: dict[str, dict[str, list]] = {}
        total = 0
        for a in articles:
            brand = a.get('brand', '')
            if not brand:
                continue
            dim = classify_dimension(a.get('title', ''), a.get('content', '') or '')
            if not dim:
                continue
            by_brand.setdefault(brand, {}).setdefault(dim, [])
            summary = (strip_html(a.get('content', '') or '') or '')[:100].strip()
            item = {'title': a['title'], 'summary': summary, 'content': a.get('content', '')[:200], 'url': a.get('url', ''), 'created_at': a.get('created_at', '')}
            if a.get('is_merged'):
                ms = a.get('merged_sources', [])
                mt = a.get('merged_times', [])
                item['source'] = f"来自{'、'.join(ms[:3])}" + (f"等{len(ms)}个来源" if len(ms) > 3 else '') + (f" | 首现 {mt[-1]}" if mt else '')
                item['urls'] = a.get('merged_urls', [])
            else:
                item['source'] = a.get('source', '')
                item['urls'] = [a.get('url', '')]
            by_brand[brand][dim].append(item)
            total += 1
        for brand in list(by_brand):
            dims = by_brand[brand]
            all_items = [(dn, it) for dn, items in dims.items() for it in items]
            if len(all_items) > 10:
                all_items = all_items[:10]
            trimmed: dict[str, list] = {}
            for dn, it in all_items:
                trimmed.setdefault(dn, []).append(it)
            by_brand[brand] = trimmed
        return {'week_start': ws, 'week_end': we, 'by_brand': by_brand, 'total_items': total, 'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M')}

    async def build_monthly(self) -> dict:
        now = datetime.now()
        if now.month == 1:
            ym = f"{now.year - 1}-12"
            label = f"{now.year - 1}年12月"
        else:
            ym = f"{now.year}-{now.month - 1:02d}"
            label = f"{now.year}年{now.month - 1}月"
        rows = await self.db.get_weibo_monthly(ym)
        stats = await self.db.get_weibo_brand_stats(ym)

        # 品牌维度：事件数 + 总出现次数
        brand_summary = []
        for s in stats:
            brand_items = []
            for r in rows:
                if r['brand'] != s['brand']:
                    continue
                first = r['first_seen_at'][:10] if r['first_seen_at'] else ''
                last = r['last_seen_at'][:10] if r['last_seen_at'] else ''
                duration = f"{first}~{last}" if first != last else first
                brand_items.append({
                    'keyword': r['keyword'],
                    'appear_count': r['appear_count'],
                    'duration': duration,
                    'status': r['status'],
                })
            brand_summary.append({
                'brand': s['brand'],
                'event_count': s['event_count'],
                'count': s['total_appears'],
                'items': brand_items[:15],
            })

        total_events = sum(s['event_count'] for s in stats)
        total_appears = sum(s['total_appears'] for s in stats)
        return {
            'year_month': ym, 'label': label,
            'brands': brand_summary,
            'total_events': total_events,
            'total_appears': total_appears,
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
        }





