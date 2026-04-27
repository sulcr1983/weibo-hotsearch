import os
import re

BRAND_PATTERNS = {
    "小米汽车": ["小米汽车"],
    "鸿蒙智行": ["问界", "智界", "尊界", "享界", "尚界"],
    "零跑汽车": ["零跑"],
    "理想汽车": ["理想"],
    "蔚来汽车": ["蔚来", "萤火虫", "乐道"],
    "极氪汽车": ["极氪"],
    "阿维塔": ["阿维塔"],
    "智己汽车": ["智己"],
    "比亚迪": ["比亚迪", "仰望", "腾势", "方程豹"],
    "特斯拉": ["特斯拉"],
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

SOURCE_LEVEL = {
    "新华网": 1, "央视新闻": 1, "人民网": 1, "中国新闻网": 1,
    "凤凰网汽车": 2, "盖世汽车": 2, "汽车之家": 2, "懂车帝": 2,
    "界面新闻": 2, "第一财经": 2, "36氪": 3, "钛媒体": 3,
}

RSSHUB_HOST = os.environ.get('RSSHUB_HOST', 'http://localhost:1200')

RSS_FEEDS = [
    {"name": "凤凰网汽车", "url": "http://auto.ifeng.com/rss/headnews.xml", "level": 2},
    {"name": "盖世汽车行业", "url": "https://cn.gasgoo.com/rss/Industry", "level": 2},
    {"name": "盖世汽车新车", "url": "https://cn.gasgoo.com/rss/NewCar", "level": 2},
    {"name": "36氪汽车", "url": "https://36kr.com/feed", "level": 3},
    {"name": "汽车之家", "url": f"{RSSHUB_HOST}/autohome/news", "level": 2, "rsshub": True},
    {"name": "汽车之家精选", "url": f"{RSSHUB_HOST}/autohome/best", "level": 2, "rsshub": True},
    {"name": "懂车帝", "url": f"{RSSHUB_HOST}/dongchedi/hot", "level": 2, "rsshub": True},
    {"name": "新华网汽车", "url": f"{RSSHUB_HOST}/xinhuanet/auto", "level": 1, "rsshub": True},
    {"name": "央视新闻", "url": f"{RSSHUB_HOST}/cctv/xwlb", "level": 1, "rsshub": True},
    {"name": "界面新闻", "url": f"{RSSHUB_HOST}/jiemian/list", "level": 2, "rsshub": True},
    {"name": "第一财经", "url": f"{RSSHUB_HOST}/yicai/brief", "level": 2, "rsshub": True},
]

FETCH_TIMEOUT = 15
FETCH_RETRY = 2
FETCH_DELAY_MIN = 2
FETCH_DELAY_MAX = 5

CONTENT_MAX_LENGTH = 800
SIMHASH_BITS = 64
HAMMING_THRESHOLD = 3
EVENT_TIME_WINDOW_HOURS = 48

DATA_RETENTION_DAYS = 8
QUEUE_MAXSIZE = 500
