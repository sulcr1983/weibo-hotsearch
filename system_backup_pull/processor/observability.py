"""可观测性模块 V5.1 — traces用deque限制内存 + 去冗余正则"""
import json
import os
import re
import uuid
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

from v2.logger import get_logger

logger = get_logger('observe')

_SYSTEM_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _SYSTEM_DIR.parent
_LOG_DIR = _PROJECT_ROOT / 'logs'
_FAIL_DIR = _LOG_DIR / 'snapshots'

MAX_TRACES = 1000


def new_trace_id() -> str:
    return uuid.uuid4().hex[:8]


class DropReason:
    NO_BRAND_MATCH = 'no_brand_match'
    DIGEST = 'digest'
    UGC = 'ugc'
    OPINION = 'opinion'
    SCORE_DISCARD = 'score_discard'
    NO_DIMENSION = 'no_dimension_match'
    FINANCIAL_BRIEF = 'financial_filter'
    DUPLICATE = 'duplicate'
    INVALID_HTML = 'invalid_html'
    CAPTCHA_PAGE = 'captcha_page'
    FORBIDDEN_PAGE = 'forbidden_page'
    EMPTY_CONTENT = 'empty_content'
    PARSE_FAILED = 'parse_failed'
    INVALID_DATA = 'invalid_data'
    LLM_FAILED = 'llm_failed'

    LABELS = {
        'no_brand_match': '品牌未命中',
        'digest': '汇总/晨报过滤',
        'ugc': 'UGC/自媒体过滤',
        'opinion': '观点评论过滤',
        'score_discard': '评分过低(<35)',
        'no_dimension_match': '四维度未命中',
        'financial_filter': '金融快讯过滤',
        'duplicate': 'URL去重',
        'invalid_html': 'HTML无效',
        'captcha_page': '验证码页面',
        'forbidden_page': '403/禁止访问',
        'empty_content': '内容为空',
        'parse_failed': '解析失败',
        'invalid_data': '数据格式无效',
        'llm_failed': 'LLM分类失败',
    }


class FunnelStats:
    def __init__(self):
        self.reset()

    def reset(self):
        self.rss_sources = 0
        self.web_sources = 0
        self.auto_sources = 0
        self.pw_sources = 0
        self.rss_success = 0
        self.web_success = 0
        self.auto_success = 0
        self.pw_success = 0
        self.raw_captured = 0
        self.brand_hit = 0
        self.dimension_pass = 0
        self.financial_filtered = 0
        self.dedup_filtered = 0
        self.digest_filtered = 0
        self.ugc_filtered = 0
        self.opinion_filtered = 0
        self.score_discarded = 0
        self.db_inserted = 0
        self.errors = 0
        self.drop_counts: Dict[str, int] = {}
        self.traces: deque = deque(maxlen=MAX_TRACES)

    def count_drop(self, reason: str):
        self.drop_counts[reason] = self.drop_counts.get(reason, 0) + 1

    def record_trace(self, trace_id: str, stage: str, detail: dict = None):
        entry = {'trace_id': trace_id, 'stages': [stage]}
        if detail:
            entry['detail'] = detail
        self.traces.append(entry)

    def summary(self) -> dict:
        top_drops = sorted(self.drop_counts.items(), key=lambda x: -x[1])
        return {
            'sources': {
                'rss': f'{self.rss_success}/{self.rss_sources}',
                'web': f'{self.web_success}/{self.web_sources}',
                'auto': f'{self.auto_success}/{self.auto_sources}',
                'playwright': f'{self.pw_success}/{self.pw_sources}',
            },
            'pipeline': {
                'raw_captured': self.raw_captured,
                'brand_hit': self.brand_hit,
                'dimension_pass': self.dimension_pass,
                'financial_filtered': self.financial_filtered,
                'digest_filtered': self.digest_filtered,
                'ugc_filtered': self.ugc_filtered,
                'opinion_filtered': self.opinion_filtered,
                'score_discarded': self.score_discarded,
                'dedup_filtered': self.dedup_filtered,
                'db_inserted': self.db_inserted,
                'errors': self.errors,
            },
            'top_drop_reasons': [{'reason': DropReason.LABELS.get(r, r), 'count': c}
                                 for r, c in top_drops[:5]],
            'success_rate': f'{self.db_inserted}/{self.raw_captured}' if self.raw_captured else '0/0',
        }

    def log_report(self):
        s = self.summary()
        p = s['pipeline']
        logger.info(
            f"[采集统计]\n"
            f"  RSS源数量: {s['sources']['rss']}\n"
            f"  Web源数量: {s['sources']['web']}\n"
            f"  垂媒源数量: {s['sources']['auto']}\n"
            f"  PW源数量: {s['sources']['playwright']}\n"
            f"\n"
            f"  原始抓取: {p['raw_captured']}\n"
            f"  品牌命中: {p['brand_hit']}\n"
            f"  四维度通过: {p['dimension_pass']}\n"
            f"  金融过滤后: {p['financial_filtered']}条被过滤\n"
            f"  去重后: {p['dedup_filtered']}条被去重\n"
            f"  最终入库: {p['db_inserted']}\n"
            f"  处理错误: {p['errors']}\n"
            f"\n"
            f"  TOP过滤原因:\n" +
            ''.join(f"    - {d['reason']}: {d['count']}\n" for d in s['top_drop_reasons'])
        )


