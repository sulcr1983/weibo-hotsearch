"""weibo-hotsearch 测试装置：共享 Fixtures + Mock 工厂"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import AsyncGenerator

import aiosqlite
import pytest
import pytest_asyncio

# ── 将项目根加入 sys.path，使测试可导入 system 包 ──
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / 'system') not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / 'system'))


# ── 环境变量固化：测试永不碰真实网络/凭据 ──
@pytest.fixture(autouse=True)
def _isolate_env():
    saved = {}
    for k in ('FEISHU_WEBHOOK_URL', 'AI_API_KEY', 'AI_API_URL', 'AI_MODEL',
              'EMAIL_SENDER', 'EMAIL_PASSWORD', 'EMAIL_RECIPIENTS',
              'SMTP_SERVER', 'SMTP_PORT', 'DB_PATH', 'WEIBO_DB_PATH',
              'RSSHUB_HOST', 'SSH_HOST', 'SSH_USER', 'SSH_PASSWORD'):
        saved[k] = os.environ.get(k)
    os.environ.update({
        'FEISHU_WEBHOOK_URL': '',
        'AI_API_KEY': '',
        'AI_API_URL': 'https://api.deepseek.com/chat/completions',
        'AI_MODEL': 'deepseek-chat',
        'EMAIL_SENDER': '',
        'EMAIL_PASSWORD': '',
        'EMAIL_RECIPIENTS': '',
        'RSSHUB_HOST': 'http://localhost:1200',
    })
    yield
    for k in saved:
        if saved[k] is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = saved[k]


@pytest.fixture
def sample_article_html() -> str:
    return """<!DOCTYPE html>
<html><head><title>比亚迪秦L DM-i 上市首月销量突破2万辆</title></head>
<body>
  <article>
    <h1>比亚迪秦L DM-i 上市首月销量突破2万辆</h1>
    <div class="meta">
      <span class="source">新浪汽车</span>
      <time>2026-04-15 10:30</time>
    </div>
    <div class="content">
      <p>据比亚迪官方消息，秦L DM-i 上市首月销量突破2万辆，成为中级轿车市场黑马。</p>
      <p>新车搭载第五代 DM 混动技术，亏电油耗低至 2.9L/100km，综合续航超 2000km。</p>
      <p>比亚迪王朝网销售事业部总经理透露，目前秦L DM-i 订单已超过5万辆，产能正在爬坡。</p>
    </div>
  </article>
</body></html>"""


@pytest.fixture
def sample_weibo_response() -> dict:
    return {
        "ok": 1,
        "data": {
            "realtime": [
                {"word": "比亚迪秦L销量", "raw_hot": 2580000, "category": "汽车",
                 "icon_desc": "新", "label_name": "热门"},
                {"word": "小米SU7产能提升", "raw_hot": 1890000, "category": "汽车",
                 "icon_desc": "沸", "label_name": "热议"},
                {"word": "华为问界M9 OTA升级", "raw_hot": 1450000, "category": "科技"},
                {"word": "理想L6交付破万", "raw_hot": 2100000, "category": "汽车"},
                {"word": "特斯拉FSD入华进展", "raw_hot": 3200000, "category": "科技"},
                {"word": "蔚来换电站布局", "raw_hot": 820000, "category": "汽车"},
            ]
        }
    }


@pytest.fixture
def sample_weibo_html() -> str:
    return """<html><head><meta charset="utf-8"/></head><body>
<table class="s-table">
  <tbody>
    <tr><td class="td-02"><a href="javascript:void(0);" target="_blank">比亚迪秦L销量</a><span>2580000</span></td></tr>
    <tr><td class="td-02"><a href="javascript:void(0);" target="_blank">小米SU7产能提升</a><span>1890000</span></td></tr>
    <tr><td class="td-02"><a href="javascript:void(0);" target="_blank">华为问界M9 OTA升级</a><span>1450000</span></td></tr>
  </tbody>
</table>
</body></html>"""


@pytest.fixture
def article_record() -> dict:
    return {
        'url_hash': 'a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6',
        'title': '比亚迪秦L DM-i 上市首月销量突破2万辆',
        'url': 'https://auto.sina.com.cn/news/2026-04-15/detail-123.html',
        'source': '新浪汽车',
        'source_level': 1,
        'brand': '比亚迪',
        'keywords': json.dumps(['比亚迪', '秦L', 'DM-i', '销量'], ensure_ascii=False),
        'content': '比亚迪秦L DM-i 上市首月销量突破2万辆',
        'simhash': '1234567890abcdef1234567890abcdef',
        'event_id': 'byd_qinl_202604',
        'summary': None,
        'score': 85,
        'score_tier': 'strong',
        'is_pushed': 0,
        'created_at': '2026-04-15 10:30:00',
    }


@pytest.fixture
def edge_case_texts() -> dict:
    return {
        'empty': '',
        'whitespace': '   \t\n  ',
        'special_chars': '<script>alert("xss")</script> &nbsp; © ® ™ 🚗',
        'long_text': '比亚迪 ' * 5000,
        'mixed_lang': 'BYD秦L DM-i 2026 上市！test@auto.com #销量',
        'malformed_html': '<div><p>未闭合标签<span>内容</div>',
        'no_brand': '今日天气晴朗，适合出行',
    }


@pytest_asyncio.fixture
async def in_memory_db():
    tmp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    tmp_weibo = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    tmp_db.close()
    tmp_weibo.close()

    from storage.database import Database
    db = Database(tmp_db.name, tmp_weibo.name)
    await db.start()
    yield db
    await db.stop()

    os.unlink(tmp_db.name)
    os.unlink(tmp_weibo.name)


@pytest.fixture
def mock_session():
    from unittest.mock import AsyncMock

    class MockSession:
        def __init__(self, html='<html><body>mock</body></html>'):
            self._html = html
            self.fetch = AsyncMock(return_value=html)
            self.fetch_with_cc = AsyncMock(return_value=html)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    return MockSession


@pytest.fixture
def cassettes_dir() -> Path:
    d = PROJECT_ROOT / 'system' / 'tests' / 'cassettes'
    d.mkdir(parents=True, exist_ok=True)
    return d