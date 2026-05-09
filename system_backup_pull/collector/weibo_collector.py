"""微博热搜采集器 V5：多渠道降级 + 移动端UA + HTML兜底"""
from datetime import datetime
from typing import List, Optional, Dict

import aiohttp
import simhash
import re

from v2.logger import get_logger

logger = get_logger('weibo')

SIDE_API = 'https://weibo.com/ajax/side/hotSearch'
HTML_TOP = 'https://s.weibo.com/top/summary?cate=realtimehot'

# 移动端微博 UA 标识（关键——这是绕过 Forbidden 的核心）
WEIBO_UA = (
    'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) '
    'AppleWebKit/605.1.15 (KHTML, like Gecko) '
    'Mobile/15E148 Weibo (iPhone15,2)'
)

# 品牌别名字典
BRAND_DICT: Dict[str, list] = {
    "小米汽车": ["小米汽车", "小米SU7", "小米YU7", "小米SU"],
    "鸿蒙智行": ["鸿蒙智行", "问界", "智界", "尊界", "享界", "尚界"],
    "零跑汽车": ["零跑汽车", "零跑"],
    "理想汽车": ["理想汽车", "理想", "理想L", "理想MEGA", "理想i"],
    "蔚来汽车": ["蔚来汽车", "蔚来", "萤火虫", "乐道"],
    "极氪汽车": ["极氪汽车", "极氪", "极氪00"],
    "阿维塔": ["阿维塔"],
    "智己汽车": ["智己汽车", "智己"],
    "比亚迪": ["比亚迪", "仰望", "腾势", "方程豹"],
    "特斯拉": ["特斯拉", "Tesla", "Model Y", "Model 3", "Cybertruck"],
}

SIMHASH_THRESHOLD = 15


def _match_brand(text: str) -> Optional[str]:
    """品牌关键词匹配"""
    for brand, aliases in BRAND_DICT.items():
        for alias in sorted(aliases, key=lambda x: -len(x)):
            if alias in text:
                # 避免误匹配：确保不是更长的词的一部分
                idx = text.find(alias)
                if idx >= 0:
                    # 检查前后边界
                    before_ok = idx == 0 or not text[idx-1].isalnum() if idx > 0 else True
                    after = idx + len(alias)
                    after_ok = after >= len(text) or not text[after].isalnum() if after < len(text) else True
                    if before_ok and after_ok:
                        return brand
    return None


def _compute_simhash(keyword: str) -> str:
    if not keyword or len(keyword) < 4:
        return '0' * 16
    try:
        import jieba
        words = [w.strip() for w in jieba.cut(keyword) if len(w.strip()) >= 2]
        if not words:
            words = [keyword[:20]]
        s = simhash.Simhash(words)
        return format(s.value, '016x')
    except Exception:
        return '0' * 16


def _hamming_dist(hex1: str, hex2: str) -> int:
    try:
        return bin(int(hex1, 16) ^ int(hex2, 16)).count('1')
    except Exception:
        return 64


async def _fetch_api(session: aiohttp.ClientSession) -> Optional[dict]:
    """方案A：微博内部JSON API（移动端UA）"""
    headers = {
        'User-Agent': WEIBO_UA,
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://weibo.com/hot',
        'X-Requested-With': 'XMLHttpRequest',
    }
    try:
        async with session.get(SIDE_API, headers=headers, timeout=aiohttp.ClientTimeout(total=12)) as resp:
            if resp.status == 200:
                data = await resp.json()
                if isinstance(data, dict) and 'data' in data:
                    return data
            logger.warning(f"微博API HTTP {resp.status}")
            return None
    except Exception as e:
        logger.warning(f"微博API异常: {e}")
        return None


