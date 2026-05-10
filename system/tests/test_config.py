"""配置加载模块单元测试 — 覆盖环境变量/默认值回退/YAML 加载"""

import os
import importlib
import pytest


class TestConfigDefaults:
    def test_db_path_default(self):
        from config import DB_PATH
        assert DB_PATH.endswith('.db')
        assert 'data' in DB_PATH or 'v3' in DB_PATH

    def test_weibo_db_path_default(self):
        from config import WEIBO_DB_PATH
        assert WEIBO_DB_PATH.endswith('.db')
        assert 'weibo' in WEIBO_DB_PATH.lower()

    def test_ai_api_url_default(self):
        from config import AI_API_URL
        assert AI_API_URL.startswith('http')

    def test_ai_model_default(self):
        from config import AI_MODEL
        assert isinstance(AI_MODEL, str) and len(AI_MODEL) > 0

    def test_feishu_webhook_default_empty(self):
        from config import FEISHU_WEBHOOK_URL
        assert FEISHU_WEBHOOK_URL == ''

    def test_email_sender_default_empty(self):
        from config import EMAIL_SENDER
        assert EMAIL_SENDER == ''

    def test_smtp_defaults(self):
        from config import SMTP_SERVER, SMTP_PORT
        assert isinstance(SMTP_SERVER, str)
        assert isinstance(SMTP_PORT, int)
        assert SMTP_PORT > 0

    def test_retention_days_positive(self):
        from config import NEWS_RETENTION_DAYS, WEIBO_RETENTION_DAYS
        assert NEWS_RETENTION_DAYS > 0
        assert WEIBO_RETENTION_DAYS > 0

    def test_email_recipients_default_empty(self):
        from config import EMAIL_RECIPIENTS
        assert EMAIL_RECIPIENTS == []


class TestConfigEnvOverride:
    def test_db_path_override(self, monkeypatch):
        monkeypatch.setenv('DB_PATH', 'custom_test.db')
        importlib.reload(__import__('config'))
        from config import DB_PATH
        assert DB_PATH.endswith('custom_test.db')

    def test_ai_url_override(self, monkeypatch):
        monkeypatch.setenv('AI_API_URL', 'https://custom.api.com/v1')
        importlib.reload(__import__('config'))
        from config import AI_API_URL
        assert 'custom.api.com' in AI_API_URL

    def test_smtp_port_override(self, monkeypatch):
        monkeypatch.setenv('SMTP_PORT', '465')
        importlib.reload(__import__('config'))
        from config import SMTP_PORT
        assert SMTP_PORT == 465


class TestSourcesConfig:
    def test_sources_yml_exists(self):
        from pathlib import Path
        cfg = Path(__file__).resolve().parents[1] / 'sources' / 'sources.yml'
        assert cfg.exists(), f"sources.yml 不存在: {cfg}"

    def test_rsshub_host_default(self):
        from sources import RSSHUB_HOST
        assert RSSHUB_HOST.startswith('http')

    def test_get_rss_feeds_returns_list(self):
        from sources import get_rss_feeds
        feeds = get_rss_feeds()
        assert isinstance(feeds, list)

    def test_feed_has_required_keys(self):
        from sources import get_rss_feeds
        for feed in get_rss_feeds()[:3]:
            assert 'name' in feed
            assert 'url' in feed
            assert 'level' in feed

    def test_auto_feeds_loaded(self):
        from sources import get_auto_feeds
        feeds = get_auto_feeds()
        assert isinstance(feeds, list)
        if feeds:
            assert 'name' in feeds[0]