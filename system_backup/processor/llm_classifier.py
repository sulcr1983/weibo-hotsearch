"""LLM 精确分类器（V4.2）：关键词未命中维度时调 AI 判断，更宽容的兜底策略"""
import aiohttp
import re

from v2.logger import get_logger
from processor.classifier import DIMENSION_RULES, get_all_dimensions

logger = get_logger('llm')

# V4.2: 维度的模糊关键词映射，用于解析LLM输出
_DIM_HINTS = {
    "⚙️ 核心活动": ["核心活动", "产品", "技术", "活动", "上市", "发布", "交付", "量产", "财报", "业绩"],
    "🎨 创意营销/公关事件": ["创意营销", "公关事件", "营销", "公关", "促销", "优惠", "降价", "声明", "回应", "品牌"],
    "📤 投放与合作": ["投放", "合作", "战略", "出海", "供应链", "投资", "网络", "渠道"],
    "🌟 明星与IP合作": ["明星", "IP", "代言", "联名", "赞助", "冠名", "综艺"],
}


async def classify_with_llm(title: str, content: str, api_key: str, api_url: str, model: str) -> str:
    """关键词分类未命中时，扔给 LLM 精确判断。V4.2: 更宽容，尽量不返回空"""
    if not api_key:
        return ''

    dims_text = '\n'.join(f"  {d[0]}: {', '.join(d[1][:8])}..." for d in DIMENSION_RULES)
    prompt = (
        f"你是汽车行业内容分类助手。请将以下汽车行业新闻归入最接近的维度。\n"
        f"每个新闻都必须归入一个维度，选择最相关的那一个。\n"
        f"只回复维度全名（如：⚙️ 核心活动）。\n\n"
        f"四个维度：\n{dims_text}\n\n"
        f"新闻标题：{title}\n"
        f"新闻摘要：{content[:200]}\n\n"
        f"请选择一个维度（只回复维度全名）："
    )

    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}
    data = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': '你是汽车行业内容分类助手。必须选择一个维度回复其全名，不做解释。'},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': 0.1,
        'max_tokens': 30,
    }
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(api_url, headers=headers, json=data, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status == 200:
                    r = await resp.json()
                    choices = r.get('choices', [])
                    if choices:
                        result = choices[0].get('message', {}).get('content', '').strip()
                        # V4.2: 尝试精确匹配维度名
                        for dim_name, _ in DIMENSION_RULES:
                            if dim_name in result:
                                logger.info(f"LLM分类: [{dim_name}] {title[:30]}")
                                return dim_name
                        # V4.2: 模糊匹配 — 基于LLM输出中的关键词推断维度
                        dim = _fuzzy_match_dimension(result)
                        if dim:
                            logger.info(f"LLM模糊分类: [{dim}] {title[:30]} (raw: {result[:40]})")
                            return dim
                        # V4.2: 最终兜底 — 只要是汽车行业新闻，默认归入核心活动
                        if result and result.strip() and result.strip().upper() != 'NONE':
                            fallback = "⚙️ 核心活动"
                            logger.info(f"LLM兜底分类: [{fallback}] {title[:30]} (raw: {result[:40]})")
                            return fallback
                logger.debug(f"LLM分类返回空/NONE: {title[:30]}")
                return ''
    except Exception as e:
        logger.error(f"LLM分类调用失败: {e}")
        return ''


def _fuzzy_match_dimension(result: str) -> str:
    """V4.2: 基于LLM输出关键词的模糊维度匹配"""
    result_lower = result.lower()
    for dim_name, hints in _DIM_HINTS.items():
        score = sum(1 for h in hints if h.lower() in result_lower)
        if score >= 2:
            return dim_name
    for dim_name, hints in _DIM_HINTS.items():
        if any(h.lower() in result_lower for h in hints):
            return dim_name
    return ''
