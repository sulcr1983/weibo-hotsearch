"""文章质量评分器：品牌命中 + 来源权重 + 强信号关键词 + 噪音惩罚 + 标题质量"""
from typing import Optional

from v2.constants import SOURCE_LEVEL, DEFAULT_BRAND_COLOR

# 强信号关键词：这些词出现说明文章有实质内容
STRONG_SIGNALS = [
    "发布", "宣布", "上市", "开售", "预售", "交付", "量产", "下线",
    "融资", "财报", "营收", "业绩", "订单", "订单量", "大定",
    "合作", "战略合作", "签约", "携手", "达成",
    "技术突破", "首发", "全球首", "国内首", "新一代",
    "OTA", "智驾", "自动驾驶", "超充", "换电", "闪充",
]

# 噪音关键词：出现这些词说明内容价值低
NOISE_SIGNALS = [
    "网友", "吐槽", "曝光", "震惊", "热议", "炸锅",
    "惊呆了", "没想到", "不可思议", "竟然", "居然",
    "二手", "水泡车", "事故车", "投诉", "维权",
    "前十", "排行", "榜单", "对比横评", "横评",
    "入门", "选购指南", "怎么选", "值不值",
]


def calc_article_score(title: str, content: str = "", source: str = "",
                       brand_hit_title: bool = True, source_level: int = 3) -> dict:
    """计算文章质量分 (0~100)，返回 {'score': int, 'breakdown': dict}"""
    score = 50  # 基础分
    breakdown = {"base": 50}

    # 1. 品牌命中位置
    if brand_hit_title:
        score += 20
        breakdown["brand_title"] = 20
    else:
        score += 10
        breakdown["brand_content"] = 10

    # 2. 来源权重 (1=央媒, 2=财经/垂媒, 3=新媒体)
    text = title + ' ' + (content or '')[:200]
    if source_level == 1:
        score += 20
        breakdown["source_A"] = 20
    elif source_level == 2:
        score += 12
        breakdown["source_B"] = 12
    else:
        score += 5
        breakdown["source_C"] = 5

    # 3. 强信号关键词加分
    signal_hits = [kw for kw in STRONG_SIGNALS if kw in text]
    signal_bonus = min(len(signal_hits) * 6, 24)
    score += signal_bonus
    if signal_hits:
        breakdown["signals"] = signal_bonus
        breakdown["signal_kws"] = signal_hits[:5]

    # 4. 噪音惩罚
    noise_hits = [kw for kw in NOISE_SIGNALS if kw in text]
    noise_penalty = len(noise_hits) * 10
    score -= noise_penalty
    if noise_hits:
        breakdown["noise"] = -noise_penalty
        breakdown["noise_kws"] = noise_hits[:3]

    # 5. 标题质量
    tlen = len(title)
    if 12 <= tlen <= 35:
        score += 8
        breakdown["title_ok"] = 8
    elif tlen < 6:
        score -= 10
        breakdown["title_short"] = -10
    elif tlen > 50:
        score -= 5
        breakdown["title_long"] = -5

    # 6. 正文丰富度
    clen = len(content or '')
    if clen >= 200:
        score += 5
        breakdown["content_rich"] = 5
    elif clen < 80:
        score -= 5
        breakdown["content_thin"] = -5

    score = max(0, min(100, score))
    return {"score": score, "breakdown": breakdown}


def score_tier(score: int) -> str:
    """评分分层：strong(>=65) / weak(>=35) / discard(<35)"""
    if score >= 65:
        return "strong"
    elif score >= 35:
        return "weak"
    else:
        return "discard"
