"""四维度评分分类器"""
from typing import List, Optional

DIMENSION_RULES: List[tuple] = [
    ("🎨 创意营销/公关事件", [
        "跨界联名", "官方声明", "危机公关", "互动营销", "用户互动",
        "促销联动", "品牌日", "粉丝节", "官方回应", "辟谣",
        "致歉", "召回", "声明", "回应", "澄清", "公关",
        "营销活动", "用户活动", "品牌活动日",
    ]),
    ("📤 投放与合作", [
        "KOL", "商单", "开屏投放", "商圈大屏", "快闪店", "垂媒合作",
        "付费投放", "线下投放", "场景投放", "媒体合作", "签约",
        "战略合作", "合作协议", "达成合作", "签署", "携手",
        "生态合作", "渠道合作", "共建", "入驻",
    ]),
    ("🌟 明星与IP合作", [
        "品牌代言人", "综艺植入", "IP联名", "IP 联名", "赛事赞助",
        "明星代言", "官宣代言", "联名款", "冠名", "赞助",
        "代言", "联名", "合作款", "限定款", "IP合作",
        "品牌大使", "品牌挚友", "品牌代言",
    ]),
    ("⚙️ 核心活动", [
        "新车上市", "技术发布会", "品牌主题", "发布会", "车展",
        "核心技术", "战略发布", "品牌活动", "全球首发", "上市发布会",
        "交付", "量产", "下线", "投产", "预售", "亮相",
        "发布", "首发", "上市", "开售", "试驾", "路试",
        "OTA升级", "智驾", "自动驾驶", "超充", "换电",
        "财报", "业绩", "营收", "交付量", "订单量",
    ]),
]


def classify_dimension(title: str, content: str = '') -> str:
    text = title + ' ' + (content or '')[:300]
    if not text.strip():
        return ''
    scored = []
    for dim_name, keywords in DIMENSION_RULES:
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scored.append((score, dim_name))
    if scored:
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]
    return ''


def get_all_dimensions() -> List[str]:
    return [d[0] for d in DIMENSION_RULES]
