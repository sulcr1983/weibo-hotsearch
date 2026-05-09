"""数据源配置加载器 V5.0 — 修复路径 + 添加缺失函数 + RSSHUB_HOST替换"""
import os
import yaml
from pathlib import Path
from typing import List, Dict, Any

from v2.logger import get_logger

logger = get_logger('sources')

# RSSHub 主机地址
RSSHUB_HOST = os.getenv('RSSHUB_HOST', 'http://localhost:1200')


def _get_config() -> dict:
    config_path = Path(__file__).parent / "sources" / "sources.yml"
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                raw = f.read()
            # 替换 {RSSHUB_HOST} 占位符
            raw = raw.replace('{RSSHUB_HOST}', RSSHUB_HOST)
            return yaml.safe_load(raw) or {}
        except Exception as e:
            logger.warning(f"加载 sources.yml 失败: {e}")
    return {}


def _build_feeds(sources_key: str) -> list:
    cfg = _get_config()
    sources = cfg.get(sources_key, [])
    feeds = []
    for source in sources:
        feed = {
            'name': source.get('name', 'unknown'),
            'url': source.get('url', source.get('feed_url', '')),
            'level': source.get('level', 3),
            'max_items': source.get('max_items', 20),
            'selectors': source.get('selectors', {}),
        }
        feeds.append(feed)
    return feeds


def get_rss_feeds() -> List[Dict[str, Any]]:
    return _build_feeds('rss_feeds')


def get_web_feeds() -> List[Dict[str, Any]]:
    return _build_feeds('web_feeds')


def get_playwright_feeds() -> List[Dict[str, Any]]:
    return _build_feeds('playwright_sources')


def get_auto_feeds() -> List[Dict[str, Any]]:
    return _build_feeds('auto_sources')