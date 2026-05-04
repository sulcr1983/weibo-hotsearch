"""AI总结生成器 (火山引擎 GLM-4-Flash)"""
import aiohttp

from v2.logger import get_logger

logger = get_logger('ai')

_SYSTEM_PROMPT = (
    '你是汽车行业专业分析师。严格基于给定事实提炼总结，'
    '按创意营销/公关、投放与合作、明星与IP、核心活动四个维度归纳。'
    '不编造、不猜测、不做主观评价。输出150-200字中文。'
)


async def weekly_summary(api_key: str, api_url: str, model: str, by_brand: dict, week_start: str, week_end: str, total: int) -> str:
    if not api_key:
        return ''
    items = []
    for brand, dims in by_brand.items():
        for dn, arts in dims.items():
            for a in arts[:3]:
                items.append(f"[{brand}] {dn} — {a['title']}")
            if len(items) >= 30:
                break
    prompt = (
        f"你是汽车行业专业分析师。以下是 {week_start} 至 {week_end} 一周"
        f"汽车行业 10 个品牌的舆情动态（共 {total} 条）。\n"
        f"请严格基于给定事实，撰写 150-200 字中文周度核心总结。\n\n"
        f"要求：\n"
        f"1. 真实性第一：严禁编造\n"
        f"2. 按四个维度归纳行业亮点与趋势\n"
        f"3. 只提炼有实质内容的维度\n"
        f"4. 客观专业语气\n\n动态列表：\n"
    )
    for it in items:
        prompt += f"- {it}\n"
    return await _call_ai(api_key, api_url, model, _SYSTEM_PROMPT, prompt)


async def monthly_summary(api_key: str, api_url: str, model: str, report: dict) -> str:
    if not api_key:
        return ''
    parts = []
    for b in report.get('brands', []):
        kwds = [it['title'] for it in b.get('items', [])[:5]]
        if kwds:
            parts.append(f"{b['brand']}({b['count']}次): {'; '.join(kwds)}")
    prompt = (
        f"你是汽车行业专业分析师。以下是{report.get('label','上个月')}"
        f"微博热搜中 10 个汽车品牌的出现情况。\n"
        f"请撰写 150-200 字月度总结，包括：品牌热度排名、月度核心话题、"
        f"相比上月的变化趋势、值得关注的舆情信号。\n"
        f"严禁编造。\n\n品牌数据：\n"
    )
    for p in parts:
        prompt += f"- {p}\n"
    return await _call_ai(api_key, api_url, model, (
        '你是汽车行业专业分析师。基于微博热搜数据撰写月度舆情总结。'
        '包含品牌热度排名、核心话题、趋势变化、舆情信号。不编造。150-200字中文。'
    ), prompt)


async def _call_ai(api_key: str, api_url: str, model: str, sys_prompt: str, user_prompt: str) -> str:
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}
    data = {'model': model, 'messages': [{'role': 'system', 'content': sys_prompt}, {'role': 'user', 'content': user_prompt}], 'temperature': 0.3}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(api_url, headers=headers, json=data, timeout=aiohttp.ClientTimeout(total=45)) as resp:
                if resp.status == 200:
                    r = await resp.json()
                    choices = r.get('choices', [])
                    if choices:
                        return choices[0].get('message', {}).get('content', '').strip()
                else:
                    logger.warning(f"AI调用失败 HTTP {resp.status}")
                return ''
    except Exception as e:
        logger.error(f"AI调用失败: {e}")
        return ''
