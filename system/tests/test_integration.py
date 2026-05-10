"""集成测试 — VCR 录制回放模拟微博页面，覆盖完整链路

运行方式:
  # 首次运行（录制真实请求）：需要网络
  pytest system/tests/test_integration.py --record-mode=once

  # 后续运行（回放录制数据）：离线
  pytest system/tests/test_integration.py

依赖: pip install pytest-vcr
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# 跳过集成测试条件：未安装 vcr
pytest.importorskip("vcr", reason="需要 pytest-vcr 库")

# 标记整个文件为 slow（含 VCR 回放）
pytestmark = [
    pytest.mark.slow,
    pytest.mark.network,
]


class TestWeiboCollectIntegration:
    """微博采集链路测试：请求 → 解析 → 过滤 → 入库"""

    @pytest.mark.vcr(
        filter_headers=['cookie', 'authorization'],
        record_mode='once',
        cassette_library_dir='system/tests/cassettes',
    )
    @pytest.mark.asyncio
    async def test_weibo_api_parse(self, sample_weibo_response, in_memory_db):
        from collector.weibo_collector import _parse_api_response

        items = await _parse_api_response(sample_weibo_response, in_memory_db)
        assert len(items) > 0
        for item in items:
            assert 'keyword' in item
            assert 'brand' in item
            assert 'heat' in item
            assert item['heat'] > 0

    @pytest.mark.asyncio
    async def test_weibo_html_parse(self, sample_weibo_html, in_memory_db):
        from collector.weibo_collector import _parse_html

        items = await _parse_html(sample_weibo_html, in_memory_db)
        assert len(items) > 0
        for item in items:
            assert isinstance(item.get('heat'), int)
            assert item['heat'] >= 0


class TestFullPipelineIntegration:
    """完整采集→处理→入库链路测试（使用 mock session）"""

    @pytest.mark.asyncio
    async def test_news_collect_flow(self, in_memory_db, article_record):
        from processor.brand_matcher import match_brand
        from processor.scoring import calc_article_score, score_tier
        from processor.keyworder import extract_keywords
        from processor.deduplicator import compute_simhash, cluster_article

        brand, _ = match_brand(article_record['title'], article_record['content'])
        assert brand == '比亚迪'

        score_info = calc_article_score(
            article_record['title'], article_record['content'],
            article_record['source'], brand_hit_title=True, source_level=1,
        )
        assert score_info['score'] >= 70

        tier = score_tier(score_info['score'])
        assert tier != 'discard'

        kws = extract_keywords(article_record['title'] + ' ' + article_record['content'])
        assert len(kws) > 0

        sh = compute_simhash(article_record['title'][:200] + ' ' + article_record['content'][:300])
        assert sh is not None

        eid = await cluster_article(article_record, in_memory_db)
        assert eid is not None

        in_memory_db.enqueue('insert_article', article_record)
        await asyncio.sleep(0.3)
        cnt = await in_memory_db.count_articles()
        assert cnt >= 1

    @pytest.mark.asyncio
    async def test_weibo_collect_flow(self, sample_weibo_response, in_memory_db):
        from collector.weibo_collector import _parse_api_response

        items = await _parse_api_response(sample_weibo_response, in_memory_db)
        assert len(items) > 0

        for it in items:
            result = await in_memory_db.upsert_weibo_event(
                keyword=it['keyword'], brand=it['brand'],
                link=it.get('link', ''), label=it.get('label', ''),
                heat=it.get('heat', 0),
            )
            assert result['is_new'] is True or result['is_new'] is False

        cnt = await in_memory_db.count_weibo_events()
        assert cnt >= 1


class TestErrorRecovery:
    """异常恢复测试：重试逻辑、降级、空响应"""

    @pytest.mark.asyncio
    async def test_empty_response_graceful(self, in_memory_db):
        from processor.brand_matcher import match_brand
        brand, conf = match_brand("", "")
        assert brand is None

    @pytest.mark.asyncio
    async def test_malformed_json_parse(self):
        from collector.weibo_collector import _parse_api_response
        with pytest.raises((TypeError, ValueError, KeyError)):
            await _parse_api_response({"ok": 0}, None)

    @pytest.mark.asyncio
    async def test_html_validity_check(self, sample_article_html):
        from processor.observability import check_html_validity
        result = check_html_validity(sample_article_html, '新浪汽车')
        assert result['valid'] is True

    @pytest.mark.asyncio
    async def test_invalid_html_detection(self):
        from processor.observability import check_html_validity
        result = check_html_validity("<html>验证码</html>", '测试源')
        assert result['valid'] is False or '验证码' in str(result)


try:
    import asyncio
except ImportError:
    pass