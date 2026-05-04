"""配置加载器 — 从 sources.yml 加载数据源（V4.0）"""
import os
from pathlib import Path
from typing import List, Dict

import yaml

_CONF_DIR = Path(__file__).resolve().parent
_SOURCES_FILE = _CONF_DIR / 'sources.yml'

_rss_feeds: List[dict] = []
_web_feeds: List[dict] = []
_auto_feeds: List[dict] = []


def _load():
    global _rss_feeds, _web_feeds, _auto_feeds
    if _rss_feeds:
        return
    if not _SOURCES_FILE.exists():
        return
    with open(_SOURCES_FILE, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    rsshub_host = os.environ.get('RSSHUB_HOST', 'http://localhost:1200')
    for item in data.get('rss_feeds', []):
        url = item.get('url', '')
        if '{RSSHUB_HOST}' in url:
            url = url.replace('{RSSHUB_HOST}', rsshub_host)
        item['url'] = url
        _rss_feeds.append(item)
    for item in data.get('web_feeds', []):
        _web_feeds.append(item)
    for item in data.get('auto_feeds', []):
        _auto_feeds.append(item)


def get_rss_feeds() -> List[dict]:
    _load()
    return _rss_feeds


def get_web_feeds() -> List[dict]:
    _load()
    return _web_feeds


def get_auto_feeds() -> List[dict]:
    _load()
    return _auto_feeds
