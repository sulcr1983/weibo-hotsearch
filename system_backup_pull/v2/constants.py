"""系统常量 V5.0 — 重构版：统一从 sources.py 加载，移除硬编码回退"""
import os
import re

from v2.logger import get_logger

logger = get_logger('constants')

RSSHUB_HOST = os.getenv('RSSHUB_HOST', 'http://localhost:1200')

# ── 品牌配置 ──
BRAND_PATTERNS = {
    "小米汽车": ["小米汽车", "小米SU7", "小米YU7", "小米SU"],
    "鸿蒙智行": ["鸿蒙智行", "问界", "智界", "尊界", "享界", "尚界"],
    "零跑汽车": ["零跑汽车", "零跑"],
    "理想汽车": ["理想汽车", "理想", "理想L", "理想MEGA"],
    "蔚来汽车": ["蔚来汽车", "蔚来", "萤火虫", "乐道"],
    "极氪汽车": ["极氪汽车", "极氪", "极氪00"],
    "阿维塔": ["阿维塔"],
    "智己汽车": ["智己汽车", "智己"],
    "比亚迪": ["比亚迪", "仰望", "腾势", "方程豹"],
    "特斯拉": ["特斯拉", "Tesla", "Model Y", "Model 3", "Cybertruck"],
}

BRAND_REGEX = {brand: re.compile('|'.join(re.escape(kw) for kw in kws)) for brand, kws in BRAND_PATTERNS.items()}

BRAND_COLORS = {
    "小米汽车": "#FF6900", "鸿蒙智行": "#C0392B", "零跑汽车": "#27AE60",
    "理想汽车": "#2E86C1", "蔚来汽车": "#1ABC9C", "极氪汽车": "#F39C12",
    "阿维塔": "#8E44AD", "智己汽车": "#D35400", "比亚迪": "#16A085",
    "特斯拉": "#E74C3C",
}
DEFAULT_BRAND_COLOR = "#16213e"

SOURCE_LEVEL = {1: "国家级", 2: "财经/垂直", 3: "科技/新媒体"}

FETCH_TIMEOUT = 20
FETCH_RETRY = 2
FETCH_DELAY_MIN = 2
FETCH_DELAY_MAX = 5
CONTENT_MAX_LENGTH = 800

SIMHASH_BITS = 64
HAMMING_THRESHOLD = 20
EVENT_TIME_WINDOW_HOURS = 48
DATA_RETENTION_DAYS = 8
QUEUE_MAXSIZE = 500

# ── RSS/Web数据源 — 优先从 sources.py (YAML) 加载 ──
RSS_FEEDS = []
WEB_FEEDS = []
_rss_loaded = False
_web_loaded = False

try:
    from sources import get_rss_feeds, get_web_feeds
    RSS_FEEDS = get_rss_feeds()
    WEB_FEEDS = get_web_feeds()
    if RSS_FEEDS:
        _rss_loaded = True
    if WEB_FEEDS:
        _web_loaded = True
except ImportError as e:
    logger.warning(f"sources.py 导入失败, 使用空源列表: {e}")

if not RSS_FEEDS:
    logger.warning("RSS_FEEDS 为空 — 检查 sources/sources.yml")
if not WEB_FEEDS:
    logger.warning("WEB_FEEDS 为空 — 检查 sources/sources.yml")