_funnel = FunnelStats()


def get_funnel() -> FunnelStats:
    return _funnel


# ── HTML 有效性检测 ──

CAPTCHA_PATTERNS = [
    re.compile(r'验证码', re.IGNORECASE),
    re.compile(r'captcha', re.IGNORECASE),
    re.compile(r'点击进行验证', re.IGNORECASE),
    re.compile(r'请完成安全验证', re.IGNORECASE),
    re.compile(r'人机验证', re.IGNORECASE),
    re.compile(r'滑块验证', re.IGNORECASE),
    re.compile(r'spider', re.IGNORECASE),
]

LOGIN_PATTERNS = [
    re.compile(r'请先登录', re.IGNORECASE),
    re.compile(r'立即登录', re.IGNORECASE),
    re.compile(r'登录/注册', re.IGNORECASE),
    re.compile(r'login', re.IGNORECASE),
    re.compile(r'请先登入', re.IGNORECASE),
]

FORBIDDEN_PATTERNS = [
    re.compile(r'403 Forbidden', re.IGNORECASE),
    re.compile(r'Access Denied', re.IGNORECASE),
    re.compile(r'访问被拒', re.IGNORECASE),
    re.compile(r'禁止访问', re.IGNORECASE),
    re.compile(r'无权限访问', re.IGNORECASE),
]

CLOUDFLARE_PATTERNS = [
    re.compile(r'Cloudflare', re.IGNORECASE),
    re.compile(r'Checking your browser', re.IGNORECASE),
    re.compile(r'DDoS protection', re.IGNORECASE),
    re.compile(r'cf-browser-verification', re.IGNORECASE),
    re.compile(r'cf_chl', re.IGNORECASE),
]

MIN_HTML_LENGTH = 200


def check_html_validity(html: str, source_name: str = '') -> dict:
    if not html:
        return {'valid': False, 'issues': ['空响应'], 'issue_type': 'empty_content'}
    issues = []
    issue_type = None
    if len(html) < MIN_HTML_LENGTH:
        issues.append(f'HTML过短({len(html)}字节)')
    for p in CAPTCHA_PATTERNS:
        if p.search(html):
            issues.append(f'疑似验证码页面: {p.pattern}')
            issue_type = 'captcha_page'
            break
    for p in LOGIN_PATTERNS:
        if p.search(html):
            issues.append(f'疑似登录页面: {p.pattern}')
            if not issue_type:
                issue_type = 'forbidden_page'
            break
    for p in FORBIDDEN_PATTERNS:
        if p.search(html):
            issues.append(f'疑似禁止访问: {p.pattern}')
            issue_type = 'forbidden_page'
            break
    for p in CLOUDFLARE_PATTERNS:
        if p.search(html):
            issues.append(f'疑似Cloudflare防护: {p.pattern}')
            if not issue_type:
                issue_type = 'forbidden_page'
            break
    valid = len(issues) == 0
    return {'valid': valid, 'issues': issues, 'issue_type': issue_type}


def save_fail_snapshot(html: str, source_name: str, issue: str, prefix: str = 'fail') -> Optional[str]:
    if not html:
        return None
    try:
        _FAIL_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_name = re.sub(r'[^\w]', '_', source_name)[:30]
        fname = f'{prefix}_{safe_name}_{ts}.html'
        fpath = _FAIL_DIR / fname
        snippet = html[:5000]
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(f'<!-- issue: {issue} -->\n')
            f.write(f'<!-- source: {source_name} -->\n')
            f.write(f'<!-- time: {ts} -->\n')
            f.write(f'<!-- saved_len: {min(len(html), 5000)} / original: {len(html)} -->\n')
            f.write(snippet)
        logger.info(f"失败快照已保存: {fpath}")
        return str(fpath)
    except Exception as e:
        logger.error(f"保存快照失败: {e}")
        return None


def log_trace(trace_id: str, stage: str, title: str = '', detail: str = ''):
    funnel = get_funnel()
    detail_dict = {}
    if title:
        detail_dict['title'] = title[:60]
    if detail:
        detail_dict['detail'] = detail[:200]
    funnel.record_trace(trace_id, stage, detail_dict)
    title_preview = title[:40] if title else ''
    logger.debug(f"[{stage}] trace={trace_id} {title_preview} {detail}")
