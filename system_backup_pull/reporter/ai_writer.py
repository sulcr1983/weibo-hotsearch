"""AI总结生成器 V5.2 — 传完整content + 周报/月报分开优化"""

import json
import aiohttp
from typing import Optional

from v2.logger import get_logger

logger = get_logger('ai')


async def _call_ai(api_key: str, api_url: str, model: str,
                   sys_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
    if not api_key:
        return ''
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}
    data = {
        'model': model,
        'messages': [{'role': 'system', 'content': sys_prompt},
                     {'role': 'user', 'content': user_prompt}],
        'temperature': temperature,
        'max_tokens': 600,
    }
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(api_url, headers=headers, json=data,
                              timeout=aiohttp.ClientTimeout(total=60)) as resp:
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


async def _call_ai_json(api_key: str, api_url: str, model: str,
                        sys_prompt: str, user_prompt: str) -> Optional[dict]:
    raw = await _call_ai(api_key, api_url, model, sys_prompt, user_prompt, temperature=0.1)
    if not raw:
        return None
    raw = raw.strip()
    if raw.startswith('```'):
        try:
            raw = raw.split('\n', 1)[1]
        except IndexError:
            pass
        if raw.endswith('```'):
            raw = raw[:-3]
        raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        import re
        m = re.search(r'\{[\s\S]*\}', raw)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
        return None


# ═══════ 周报总结 — 传入完整 content ═══════

async def weekly_summary(api_key: str, api_url: str, model: str,
                         by_brand: dict, week_start: str, week_end: str,
                         total: int) -> str:
    if not api_key:
        return ''

    items = []
    for brand, dims in by_brand.items():
        for dn, arts in dims.items():
            for a in arts[:3]:
                title = a.get('title', '')
                # 优先使用完整 content，回退到 summary
                content = a.get('content', '') or a.get('summary', '')
                items.append(
                    f"[{brand}] {dn} | {title}"
                    + (f" — {content[:120]}" if content else '')
                )
            if len(items) >= 35:
                break
        if len(items) >= 35:
            break

    sys_prompt = (
        '你是汽车行业首席分析师。请基于以下一周真实舆情动态（含标题+正文摘要），'
        '撰写一份150-200字的周度核心洞察。\n\n'
        '严格要求：\n'
        '1. 不是列举标题！要提炼行业趋势、竞争格局、重点事件信号\n'
        '2. 四个维度（创意营销/公关事件、投放与合作、明星与IP合作、核心活动）'
        '各用1-2句话概括本周亮点与变化\n'
        '3. 明确指出本周最值得关注的1-3个品牌及其核心动作\n'
        '4. 若某些维度本周无实质内容则自然省略\n'
        '5. 客观专业语气，禁止编造和猜测\n\n'
        '输出格式：直接输出总结正文，不要"本周总结："等任何前缀。'
    )

    prompt = (
        f"以下是 {week_start} 至 {week_end} 一周汽车行业10个品牌的舆情动态"
        f"（共 {total} 条）：\n\n" + '\n'.join(items)
    )
    return await _call_ai(api_key, api_url, model, sys_prompt, prompt)


# ═══════ 月报总结 — 传入完整热搜信息 ═══════

async def monthly_summary(api_key: str, api_url: str, model: str,
                          report: dict) -> str:
    if not api_key:
        return ''

    parts = []
    for b in report.get('brands', []):
        items = b.get('items', b.get('keywords', []))
        kwds = []
        for it in items[:5]:
            kw = it.get('keyword', it.get('title', ''))
            cnt = it.get('appear_count', 1)
            if cnt > 1:
                kwds.append(f"{kw}(×{cnt})")
            else:
                kwds.append(kw)
        if kwds:
            appears = b.get('count', b.get('total_appears', 0))
            parts.append(
                f"{b['brand']}（{appears}次）: {'; '.join(kwds)}"
            )

    sys_prompt = (
        '你是汽车行业首席分析师。请基于以下一个月微博热搜数据，'
        '撰写一份150-200字的月度舆情洞察。\n\n'
        '严格要求：\n'
        '1. 品牌热度排名：按出现频次说明哪些品牌最受关注及原因\n'
        '2. 月度核心话题：提炼本月最突出的1-2个行业核心话题\n'
        '3. 趋势变化：相比上月值得注意的变化方向\n'
        '4. 舆情信号：值得品牌关注的潜在舆情风险或机会\n'
        '5. 禁止编造猜测，只基于给定数据\n\n'
        '输出格式：直接输出总结正文，不要任何前缀。'
    )

    prompt = (
        f"以下是{report.get('label', '上个月')}微博热搜中"
        f"10个汽车品牌的出现情况：\n\n" + '\n'.join(parts)
    )
    return await _call_ai(api_key, api_url, model, sys_prompt, prompt)


# ═══════ AI 爬虫 — 从 HTML 提取结构化文章 ═══════

SCRAPER_SYS = (
    '你是一个网页数据提取器。'
    '请从以下汽车行业网页文本中提取所有新闻/文章条目。\n\n'
    '严格JSON：{"articles":[{"title":"标题","url":"链接",'
    '"summary":"50字以内摘要","time":"发布时间(YYYY-MM-DD HH:MM,未知null)",'
    '"source":"来源名称"}]}\n'
    '规则：title完整不截断 | url相对路径亦可 | summary从正文提炼≤50字 | '
    '跳过导航/广告/页脚 | 最多15条 | 无则{"articles":[]}'
)


async def ai_extract_articles(api_key: str, api_url: str, model: str,
                               html_text: str, source_name: str) -> list:
    if len(html_text) > 8000:
        html_text = html_text[:8000]
    prompt = f"网页来源: {source_name}\n\n网页文本内容:\n{html_text}"
    result = await _call_ai_json(api_key, api_url, model, SCRAPER_SYS, prompt)
    if result and isinstance(result.get('articles'), list):
        return result['articles']
    return []


async def ai_extract_article_detail(api_key: str, api_url: str, model: str,
                                     html_text: str) -> Optional[dict]:
    SYS = (
        '提取JSON: {"title":"完整标题","content":"100字摘要",'
        '"time":"发布时间","tags":["标签"]}'
    )
    if len(html_text) > 5000:
        html_text = html_text[:5000]
    return await _call_ai_json(api_key, api_url, model, SYS, html_text)
