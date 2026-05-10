"""品牌匹配模块单元测试 — 覆盖匹配/过滤/边界"""

import pytest
from processor.brand_matcher import (
    match_brand, strip_html,
    is_financial_brief, is_digest, is_ugc, is_opinion,
    _is_chinese, _is_all_chinese,
)


class TestStripHtml:
    def test_remove_tags(self):
        assert strip_html("<p>比亚迪</p>") == "比亚迪"

    def test_nested_tags(self):
        assert strip_html("<div><b>秦L</b> DM-i</div>") == "秦L DM-i"

    def test_empty_input(self):
        assert strip_html("") == ""

    def test_whitespace_only(self):
        assert strip_html("   ") == ""

    def test_malformed_html(self, edge_case_texts):
        r = strip_html(edge_case_texts['malformed_html'])
        assert "未闭合标签" in r


class TestMatchBrand:
    BRAND_TESTS = [
        ("比亚迪秦L销量突破2万", "比亚迪"),
        ("特斯拉FSD入华", "特斯拉"),
        ("华为问界M9 OTA升级", "鸿蒙智行"),
        ("理想L6交付破万", "理想汽车"),
        ("蔚来换电站第3000座上线", "蔚来汽车"),
        ("极氪001推送OS 6.0", "极氪汽车"),
        ("零跑C16上市", "零跑汽车"),
        ("小米SU7产能提升", "小米汽车"),
        ("智己L6发布", "智己汽车"),
    ]

    @pytest.mark.parametrize("title,expected_brand", BRAND_TESTS)
    def test_brand_match(self, title, expected_brand):
        brand, kw = match_brand(title, "")
        assert brand == expected_brand, f"[{title}] 期望={expected_brand}, 实际={brand}"

    def test_no_brand_no_match(self):
        brand, _ = match_brand("今日天气晴朗，适合出行", "")
        assert brand is None

    def test_brand_in_content_fallback(self):
        brand, _ = match_brand("重磅新车上市", "本文来自比亚迪官方")
        assert brand == "比亚迪"

    def test_unknown_brand_returns_none(self):
        brand, _ = match_brand("小鹏MONA M03上市", "")
        assert brand is None, "小鹏未在 BRAND_PATTERNS 中，应返回 None"

    def test_empty_input_returns_none(self):
        brand, _ = match_brand("", "")
        assert brand is None


class TestContentFilters:
    def test_financial_brief_match(self):
        assert is_financial_brief("比亚迪涨超5%", "港股恒指收盘大涨") is True

    def test_financial_brief_normal_article(self):
        assert is_financial_brief("比亚迪秦L销量突破2万辆", "新浪汽车") in (False, None)

    def test_digest_match(self):
        assert is_digest("一周车闻：比亚迪销量汇总") is True

    def test_digest_normal_title(self):
        assert is_digest("比亚迪秦L DM-i 深度测评") is False

    def test_digest_weekly(self):
        assert is_digest("【新闻精选】理想汽车一周盘点") is True

    def test_ugc_news_article(self):
        assert is_ugc("比亚迪秦L DM-i 正式上市，售价9.98万起") is False


class TestChineseUtils:
    def test_is_chinese(self):
        assert _is_chinese('比') is True
        assert _is_chinese('a') is False
        assert _is_chinese('1') is False

    def test_is_all_chinese(self):
        assert _is_all_chinese("比亚迪") is True
        assert _is_all_chinese("比亚迪BYD") is False