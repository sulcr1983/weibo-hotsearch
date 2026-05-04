"""LLM 精确分类器（V4.0）：关键词未命中维度时调 AI 判断"""
import aiohttp

from v2.logger import get_logger
from processor.classifier import DIMENSION_RULES, get_all_dimensions

logger = get_logger('llm')


async def classify_with_llm(title: str, content: str, api_key: str, api_url: str, model: str) -> str:
    """关键词分类未命中时，扔给 LLM 精确判断。返回维度名或空字符串"""
    if not api_key:
        return ''

    dims_text = '\n'.join(f"  {d[0]}: {', '.join(d[1][:8])}..." for d in DIMENSION_RULES)
    prompt = (
        f"你是汽车行业内容分类助手。请判断以下新闻是否属于下列4个业务维度之一。\n"
        f"如果属于，只回复维度名称（如：⚙️ 核心活动）。如果不属于任何维度，只回复：NONE。\n\n"
        f"四个维度：\n{dims_text}\n\n"
        f"新闻标题：{title}\n"
        f"新闻摘要：{content[:200]}\n\n"
        f"请判断维度（只回复维度名或NONE）："
    )

    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}
    data = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': '你是汽车行业内容分类助手。只回复维度名称或NONE，不做任何解释。'},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': 0.1,
        'max_tokens': 30,
    }
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(api_url, headers=headers, json=data, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    r = await resp.json()
                    choices = r.get('choices', [])
                    if choices:
                        result = choices[0].get('message', {}).get('content', '').strip()
                        for dim_name, _ in DIMENSION_RULES:
                            if dim_name in result:
                                logger.info(f"LLM分类: [{dim_name}] {title[:30]}")
                                return dim_name
                logger.debug(f"LLM分类返回NONE: {title[:30]}")
                return ''
    except Exception as e:
        logger.error(f"LLM分类调用失败: {e}")
        return ''
