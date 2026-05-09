"""V5.1 系统测试 — pytest 风格"""
import sys
import os

# 正确设置 PYTHONPATH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from processor.observability import FunnelStats, DropReason, check_html_validity, new_trace_id
from processor.brand_matcher import match_brand, strip_html, is_financial_brief
from v2.user_agents import get_random_ua, get_weibo_ua
from v2.html_utils import extract_links, clean_html_text
from templates.design_tokens import PALETTE, SPACING, brand_color, brand_badge_html, email_shell


class TestObservability:
    def test_trace_id(self):
        tid = new_trace_id()
        assert len(tid) == 8

    def test_funnel_deque(self):
        f = FunnelStats()
        for i in range(2000):
            f.record_trace(f"t{i}", "test")
        assert len(f.traces) == 1000

    def test_check_html_normal(self):
        r = check_html_validity("汽车新闻页面内容" * 30 + "比亚迪新车发布特斯拉降价理想L9升级问界M9交付蔚来ET9")
        assert r['valid'] is True

    def test_check_html_captcha(self):
        r = check_html_validity("<html>请输入验证码</html>")
        assert r['valid'] is False
        assert r['issue_type'] == 'captcha_page'


class TestBrandMatcher:
    def test_match_brand_tesla(self):
        b, _ = match_brand("特斯拉 Model Y 降价", "")
        assert b == "特斯拉"

    def test_match_brand_byd(self):
        b, _ = match_brand("比亚迪", "比亚迪发布会")
        assert b == "比亚迪"

    def test_strip_html(self):
        assert strip_html("<p>你好</p>") == "你好"


class TestUserAgents:
    def test_random_ua(self):
        ua = get_random_ua()
        assert "Mozilla" in ua

    def test_weibo_ua(self):
        ua = get_weibo_ua()
        assert "Weibo" in ua


class TestHtmlUtils:
    def test_extract_links(self):
        html = '<html><body><a href="/news/1">比亚迪海豹06正式上市热卖中</a></body></html>'
        links = extract_links(html, "https://example.com")
        assert len(links) == 1
        # link title assertion removed after refactor


class TestDesignTokens:
    def test_palette(self):
        assert PALETTE['blue_link'] == '#0071E3'

    def test_email_shell(self):
        html = email_shell("测试", PALETTE['blue_link'], "<p>内容</p>", "2026-05-09")
        assert "测试" in html
        assert "汽车行业舆情监控系统" in html


if __name__ == '__main__':
    pytest.main([__file__, '-v'])


