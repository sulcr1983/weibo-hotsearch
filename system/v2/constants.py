import os
import re

BRAND_PATTERNS = {
    "小米汽车": ["小米汽车", "小米SU7", "小米SU", "小米YU7", "雷军"],
    "鸿蒙智行": ["问界", "智界", "尊界", "享界", "尚界", "鸿蒙智行", "余承东"],
    "零跑汽车": ["零跑", "零跑C"],
    "理想汽车": ["理想汽车", "理想L", "理想MEGA", "理想i", "理想ONE"],
    "蔚来汽车": ["蔚来", "萤火虫", "乐道", "李斌"],
    "极氪汽车": ["极氪", "极氪00"],
    "阿维塔": ["阿维塔"],
    "智己汽车": ["智己", "智己L"],
    "比亚迪": ["比亚迪", "仰望", "腾势", "方程豹", "王传福"],
    "特斯拉": ["特斯拉", "Tesla", "Model Y", "Model 3", "Cybertruck", "FSD", "马斯克"],
}

BRAND_REGEX = {}
for brand_group, keywords in BRAND_PATTERNS.items():
    pattern = "|".join([re.escape(kw) for kw in keywords])
    BRAND_REGEX[brand_group] = re.compile(pattern, re.IGNORECASE)

BRAND_COLORS = {
    "小米汽车": "#FF6900",
    "鸿蒙智行": "#CE0E2D",
    "零跑汽车": "#0052D9",
    "理想汽车": "#4A90D9",
    "蔚来汽车": "#2E6BE6",
    "极氪汽车": "#00B2A9",
    "阿维塔": "#6C5CE7",
    "智己汽车": "#E84393",
    "比亚迪": "#C0392B",
    "特斯拉": "#E74C3C",
}

DEFAULT_BRAND_COLOR = "#16213e"

SOURCE_LEVEL = {
    "新华网": 1, "央视新闻": 1, "人民网": 1, "中国新闻网": 1, "央视网": 1,
    "凤凰网": 2, "澎湃新闻": 2, "财新": 2, "华尔街见闻": 2,
    "第一财经": 2, "财联社": 2,
    "懂车帝": 2, "新浪汽车": 2, "搜狐汽车": 2,
    "网易汽车": 2, "盖世汽车": 2, "第一电动": 2,
    "中国汽车报": 1,
    "搜狐新闻": 3, "36氪": 3, "钛媒体": 3,
    "虎嗅": 3, "知乎": 3,
}

RSSHUB_HOST = os.environ.get('RSSHUB_HOST', 'http://localhost:1200')

# ── 从 YAML 加载（V4.0），fallback 到硬编码 ──
try:
    from sources import get_rss_feeds, get_web_feeds
    RSS_FEEDS = get_rss_feeds() or [
        {"name": "36氪", "url": "https://36kr.com/feed", "level": 3},
        {"name": "钛媒体", "url": "https://www.tmtpost.com/feed", "level": 3},
        {"name": "第一财经快讯", "url": f"{RSSHUB_HOST}/yicai/brief", "level": 2},
        {"name": "虎嗅", "url": f"{RSSHUB_HOST}/huxiu/article", "level": 3},
        {"name": "知乎日报", "url": f"{RSSHUB_HOST}/zhihu/daily", "level": 3},
        {"name": "36氪快讯", "url": f"{RSSHUB_HOST}/36kr/newsflashes", "level": 3},
        {"name": "财联社深度", "url": f"{RSSHUB_HOST}/cls/depth", "level": 2},
        {"name": "财联社热门", "url": f"{RSSHUB_HOST}/cls/hot", "level": 2},
        {"name": "澎湃新闻精选", "url": f"{RSSHUB_HOST}/thepaper/featured", "level": 2},
        {"name": "财新最新", "url": f"{RSSHUB_HOST}/caixin/latest", "level": 2},
        {"name": "华尔街见闻", "url": f"{RSSHUB_HOST}/wallstreetcn/news/global", "level": 2},
    ]
    WEB_FEEDS = get_web_feeds() or []
except ImportError:
    pass

RSS_FEEDS = RSS_FEEDS if 'RSS_FEEDS' in dir() else []
WEB_FEEDS = WEB_FEEDS if 'WEB_FEEDS' in dir() else []

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
