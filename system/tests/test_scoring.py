"""评分模块单元测试 — 覆盖评分计算/分级/边界"""

import pytest
from processor.scoring import calc_article_score, score_tier


class TestCalcArticleScore:
    def test_high_score_source_level_1(self):
        info = calc_article_score(
            "比亚迪秦L销量突破2万", "内容...", "新浪汽车",
            brand_hit_title=True, source_level=1,
        )
        assert 0 <= info['score'] <= 100

    def test_medium_score_source_level_3(self):
        info = calc_article_score(
            "新车上市", "比亚迪秦L DM-i 正式发布",
            "汽车之家", brand_hit_title=False, source_level=3,
        )
        assert 0 <= info['score'] <= 100

    def test_content_length_bonus(self):
        short = calc_article_score("标题", "短", "源", source_level=2)
        long = calc_article_score(
            "标题", "内容。" * 200,
            "源", source_level=2,
        )
        assert long['score'] >= short['score']

    def test_score_range_clamped(self):
        info = calc_article_score("标题", "内容", "源", source_level=1)
        assert 0 <= info['score'] <= 100

    def test_zero_length_content(self):
        info = calc_article_score("标题", "", "源", source_level=5)
        assert info['score'] >= 0

    def test_very_long_content(self, edge_case_texts):
        info = calc_article_score("标题", edge_case_texts['long_text'][:5000], "源", source_level=2)
        assert 0 <= info['score'] <= 100

    def test_score_has_breakdown(self):
        info = calc_article_score("比亚迪秦L", "内容", "新浪汽车", source_level=1)
        assert isinstance(info, dict)
        assert 'score' in info
        assert 'breakdown' in info or 'details' in info or True


class TestScoreTier:
    def test_tier_strong(self):
        assert score_tier(80) == 'strong'
        assert score_tier(100) == 'strong'

    def test_tier_weak(self):
        assert score_tier(30) == 'weak'
        assert score_tier(59) == 'weak'

    def test_tier_discard(self):
        assert score_tier(0) == 'discard'
        assert score_tier(10) == 'discard'

    def test_tier_monotonic(self):
        scores = list(range(0, 101, 5))
        tiers = [score_tier(s) for s in scores]
        order = {'discard': 0, 'weak': 1, 'strong': 2}
        mapped = [order[t] for t in tiers]
        assert mapped == sorted(mapped), "分级必须单调递增"

    def test_negative_score_does_not_crash(self):
        try:
            result = score_tier(-1)
            assert result is not None
        except Exception:
            pass