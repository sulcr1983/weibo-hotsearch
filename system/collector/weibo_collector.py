"""微博热搜采集器 V4.1：免Cookie API + 别名字典匹配 + 事件生命周期"""
from datetime import datetime
from typing import List, Optional, Dict

import aiohttp
import simhash

from v2.logger import get_logger

logger = get_logger('weibo')

SIDE_API = 'https://weibo.com/ajax/side/hotSearch'

# 品牌别名字典 (主品牌名 → [匹配关键词])
BRAND_DICT: Dict[str, list] = {
    "小米汽车": ["小米汽车", "小米SU7", "小米YU7"],
    "鸿蒙智行": ["鸿蒙智行", "问界", "智界", "尊界", "享界", "尚界"],
    "零跑汽车": ["零跑汽车", "零跑", "零跑C"],
    "理想汽车": ["理想汽车", "理想L", "理想MEGA", "理想i", "理想ONE"],
    "蔚来汽车": ["蔚来汽车", "蔚来", "萤火虫", "乐道"],
    "极氪汽车": ["极氪汽车", "极氪", "极氪00"],
    "阿维塔": ["阿维塔"],
    "智己汽车": ["智己汽车", "智己", "智己L"],
    "比亚迪": ["比亚迪", "仰望", "腾势", "方程豹"],
    "特斯拉": ["特斯拉", "Tesla", "Model Y", "Model 3"],
}

SIMHASH_THRESHOLD = 15


def _match_brand(text: str) -> Optional[str]:
    """别名字典匹配：精确匹配品牌关键词，优先匹配更长的词"""
    import re
    for brand, aliases in BRAND_DICT.items():
        # 按长度排序，优先匹配更长的关键词
        sorted_aliases = sorted(aliases, key=lambda x: -len(x))
        for alias in sorted_aliases:
            # 如果是完整品牌名（如"小米汽车"），简单包含匹配
            if alias == brand:
                if alias in text:
                    return brand
            # 如果是型号（以字母结尾，如"理想L"、"零跑C"、"Model Y"）
            elif len(alias) >= 2 and re.search(r'[A-Za-z]$', alias):
                pattern = re.compile(re.escape(alias) + r'(?:[a-zA-Z0-9]*(?:[^a-zA-Z0-9]|$))')
                if pattern.search(text):
                    return brand
            # 如果是型号（以数字结尾但前面有字母，如"小米SU7"、"理想MEGA"）
            elif len(alias) >= 3 and re.search(r'[A-Za-z].*[0-9]$', alias):
                # 允许后面跟字母数字（如"小米SU7Ultra"）
                pattern = re.compile(re.escape(alias) + r'(?:[a-zA-Z0-9]*(?:[^a-zA-Z0-9]|$))')
                if pattern.search(text):
                    return brand
            # 如果是纯数字结尾的型号（如"极氪00"），后面可以跟数字或结束
            elif len(alias) >= 2 and re.search(r'[0-9]$', alias):
                pattern = re.compile(re.escape(alias) + r'(?:[0-9]*(?:[^a-zA-Z0-9]|$))')
                if pattern.search(text):
                    return brand
            # 子品牌（如"问界"、"乐道"、"仰望"），简单包含匹配但避免部分匹配
            else:
                # 前面可以是非字母数字或中文边界，后面可以是字母数字或边界
                # 允许"三问享界S9"这样的情况
                pattern = re.compile(r'(?:^|[\s#@【】《》，。！？、]|(?<=[\u4e00-\u9fff]))' + re.escape(alias) + r'(?:[a-zA-Z0-9]*[^a-zA-Z0-9]|$)')
                if pattern.search(text):
                    return brand
    return None


def _compute_keyword_simhash(keyword: str) -> str:
    """对热搜关键词计算 simhash（用于相似合并）"""
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


async def _fetch(session: aiohttp.ClientSession) -> Optional[dict]:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://weibo.com/',
    }
    try:
        async with session.get(SIDE_API, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 200:
                return await resp.json()
            logger.warning(f"微博API HTTP {resp.status}")
            return None
    except Exception as e:
        logger.warning(f"微博API异常: {e}")
        return None


def _parse(data: dict) -> List[dict]:
    """解析热搜JSON，品牌匹配后返回。同品牌相似热搜自动合并。"""
    realtime = data.get('data', {}).get('realtime') or []
    hotgov = data.get('data', {}).get('hotgov') or {}
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Step 1: 品牌匹配
    candidates: Dict[str, list] = {}
    for rs in realtime:
        word = rs.get('word', '').strip()
        if not word:
            continue
        brand = _match_brand(word)
        if not brand:
            continue
        keyword = word.strip('#')
        link = f'https://s.weibo.com/weibo?q={keyword}'
        candidates.setdefault(brand, []).append({
            'keyword': keyword, 'brand': brand, 'link': link,
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

    # Step 2: 同品牌内 simhash 相似合并
    merged: List[dict] = []
    for brand, items in candidates.items():
        hashes = [(it, _compute_keyword_simhash(it['keyword'])) for it in items]
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
    data = await _fetch(session)
    if not data:
        return []
    items = _parse(data)
    logger.info(f"微博热搜: {len(items)} 条品牌命中（已合并）")
    return items