async def _fetch_html(session: aiohttp.ClientSession) -> List[dict]:
    """方案B：HTML直采 s.weibo.com/top/summary"""
    headers = {
        'User-Agent': WEIBO_UA,
        'Accept': 'text/html,application/xhtml+xml',
        'Referer': 'https://weibo.com/',
    }
    try:
        async with session.get(HTML_TOP, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                logger.warning(f"微博HTML HTTP {resp.status}")
                return []
            raw = await resp.read()
            # 微博页面编码为gb2312/gbk
            try:
                html = raw.decode('gb2312')
            except Exception:
                try:
                    html = raw.decode('gbk')
                except Exception:
                    html = raw.decode('utf-8', errors='ignore')
    except Exception as e:
        logger.warning(f"微博HTML异常: {e}")
        return []

    # 从HTML中提取热搜条目: <td class="td-02"><a>词</a><span>热度</span>
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    results = []
    # 匹配模式: td-02 后的 a 标签内容 + span 热度
    pattern = re.compile(r'<td class="td-02">\s*<a[^>]*>(.*?)</a>.*?<span>(.*?)</span>', re.S)
    matches = pattern.findall(html)
    if not matches:
        # 尝试更宽松的模式
        pattern2 = re.compile(r'<a[^>]*href="/weibo\?q=[^"]*"[^>]*>(.*?)</a>.*?<span>(\d+)</span>', re.S)
        matches = pattern2.findall(html)

    for word, heat in matches:
        word = word.strip().strip('#')
        if not word or len(word) < 2:
            continue
        brand = _match_brand(word)
        if not brand:
            continue
        try:
            h = int(heat)
        except ValueError:
            h = 0
        results.append({
            'keyword': word, 'brand': brand,
            'link': f'https://s.weibo.com/weibo?q={word}',
            'label': '', 'heat': h if h > 0 else 0,
            'created_at': now,
        })
    return results


def _parse_api(data: dict) -> List[dict]:
    """解析API JSON"""
    realtime = data.get('data', {}).get('realtime') or []
    hotgov = data.get('data', {}).get('hotgov') or {}
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    candidates: Dict[str, list] = {}
    for rs in realtime:
        word = rs.get('word', '').strip()
        if not word:
            continue
        brand = _match_brand(word)
        if not brand:
            continue
        keyword = word.strip('#')
        candidates.setdefault(brand, []).append({
            'keyword': keyword, 'brand': brand,
            'link': f'https://s.weibo.com/weibo?q={keyword}',
            'label': rs.get('label_name', '') or rs.get('flag_desc', ''),
            'heat': rs.get('num', 0) or rs.get('rank', 0),
            'created_at': now,
        })

    if hotgov:
        name = hotgov.get('word', '').strip('#')
        if name:
            brand = _match_brand(name)
            if brand:
                candidates.setdefault(brand, []).append({
                    'keyword': name, 'brand': brand,
                    'link': f'https://s.weibo.com/weibo?q={name}',
                    'label': '置顶', 'heat': 0, 'created_at': now,
                })

    # 同品牌simhash合并
    merged: List[dict] = []
    for brand, items in candidates.items():
        hashes = [(it, _compute_simhash(it['keyword'])) for it in items]
        used = set()
        for i, (it1, h1) in enumerate(hashes):
            if i in used:
                continue
            for j, (it2, h2) in enumerate(hashes):
                if j <= i or j in used:
                    continue
                if _hamming_dist(h1, h2) <= SIMHASH_THRESHOLD:
                    used.add(j)
            merged.append(it1)
    return merged


async def collect(session: aiohttp.ClientSession) -> List[dict]:
    """多渠道采集：API → HTML 降级"""
    # 方案A：JSON API
    data = await _fetch_api(session)
    if data:
        items = _parse_api(data)
        if items:
            logger.info(f"微博热搜(API): {len(items)} 条品牌命中")
            return items
        # API返回了数据但无品牌命中——尝试HTML
        logger.info("微博热搜(API): 提取到数据但0条品牌命中，尝试HTML")

    # 方案B：HTML直采
    items = await _fetch_html(session)
    logger.info(f"微博热搜(HTML): {len(items)} 条品牌命中")
    return items
