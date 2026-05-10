export interface Prompt {
  id: string;
  step: number;
  category: 'diagnosis' | 'crawler' | 'pipeline' | 'push' | 'scheduler' | 'ops';
  severity: 'critical' | 'high' | 'medium';
  title: string;
  problem: string;
  rootCause: string;
  prompt: string;
  files: string[];
  verify: string;
}

export const CATEGORIES = {
  diagnosis: { label: '🔍 诊断自检', color: 'purple' },
  crawler: { label: '🕷️ 爬虫采集', color: 'red' },
  pipeline: { label: '🔄 清洗过滤', color: 'orange' },
  push: { label: '📤 推送报告', color: 'blue' },
  scheduler: { label: '⏰ 定时调度', color: 'green' },
  ops: { label: '🛠️ 运维稳定', color: 'gray' },
};

export const SEVERITY_LABELS = {
  critical: { label: '致命', bg: 'bg-red-100', text: 'text-red-700', border: 'border-red-300' },
  high: { label: '高危', bg: 'bg-orange-100', text: 'text-orange-700', border: 'border-orange-300' },
  medium: { label: '中等', bg: 'bg-yellow-100', text: 'text-yellow-700', border: 'border-yellow-300' },
};

export const prompts: Prompt[] = [
  // ─── STEP 1: 诊断自检 ───────────────────────────────────
  {
    id: 'diag-01',
    step: 1,
    category: 'diagnosis',
    severity: 'critical',
    title: '启动自检 & 环境变量诊断',
    problem: '系统启动后无任何输出、或立即崩溃退出，不知道哪里出错',
    rootCause: 'main.py 导入了不存在的模块（stealth_scraper、ai_scraper），config.py 的 DB_PATH 指向了根目录而非 data/ 目录，.env 未被正确加载',
    files: ['system/main.py', 'system/config.py', '.env'],
    prompt: `请帮我诊断 weibo-hotsearch 项目的启动问题。

**任务：**
1. 检查 system/main.py 的所有 import 语句，列出哪些模块实际不存在于项目中（对照项目文件树逐一核查）
2. 检查 system/config.py 中 DB_PATH 和 WEIBO_DB_PATH 的路径逻辑：
   - 当前：str(PROJECT_ROOT / os.getenv('DB_PATH', 'v3_monitor.db'))
   - 应改为：str(PROJECT_ROOT / 'data' / os.getenv('DB_PATH', 'v3_monitor.db'))
   - 确保 data/ 目录在启动时自动创建（DATA_DIR.mkdir(parents=True, exist_ok=True)）
3. 在 main.py 的 lifespan 函数中添加启动自检，依次验证：
   - 所有必填环境变量（FEISHU_WEBHOOK_URL、AI_API_KEY、EMAIL_SENDER）是否存在
   - data/ 和 logs/ 目录是否可写
   - 打印每项检查结果（✅/❌）
4. 把检查结果写入日志 logger.info()

执行后告诉我：有哪些 import 报错？DB_PATH 当前指向哪里？`,
    verify: '运行 cd /opt/weibo-hotsearch && ./venv/bin/python -c "import system.main" 无报错',
  },

  {
    id: 'diag-02',
    step: 2,
    category: 'diagnosis',
    severity: 'critical',
    title: '删除不存在的模块引用',
    problem: 'main.py 引用了 stealth_scraper、ai_scraper 两个不存在的模块，导致启动直接崩溃',
    rootCause: 'README 描述的"超级反爬"功能尚未实现，但 main.py 已经 import 并调用了这两个不存在的类，Python 解释器在启动时就会抛出 ModuleNotFoundError',
    files: ['system/main.py'],
    prompt: `请修复 system/main.py 中的模块导入崩溃问题。

**具体操作：**
1. 删除以下两行 import：
   \`\`\`python
   from collector.stealth_scraper import SuperStealthScraper
   from collector.ai_scraper import AIScraper
   \`\`\`
2. 删除对应的实例化：
   \`\`\`python
   stealth = SuperStealthScraper()
   ai_scraper = AIScraper({'api_key': AI_API_KEY, ...})
   \`\`\`
3. 在 news_collect() 函数中，删除以下调用：
   \`\`\`python
   stealth_items = await stealth.scrape_all()
   ai_items = await ai_scraper.scrape_all()
   \`\`\`
   以及相关的 all_items 拼接和日志语句
4. 更新 all_items 合并行，去掉 stealth_items 和 ai_items
5. 删除 health.record_stealth(...) 调用行

修改后请展示修改后的完整 news_collect() 函数。`,
    verify: '运行 ./venv/bin/python -c "from system.main import app" 不报 ModuleNotFoundError',
  },

  // ─── STEP 2: 爬虫采集 ───────────────────────────────────
  {
    id: 'crawler-01',
    step: 3,
    category: 'crawler',
    severity: 'critical',
    title: '微博热搜 API 失效修复',
    problem: '微博 weibo.com/ajax/side/hotSearch 频繁返回 403/302，采集一直失败',
    rootCause: '微博对该端点做了 UA 检测和 Referer 检测，移动端 UA 虽然比桌面端好，但缺少必要的 Cookie 和请求头。备用的 HTML 方案正则表达式有问题，匹配不到内容。',
    files: ['system/collector/weibo_collector.py'],
    prompt: `请修复 system/collector/weibo_collector.py 的微博热搜采集失败问题。

**修复方案：**

**方案一：修复 HTML 备用采集的正则（立即生效）**
当前 _fetch_html() 的正则表达式有转义问题，请替换为：
\`\`\`python
import re
from bs4 import BeautifulSoup

async def _fetch_html(session: aiohttp.ClientSession) -> List[dict]:
    headers = {
        'User-Agent': WEIBO_UA,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': 'https://weibo.com/',
    }
    try:
        async with session.get(HTML_TOP, headers=headers, 
                               timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                logger.warning(f"微博HTML HTTP {resp.status}")
                return []
            raw = await resp.read()
            for enc in ['gb2312', 'gbk', 'utf-8']:
                try:
                    html = raw.decode(enc)
                    break
                except Exception:
                    continue
            else:
                html = raw.decode('utf-8', errors='ignore')
    except Exception as e:
        logger.warning(f"微博HTML异常: {e}")
        return []
    
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    results = []
    soup = BeautifulSoup(html, 'html.parser')
    
    # 查找热搜列表
    for td in soup.select('td.td-02'):
        a_tag = td.find('a')
        if not a_tag:
            continue
        word = a_tag.get_text(strip=True).strip('#')
        if not word or len(word) < 2:
            continue
        
        # 获取热度
        heat = 0
        span = td.find('span')
        if span:
            try:
                heat = int(span.get_text(strip=True))
            except ValueError:
                pass
        
        brand = _match_brand(word)
        if not brand:
            continue
            
        results.append({
            'keyword': word,
            'brand': brand,
            'link': f'https://s.weibo.com/weibo?q={word}',
            'label': '',
            'heat': heat,
            'created_at': now,
        })
    
    return results
\`\`\`

**方案二：新增第三备用 - 微博移动端API**
在 collect() 函数最后添加第三个备用方案：
\`\`\`python
MOBILE_API = 'https://m.weibo.cn/api/container/getIndex?containerid=106003type%3D25%26t%3D3%26disable_hot%3D1%26filter_type%3Drealtimehot'

async def _fetch_mobile(session: aiohttp.ClientSession) -> List[dict]:
    headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.0',
        'Referer': 'https://m.weibo.cn/',
    }
    try:
        async with session.get(MOBILE_API, headers=headers,
                               timeout=aiohttp.ClientTimeout(total=12)) as resp:
            if resp.status != 200:
                return []
            data = await resp.json(content_type=None)
            cards = data.get('data', {}).get('cards', [])
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            results = []
            for card in cards:
                for mb in card.get('card_group', []):
                    word = mb.get('desc', '').strip('#').strip()
                    if not word:
                        continue
                    brand = _match_brand(word)
                    if not brand:
                        continue
                    results.append({
                        'keyword': word, 'brand': brand,
                        'link': f'https://s.weibo.com/weibo?q={word}',
                        'label': mb.get('desc_extr', ''),
                        'heat': 0, 'created_at': now,
                    })
            return results
    except Exception as e:
        logger.warning(f"微博移动端API异常: {e}")
        return []
\`\`\`

请完整替换 weibo_collector.py 的 _fetch_html、collect 函数，并加入 _fetch_mobile 备用方案。`,
    verify: '运行 curl -X POST http://localhost:8001/collect 后查看日志，应看到"微博热搜(HTML/API): N 条品牌命中"',
  },

  {
    id: 'crawler-02',
    step: 4,
    category: 'crawler',
    severity: 'high',
    title: 'RSS 源超时 & SharedSession 缺失修复',
    problem: 'RSS 采集报 ImportError: cannot import name SharedSession from v2.http_session，或大量超时',
    rootCause: 'rss_fetcher.py 引用了 v2.http_session.SharedSession 和 v2.user_agents，但这两个文件在项目中可能不存在；RSSHub Docker 未启动时所有 RSSHub 路由 503',
    files: ['system/collector/rss_fetcher.py', 'system/v2/http_session.py', 'system/v2/user_agents.py'],
    prompt: `请修复 system/collector/rss_fetcher.py 的依赖问题。

**步骤 1：检查并创建缺失的工具模块**

如果 system/v2/http_session.py 不存在，请创建：
\`\`\`python
# system/v2/http_session.py
"""共享 HTTP Session 上下文管理器"""
import aiohttp
from typing import Optional

class SharedSession:
    def __init__(self, timeout: int = 15):
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession(
            timeout=self._timeout,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) '
                              'Chrome/120.0.0.0 Safari/537.36',
            }
        )
        return self

    async def __aexit__(self, *args):
        if self._session:
            await self._session.close()

    async def fetch(self, url: str, **kwargs) -> Optional[str]:
        try:
            async with self._session.get(url, **kwargs) as resp:
                if resp.status == 200:
                    return await resp.text(errors='ignore')
                return None
        except Exception:
            return None
\`\`\`

如果 system/v2/user_agents.py 不存在，请创建：
\`\`\`python
# system/v2/user_agents.py
"""随机 User-Agent 池"""
import random

UA_POOL = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
]

def get_random_ua() -> str:
    return random.choice(UA_POOL)
\`\`\`

**步骤 2：修复 RSS 采集器容错**
在 rss_fetcher.py 的 fetch_all() 中，对 RSSHub 路由增加快速失败：
- 若 URL 包含 'localhost:1200'，先 ping 一次，失败则跳过整个 RSSHub 组，记录警告而不是报错
- 每个 feed 加个别 try-except，失败记 warning 后 continue

修改后展示完整的 fetch_all() 函数。`,
    verify: '运行 ./venv/bin/python -c "from collector.rss_fetcher import RssFetcher" 不报错',
  },

  {
    id: 'crawler-03',
    step: 5,
    category: 'crawler',
    severity: 'high',
    title: 'Web 直采 & 垂媒源反爬修复',
    problem: '网页直采大量返回 403/空内容，汽车之家、懂车帝等垂媒被反爬拦截',
    rootCause: 'web_scraper.py 和 auto_media.py 使用固定 UA，没有随机化 headers，没有请求间隔，容易被反爬拦截',
    files: ['system/collector/web_scraper.py', 'system/collector/auto_media.py'],
    prompt: `请加固 system/collector/web_scraper.py 和 system/collector/auto_media.py 的反爬能力。

**修复要点（两个文件都需要）：**

1. **随机化请求头**：每次请求使用不同的 User-Agent，加上合理的 Accept、Accept-Language、Accept-Encoding
\`\`\`python
import random

def _get_headers(referer: str = '') -> dict:
    ua_list = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
        'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0',
    ]
    h = {
        'User-Agent': random.choice(ua_list),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    if referer:
        h['Referer'] = referer
    return h
\`\`\`

2. **加请求间隔**：每个源之间 sleep(random.uniform(1.5, 3.5)) 秒

3. **超时 & 重试**：单个源超时设 12 秒，失败后 sleep(2) 重试一次，两次都失败才 skip

4. **汽车之家/懂车帝特殊处理**：这两个站点需要带 Referer，请在 auto_media.py 中为这两个源单独设置：
   - 汽车之家：Referer = 'https://www.autohome.com.cn/'
   - 懂车帝：Referer = 'https://www.dongchedi.com/'

5. **graceful 降级**：scrape_all() 里每个源独立 try-except，失败的源记 warning 后 continue，不影响其他源

请修改这两个文件，展示修改后的核心函数。`,
    verify: '运行 curl -X POST http://localhost:8001/collect 后日志显示至少一个 Web 源成功采集',
  },

  // ─── STEP 3: 清洗过滤 ───────────────────────────────────
  {
    id: 'pipeline-01',
    step: 6,
    category: 'pipeline',
    severity: 'critical',
    title: '过滤器太严导致0条入库',
    problem: '采集到了几百条数据，但漏斗显示"入库: 0条"，所有内容都被过滤掉了',
    rootCause: '四维度分类器关键词过少+过严，LLM分类又因为 API Key 未配置而失败，导致所有内容都在 NO_DIMENSION 步骤被丢弃；同时评分系统的 discard 阈值可能设置不合理',
    files: ['system/processor/classifier.py', 'system/processor/brand_matcher.py', 'system/processor/scoring.py', 'system/main.py'],
    prompt: `请诊断并修复"采集到数据但0条入库"的问题。

**步骤 1：在 news_collect() 中添加详细漏斗日志**

在 main.py 的 news_collect() 函数末尾，确保输出详细的漏斗统计：
\`\`\`python
# 在 for raw in all_items 循环结束后添加：
logger.info(f"""
=== 采集漏斗报告 ===
  原始捕获: {funnel.raw_captured}
  品牌命中: {funnel.brand_hit}
  评分丢弃: {funnel.score_discarded}
  维度通过: {funnel.dimension_pass}
  金融过滤: {funnel.financial_filtered}
  去重过滤: {funnel.dedup_filtered}
  实际入库: {enriched}
===================
""")
\`\`\`

**步骤 2：放宽四维度关键词（classifier.py）**

检查 system/processor/classifier.py，在现有关键词基础上新增更宽泛的汽车行业词：
- ⚙️ 核心活动维度增加：发布、推出、正式上市、首发、亮相、交付、量产、预售、官宣、宣布、开启、启动、完成、达成、突破、创新、进展
- 🎨 创意营销维度增加：营销、活动、推广、宣传、品牌、形象、口碑、话题、讨论、热议
- 🌟 明星IP维度增加：代言、合作、联名、签约、赞助
- 📤 投放合作维度增加：合作、战略、投资、融资、布局、扩张

**步骤 3：放宽评分阈值（scoring.py）**

如果 system/processor/scoring.py 存在 discard 阈值，将丢弃阈值从 35 改为 20（或者找到 score_tier() 函数，将 'discard' 分支的阈值降低）

**步骤 4：LLM 分类失败时不丢弃**

在 main.py 的维度判断逻辑中，将 LLM 失败时的处理从"丢弃"改为"标记为 other 维度继续入库"：
\`\`\`python
if not dim:
    dim = await classify_with_llm(title, content, AI_API_KEY, AI_API_URL, AI_MODEL)
    if not dim:
        # 不再丢弃，改为使用 'other' 维度，但仍记录日志
        dim = 'other'
        logger.debug(f"[DIM:FALLBACK] {title[:50]} → 使用 other 维度")
\`\`\`

请逐步操作，每步完成后告知结果。`,
    verify: '运行 curl -X POST http://localhost:8001/collect 后日志显示"实际入库: N条"（N > 0）',
  },

  {
    id: 'pipeline-02',
    step: 7,
    category: 'pipeline',
    severity: 'high',
    title: '品牌匹配误杀 & 误匹配修复',
    problem: '"理想"匹配到"理想主义"，"蔚来"匹配到"未来"，或者大量汽车新闻匹配不到品牌',
    rootCause: 'brand_matcher.py 的词边界检测逻辑对中文不够精确，中文没有空格分词，简单的 in 操作会导致误匹配；而某些正确品牌名反而因为规则过严被漏掉',
    files: ['system/processor/brand_matcher.py'],
    prompt: `请优化 system/processor/brand_matcher.py 的品牌匹配精度。

**问题一：中文误匹配**
当前代码用 isalnum() 检查边界，但对中文字符不适用（中文字符 isalnum() 返回 True）。

请将 _match_brand() 或 match_brand() 函数中的边界检测改为：
\`\`\`python
import re

# 对短关键词（<=3个字）严格匹配，对长关键词（>3个字）直接 in 搜索
def _is_standalone(text: str, keyword: str, idx: int) -> bool:
    """检查 keyword 在 text[idx] 处是否独立出现（非更长词的一部分）"""
    end = idx + len(keyword)
    # 前一个字符：如果是字母/数字则不独立
    if idx > 0 and text[idx-1].isascii() and text[idx-1].isalnum():
        return False
    # 后一个字符：同上
    if end < len(text) and text[end].isascii() and text[end].isalnum():
        return False
    return True

def _match_single(text: str, keyword: str) -> bool:
    if len(keyword) >= 4:
        # 长关键词直接 in 匹配
        return keyword in text
    idx = text.find(keyword)
    while idx >= 0:
        if _is_standalone(text, keyword, idx):
            return True
        idx = text.find(keyword, idx + 1)
    return False
\`\`\`

**问题二：容易误杀的短词处理**
以下短词应加强保护，确保不被边界检测过滤：
- "蔚来"：只要出现就认为是品牌（4字以上语境不会误匹配）
- "理想"：仅当后面跟着"汽车/L/MEGA/i/"或前面是"品牌"语境时才认为是品牌（防止"理想主义"误匹配）
- "零跑"：直接匹配

请在 brand_matcher.py 中实现以上逻辑，并添加单元测试注释说明预期行为。`,
    verify: '运行 python -c "from processor.brand_matcher import match_brand; print(match_brand(\'理想主义者\', \'\'))"  应返回 (None, None)',
  },

  {
    id: 'pipeline-03',
    step: 8,
    category: 'pipeline',
    severity: 'medium',
    title: 'SimHash 去重模块崩溃修复',
    problem: 'deduplicator.py 导入 simhash 包时崩溃，或 compute_simhash() 对短文本报错',
    rootCause: 'python-simhash 包的 API 在不同版本间有变化；对空字符串或极短文本没有保护逻辑',
    files: ['system/processor/deduplicator.py'],
    prompt: `请修复 system/processor/deduplicator.py 的稳定性问题。

**检查并修复以下问题：**

1. **import 保护**：用 try-except 包裹 simhash 导入：
\`\`\`python
try:
    from simhash import Simhash
    SIMHASH_AVAILABLE = True
except ImportError:
    SIMHASH_AVAILABLE = False
\`\`\`

2. **compute_simhash() 防御性修复**：
\`\`\`python
def compute_simhash(text: str) -> str:
    """计算文本 SimHash，失败时返回基于 hash() 的退化值"""
    if not text or len(text.strip()) < 4:
        return '0' * 16
    if not SIMHASH_AVAILABLE:
        # 退化方案：用 md5 前16位替代
        import hashlib
        return hashlib.md5(text.encode()).hexdigest()[:16]
    try:
        import jieba
        words = [w for w in jieba.cut(text) if len(w.strip()) >= 2]
        if not words:
            words = [text[:20]]
        sh = Simhash(words)
        return format(sh.value, '016x')
    except Exception as e:
        import hashlib
        return hashlib.md5(text.encode()).hexdigest()[:16]
\`\`\`

3. **cluster_article() 防御**：
\`\`\`python
def cluster_article(new_simhash: str, existing_hashes: list) -> str | None:
    """返回相似文章的 event_id，无相似则返回 None"""
    if not new_simhash or new_simhash == '0' * 16:
        return None
    try:
        for (sh, eid) in existing_hashes:
            if not sh or sh == '0' * 16:
                continue
            dist = bin(int(new_simhash, 16) ^ int(sh, 16)).count('1')
            if dist <= 20:
                return eid
    except Exception:
        pass
    return None
\`\`\`

请完整重写 deduplicator.py，保留原有逻辑并加上以上防御代码。`,
    verify: 'python -c "from processor.deduplicator import compute_simhash; print(compute_simhash(\'\'))" 输出全0字符串不报错',
  },

  // ─── STEP 4: 推送报告 ───────────────────────────────────
  {
    id: 'push-01',
    step: 9,
    category: 'push',
    severity: 'critical',
    title: '日报推送空数据修复',
    problem: '日报按时触发但飞书/邮件收到"0条新闻、0条微博"的空报告',
    rootCause: 'builder.py 的 build_daily() 查询昨日数据，但 get_articles(date=date) 的 SQL 可能用了 LIKE 匹配，而数据库中 created_at 格式是"YYYY-MM-DD HH:MM:SS"，单纯按日期过滤没问题；真正的原因是 score>=65 的文章极少，导致 strong 列表为空，而 fallback 的 score>=35 也没数据（因为前面的过滤已经把所有数据丢弃了）',
    files: ['system/reporter/builder.py', 'system/storage/database.py'],
    prompt: `请修复日报推送"0条内容"的问题。

**步骤 1：在 build_daily() 中添加调试日志**
\`\`\`python
async def build_daily(self) -> dict:
    date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    news = await self.db.get_articles(date=date)
    weibo = await self.db.get_weibo_events(date=date, status=None)
    
    # 添加调试日志
    logger.info(f"[日报] 查询日期={date}, 原始新闻={len(news)}条, 微博={len(weibo)}条")
    if news:
        scores = [n.get('score', 0) for n in news]
        logger.info(f"[日报] 分数分布: min={min(scores)}, max={max(scores)}, avg={sum(scores)//len(scores)}")
\`\`\`

**步骤 2：放宽日报筛选条件**
将当前的 score>=65 降低为 score>=40，fallback 从 score>=35 降为 score>=20：
\`\`\`python
strong = [n for n in news if n.get('score', 0) >= 40 and classify_dimension(n.get('title', ''), n.get('content', '') or '')]
strong.sort(key=lambda x: x.get('score', 0), reverse=True)
if len(strong) < 3:
    weak = [
        n for n in news
        if n.get('score', 0) >= 20
        and n not in strong
    ]
    weak.sort(key=lambda x: x.get('score', 0), reverse=True)
    strong.extend(weak[:10 - len(strong)])
\`\`\`

**步骤 3：检查 database.py 的 get_articles() 方法**
确认 SQL 查询语句：
\`\`\`sql
SELECT * FROM articles WHERE created_at >= ? AND created_at < ?
\`\`\`
参数应是 (date + ' 00:00:00', date + ' 23:59:59') 而不是只传一个 date。

**步骤 4：如果数据库真的是空的**
在 build_daily() 中，当 news 和 weibo 都为空时，改变策略：取最近 48 小时而不是严格昨天：
\`\`\`python
if not news:
    logger.warning("[日报] 昨日无数据，扩展至最近48小时")
    news = await self.db.get_articles(hours=48)
\`\`\`

请完整修改 build_daily()，展示修改后的代码。`,
    verify: 'curl -X POST http://localhost:8001/report/daily 后飞书/邮件收到非空报告',
  },

  {
    id: 'push-02',
    step: 10,
    category: 'push',
    severity: 'high',
    title: '飞书推送 API 格式错误修复',
    problem: '飞书收到推送但显示"消息发送失败"或卡片格式异常，日志报"StatusCode: 19001"',
    rootCause: '飞书 Interactive Card 格式在 2024 年后有变化，旧版 elements 结构可能不兼容新版卡片格式；卡片内容超长（>4000字符）也会导致失败',
    files: ['system/reporter/feishu.py', 'system/templates/feishu_cards.py'],
    prompt: `请修复飞书推送的格式兼容性问题。

**步骤 1：修改 feishu.py 的 send_card() 函数**
升级为飞书卡片 V2 格式，并增加内容截断保护：
\`\`\`python
async def send_card(webhook: str, title: str, template: str, elements: list):
    if not webhook:
        logger.warning("飞书 Webhook URL 未配置，跳过推送")
        return
    
    # 内容截断保护：飞书单消息限制 4000 字
    import json
    payload = {
        'msg_type': 'interactive',
        'card': {
            'header': {
                'title': {'tag': 'plain_text', 'content': title[:100]},
                'template': template,
            },
            'elements': elements[:30],  # 最多30个元素
        }
    }
    
    payload_str = json.dumps(payload, ensure_ascii=False)
    if len(payload_str) > 30000:
        logger.warning(f"飞书消息过长({len(payload_str)}字符)，截断elements")
        payload['card']['elements'] = elements[:15]
    
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                webhook, json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                body = await resp.text()
                if resp.status == 200:
                    result = json.loads(body)
                    if result.get('StatusCode') == 0 or result.get('code') == 0:
                        logger.info(f"✅ 飞书推送成功: {title}")
                    else:
                        logger.error(f"❌ 飞书API错误: {body}")
                else:
                    logger.error(f"❌ 飞书HTTP {resp.status}: {body}")
    except Exception as e:
        logger.error(f"飞书推送异常: {e}")
\`\`\`

**步骤 2：给飞书卡片模板增加纯文本降级方案**
如果 Interactive Card 失败，降级发送 markdown 格式：
\`\`\`python
async def send_text_fallback(webhook: str, title: str, content: str):
    """降级：发送纯文本消息"""
    payload = {
        'msg_type': 'text',
        'content': {'text': f"{title}\\n{content[:3000]}"}
    }
    async with aiohttp.ClientSession() as s:
        async with s.post(webhook, json=payload,
                          headers={'Content-Type': 'application/json'},
                          timeout=aiohttp.ClientTimeout(total=15)) as resp:
            logger.info(f"飞书降级文本推送: {resp.status}")
\`\`\`

**步骤 3：在 send_daily/send_weekly/send_monthly 中加 try-except**
任何一个推送失败时，catch 异常并尝试 send_text_fallback。

请修改 feishu.py，展示完整文件内容。`,
    verify: '运行 curl -X POST http://localhost:8001/report/daily 后飞书机器人收到卡片消息',
  },

  {
    id: 'push-03',
    step: 11,
    category: 'push',
    severity: 'high',
    title: '邮件 SMTP 发送失败修复',
    problem: '日志显示"邮件发送失败: [SSL: WRONG_VERSION_NUMBER]"或"SMTPAuthenticationError"',
    rootCause: 'QQ邮箱端口配置问题：587是STARTTLS，465是SSL，两种不能混用；授权码错误或过期也会导致认证失败',
    files: ['system/reporter/emailer.py'],
    prompt: `请修复 system/reporter/emailer.py 的 SMTP 发送问题。

**问题一：SSL/TLS 端口混用**
修改 _send_sync() 函数，根据端口自动选择连接方式：
\`\`\`python
def _send_sync(sender: str, pw: str, recipients: list, server: str, port: int, subject: str, html: str):
    msg = MIMEMultipart('alternative')
    msg['From'] = sender
    msg['To'] = ','.join(recipients)
    msg['Subject'] = Header(subject, 'utf-8')
    msg.attach(MIMEText(html, 'html', 'utf-8'))
    
    try:
        if port == 465:
            # SSL 直连
            import ssl
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(server, port, context=context, timeout=30) as s:
                s.login(sender, pw)
                s.sendmail(sender, recipients, msg.as_string())
        else:
            # STARTTLS（587 或 25）
            with smtplib.SMTP(server, port, timeout=30) as s:
                s.ehlo()
                try:
                    s.starttls()
                    s.ehlo()
                except smtplib.SMTPNotSupportedError:
                    pass  # 部分服务器不支持 STARTTLS
                s.login(sender, pw)
                s.sendmail(sender, recipients, msg.as_string())
        logger.info(f"✅ 邮件发送成功: {subject} → {recipients}")
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"❌ 邮件认证失败（检查授权码是否正确）: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ 邮件发送失败: {e}")
        raise
\`\`\`

**问题二：收件人格式验证**
在 Emailer.__init__() 中增加验证：
\`\`\`python
def __init__(self, sender, pw, recipients, server='smtp.qq.com', port=587):
    self.sender = sender
    self.pw = pw
    # 过滤掉空字符串和无效地址
    self.recipients = [r for r in (recipients or []) if r and '@' in r]
    self.server = server
    self.port = port
    if not self.sender:
        logger.warning("EMAIL_SENDER 未配置，邮件推送将跳过")
    if not self.recipients:
        logger.warning("EMAIL_RECIPIENTS 未配置，邮件推送将跳过")
\`\`\`

**问题三：添加邮件连通性测试接口**
在 main.py 中新增一个测试路由（不需要认证）：
\`\`\`python
@app.post("/test/email")
async def test_email():
    try:
        emailer._send("测试邮件", "<h1>连通性测试</h1><p>邮件发送正常</p>")
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
\`\`\`

请完整修改 emailer.py 并展示。`,
    verify: 'curl -X POST http://localhost:8001/test/email 返回 {"ok": true}',
  },

  // ─── STEP 5: 定时调度 ───────────────────────────────────
  {
    id: 'scheduler-01',
    step: 12,
    category: 'scheduler',
    severity: 'critical',
    title: 'APScheduler 崩溃循环修复',
    problem: '服务不断重启，日志每12秒刷一次启动信息，或日志出现"reschedule_job"相关报错',
    rootCause: 'APScheduler 在 reschedule_job 失败时没有足够的降级保护，job 状态异常会导致调度器持续出错；同时 nohup 启动时如果 Python 崩溃了没有自动拉起',
    files: ['system/main.py', 'system/services/deploy.sh'],
    prompt: `请修复定时调度的崩溃循环问题。

**步骤 1：修复 main.py 中的调度器配置**

将调度器的 job 注册方式改为更健壮的写法：
\`\`\`python
def _setup_scheduler():
    """配置并启动调度器，所有任务注册失败时优雅降级"""
    try:
        scheduler.add_job(
            news_collect, 
            IntervalTrigger(seconds=3600),  # 每小时
            id='news_collect',
            replace_existing=True,
            max_instances=1,
            coalesce=True,  # 错过的任务只执行一次
            misfire_grace_time=300,  # 5分钟内错过的任务仍执行
        )
    except Exception as e:
        logger.error(f"news_collect 任务注册失败: {e}")
    
    try:
        scheduler.add_job(
            weibo_collect_job,
            IntervalTrigger(seconds=random.randint(3420, 4020)),  # 57~67分钟
            id='weibo_collect',
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=600,
        )
    except Exception as e:
        logger.error(f"weibo_collect 任务注册失败: {e}")
    
    # 日报：每天09:00
    try:
        scheduler.add_job(
            daily_report_job, CronTrigger(hour=9, minute=0),
            id='daily_report', replace_existing=True, max_instances=1,
        )
    except Exception as e:
        logger.error(f"daily_report 任务注册失败: {e}")
    
    # 周报：每周一08:00
    try:
        scheduler.add_job(
            weekly_report_job, CronTrigger(day_of_week='mon', hour=8, minute=0),
            id='weekly_report', replace_existing=True, max_instances=1,
        )
    except Exception as e:
        logger.error(f"weekly_report 任务注册失败: {e}")
    
    # 月报：每月1日08:00
    try:
        scheduler.add_job(
            monthly_report_job, CronTrigger(day=1, hour=8, minute=0),
            id='monthly_report', replace_existing=True, max_instances=1,
        )
    except Exception as e:
        logger.error(f"monthly_report 任务注册失败: {e}")
    
    scheduler.start()
    logger.info("✅ 调度器启动完成")
\`\`\`

**步骤 2：修复 deploy.sh 加入进程守护**
\`\`\`bash
#!/bin/bash
cd /opt/weibo-hotsearch

# 停止旧进程
pkill -f "python system/main.py" 2>/dev/null
sleep 2

# 激活虚拟环境
source venv/bin/activate

# 启动服务（带自动重启的 while 循环守护）
while true; do
    echo "$(date) 启动服务..." >> logs/deploy.log
    python system/main.py >> logs/stdout.log 2>&1
    echo "$(date) 服务退出，5秒后重启..." >> logs/deploy.log
    sleep 5
done &

echo "守护进程已启动，PID=$!"
\`\`\`

请修改 main.py 的调度器相关代码，并更新 deploy.sh。`,
    verify: '服务运行10分钟后 logs/main.log 不出现"reschedule_job"错误，进程稳定',
  },

  {
    id: 'scheduler-02',
    step: 13,
    category: 'scheduler',
    severity: 'high',
    title: '微博采集任务独立化',
    problem: '微博采集和新闻采集在同一个任务中，一旦其中一个超时就影响另一个',
    rootCause: 'main.py 的 news_collect() 同时承担了所有采集任务，应该把微博采集分离为独立的 weibo_collect_job()',
    files: ['system/main.py'],
    prompt: `请将微博采集任务从 news_collect() 中拆分出来，变成独立的调度任务。

**步骤 1：新建 weibo_collect_job() 函数**
\`\`\`python
async def weibo_collect_job():
    """独立的微博热搜采集任务"""
    logger.info(f"🔥 微博热搜采集: {datetime.now().strftime('%H:%M')}")
    try:
        session = await get_weibo_session()
        items = await weibo_collect(session)
        logger.info(f"微博热搜采集: {len(items)} 条品牌命中")
        
        if not items:
            logger.warning("本轮微博热搜：0条品牌命中")
            return
        
        saved = 0
        for item in items:
            try:
                result = await db.upsert_weibo_event(item)
                if result:
                    saved += 1
            except Exception as e:
                logger.error(f"微博入库失败: {e}")
        
        logger.info(f"微博热搜本轮新增/更新: {saved} 条")
    except Exception as e:
        logger.error(f"微博采集任务异常: {e}")
    finally:
        # 动态调整下次执行间隔（57~67分钟）
        try:
            next_seconds = random.randint(57 * 60, 67 * 60)
            scheduler.reschedule_job('weibo_collect', trigger=IntervalTrigger(seconds=next_seconds))
        except Exception:
            pass  # 忽略重调度失败，下次会自动触发
\`\`\`

**步骤 2：确认 database.py 有 upsert_weibo_event() 方法**
如果没有，在 database.py 中添加：
\`\`\`python
async def upsert_weibo_event(self, item: dict) -> bool:
    """插入或更新微博热搜事件（同一 keyword+brand 算同一事件）"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        async with aiosqlite.connect(self.weibo_path) as db:
            cur = await db.execute(
                'SELECT id, appear_count FROM hotsearch_events WHERE keyword=? AND brand=?',
                (item['keyword'], item['brand'])
            )
            row = await cur.fetchone()
            if row:
                await db.execute(
                    'UPDATE hotsearch_events SET last_seen_at=?, appear_count=?, heat=? WHERE id=?',
                    (now, row[1] + 1, item.get('heat', 0), row[0])
                )
            else:
                await db.execute(
                    'INSERT INTO hotsearch_events (keyword, brand, link, label, heat, first_seen_at, last_seen_at, appear_count, status) VALUES (?,?,?,?,?,?,?,?,?)',
                    (item['keyword'], item['brand'], item.get('link', ''), item.get('label', ''),
                     item.get('heat', 0), now, now, 1, 'active')
                )
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"微博upsert失败: {e}")
        return False
\`\`\`

**步骤 3：把微博相关代码从 news_collect() 中移除**

请修改 main.py，展示新的 weibo_collect_job() 函数和修改后的 news_collect()。`,
    verify: '运行后日志同时出现"新闻采集"和"微博热搜采集"的独立日志条目',
  },

  // ─── STEP 6: 运维稳定 ───────────────────────────────────
  {
    id: 'ops-01',
    step: 14,
    category: 'ops',
    severity: 'high',
    title: '依赖包补全 & requirements.txt 修复',
    problem: '启动时报"ModuleNotFoundError: No module named playwright"或"simhash"，或者 pip install 失败',
    rootCause: 'requirements.txt 缺少 playwright、lxml、requests 等实际用到的依赖；simhash 包需要 C 编译环境，在某些系统上安装失败',
    files: ['system/requirements.txt'],
    prompt: `请修复 system/requirements.txt 并确保所有依赖可以正确安装。

**步骤 1：更新 requirements.txt**
请将 system/requirements.txt 替换为以下内容：
\`\`\`
# Web框架
fastapi>=0.109.0,<1.0
uvicorn[standard]>=0.27.0,<1.0

# HTTP 客户端
aiohttp>=3.9.0,<4.0
requests>=2.31.0,<3.0

# 数据库
aiosqlite>=0.20.0,<0.21

# 定时调度
apscheduler>=3.10.0,<4.0

# HTML 解析
beautifulsoup4>=4.12.0,<5.0
lxml>=4.9.0

# RSS 解析
feedparser>=6.0.0,<7.0

# 中文分词
jieba>=0.42.0,<1.0

# 配置
python-dotenv>=1.0.0,<2.0
pyyaml>=6.0,<7.0

# 去重（simhash，C扩展可能需要 build-essential）
simhash>=2.0.0,<3.0

# 浏览器渲染（可选）
playwright>=1.40.0
\`\`\`

**步骤 2：修改 deploy.sh 的安装步骤**
在安装依赖时，对 simhash 安装失败做降级处理：
\`\`\`bash
# 安装依赖，simhash 单独处理
pip install -r system/requirements.txt --no-deps simhash 2>/dev/null || \\
    pip install -r system/requirements.txt  # 无 simhash 版本降级

# 单独安装 simhash，失败不阻塞
pip install simhash 2>/dev/null || echo "simhash 安装失败，将使用 MD5 降级方案"

# 安装 Playwright（仅在 PLAYWRIGHT_ENABLED=true 时）
if [ "$PLAYWRIGHT_ENABLED" = "true" ]; then
    playwright install chromium --with-deps
fi
\`\`\`

**步骤 3：验证所有模块可导入**
\`\`\`bash
cd /opt/weibo-hotsearch
./venv/bin/python -c "
import aiohttp, aiosqlite, apscheduler, bs4, feedparser, jieba, dotenv, yaml, fastapi, uvicorn
print('✅ 核心依赖全部正常')
try:
    import simhash; print('✅ simhash 可用')
except ImportError:
    print('⚠️ simhash 不可用，使用 MD5 降级')
try:
    import playwright; print('✅ playwright 可用')
except ImportError:
    print('⚠️ playwright 不可用（PLAYWRIGHT_ENABLED=false 时正常）')
"
\`\`\`

请展示修改后的 requirements.txt。`,
    verify: '运行验证脚本，核心依赖显示 ✅',
  },

  {
    id: 'ops-02',
    step: 15,
    category: 'ops',
    severity: 'medium',
    title: '日志系统 & 监控接口强化',
    problem: '日志文件过大、找不到关键错误、或 /health 接口返回空数据',
    rootCause: '日志轮转在 Windows 上有 PermissionError（服务器通常是 Linux 没问题），但日志格式不够清晰；/health 接口的数据来源于内存，服务重启后数据丢失',
    files: ['system/v2/logger.py', 'system/reporter/health.py', 'system/main.py'],
    prompt: `请强化日志系统和监控接口。

**步骤 1：改进日志格式（v2/logger.py）**
确保日志包含时间、级别、模块名，添加错误追踪：
\`\`\`python
import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(f'weibo.{name}')
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.DEBUG)
    
    fmt = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 控制台输出
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    
    # 文件输出（每天轮转，保留8天）
    try:
        log_dir = Path(__file__).resolve().parents[2] / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / 'main.log'
        
        fh = TimedRotatingFileHandler(
            str(log_file), when='midnight', interval=1,
            backupCount=8, encoding='utf-8', delay=True
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception as e:
        logger.warning(f"文件日志初始化失败: {e}")
    
    return logger
\`\`\`

**步骤 2：添加 /status 接口（详细运行状态）**
在 main.py 中添加：
\`\`\`python
@app.get("/status")
async def status():
    """详细系统状态（运维用）"""
    import os, psutil
    proc = psutil.Process(os.getpid()) if 'psutil' in sys.modules else None
    
    jobs = []
    for job in scheduler.get_jobs():
        next_run = str(job.next_run_time) if job.next_run_time else 'N/A'
        jobs.append({'id': job.id, 'next_run': next_run})
    
    # 数据库统计
    try:
        article_count = await db.count_articles()
        weibo_count = await db.count_weibo_events()
    except Exception:
        article_count = weibo_count = -1
    
    return {
        'version': 'V4.3',
        'time': datetime.now().isoformat(),
        'scheduler_jobs': jobs,
        'db': {'articles': article_count, 'weibo_events': weibo_count},
        'config': {
            'feishu': bool(FEISHU_WEBHOOK_URL),
            'email': bool(EMAIL_SENDER),
            'ai': bool(AI_API_KEY),
        }
    }
\`\`\`

**步骤 3：在 database.py 中添加 count_articles() 和 count_weibo_events()**
\`\`\`python
async def count_articles(self) -> int:
    async with aiosqlite.connect(self.db_path) as db:
        cur = await db.execute('SELECT COUNT(*) FROM articles')
        row = await cur.fetchone()
        return row[0] if row else 0

async def count_weibo_events(self) -> int:
    async with aiosqlite.connect(self.weibo_path) as db:
        cur = await db.execute('SELECT COUNT(*) FROM hotsearch_events')
        row = await cur.fetchone()
        return row[0] if row else 0
\`\`\`

请修改这三个文件并展示修改内容。`,
    verify: 'curl http://localhost:8001/status 返回包含 scheduler_jobs 和 db 信息的 JSON',
  },

  {
    id: 'ops-03',
    step: 16,
    category: 'ops',
    severity: 'medium',
    title: '一键诊断脚本',
    problem: '每次出问题不知道从哪里排查，需要一个快速检查工具',
    rootCause: '缺少自动化诊断工具，靠人工看日志太慢',
    files: ['system/services/diagnose.sh'],
    prompt: `请创建 system/services/diagnose.sh 一键诊断脚本。

创建文件 system/services/diagnose.sh，内容如下：
\`\`\`bash
#!/bin/bash
# weibo-hotsearch 一键诊断脚本
# 用法：bash system/services/diagnose.sh

cd /opt/weibo-hotsearch
VENV=./venv/bin/python

echo "========================================"
echo " weibo-hotsearch 系统诊断报告"
echo " $(date)"
echo "========================================"

# 1. 进程检查
echo ""
echo "【1】进程状态"
PID=$(pgrep -f "python system/main.py")
if [ -n "$PID" ]; then
    echo "  ✅ 服务运行中 PID=$PID"
    ps -p $PID -o pid,vsz,rss,pcpu,etime --no-headers | awk '{printf "  内存: %dMB | CPU: %s%% | 运行: %s\\n", $3/1024, $4, $5}'
else
    echo "  ❌ 服务未运行"
fi

# 2. 端口检查
echo ""
echo "【2】端口监听"
if ss -tlnp | grep -q ':8001'; then
    echo "  ✅ :8001 端口监听正常"
else
    echo "  ❌ :8001 端口未监听"
fi

# 3. API 健康检查
echo ""
echo "【3】API 健康检查"
RESP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/ 2>/dev/null)
if [ "$RESP" = "200" ]; then
    echo "  ✅ API 响应正常 (HTTP 200)"
else
    echo "  ❌ API 无响应或异常 (HTTP $RESP)"
fi

# 4. 数据库检查
echo ""
echo "【4】数据库状态"
for DB in data/v3_monitor.db data/v3_weibo.db; do
    if [ -f "$DB" ]; then
        echo "  ✅ $DB 存在"
    else
        echo "  ❌ $DB 不存在"
    fi
done

# 5. 环境变量检查
echo ""
echo "【5】环境变量检查"
source .env 2>/dev/null || true
[ -n "$FEISHU_WEBHOOK_URL" ] && echo "  ✅ FEISHU_WEBHOOK_URL 已配置" || echo "  ❌ FEISHU_WEBHOOK_URL 未配置"
[ -n "$AI_API_KEY" ] && echo "  ✅ AI_API_KEY 已配置" || echo "  ❌ AI_API_KEY 未配置"
[ -n "$EMAIL_SENDER" ] && echo "  ✅ EMAIL_SENDER 已配置" || echo "  ❌ EMAIL_SENDER 未配置"

# 6. 日志最后20行
echo ""
echo "【6】最新日志（最后20行）"
if [ -f "logs/main.log" ]; then
    tail -20 logs/main.log
else
    echo "  ⚠️ 日志文件不存在"
fi

# 7. 最近错误统计
echo ""
echo "【7】最近24小时错误统计"
if [ -f "logs/main.log" ]; then
    echo "  错误统计："
    grep -c "ERROR" logs/main.log 2>/dev/null
    grep -c "WARNING" logs/main.log 2>/dev/null
    echo "  最近错误："
    grep "ERROR" logs/main.log | tail -5
fi

echo ""
echo "========================================"
echo " 诊断完成"
echo "========================================"
\`\`\`

chmod +x system/services/diagnose.sh

然后在 README 的运维手册部分添加：
\`\`\`
# 一键诊断
bash system/services/diagnose.sh
\`\`\`

请创建这个文件并展示内容。`,
    verify: '运行 bash system/services/diagnose.sh 后看到完整的诊断输出',
  },
];
