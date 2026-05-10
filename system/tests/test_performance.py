"""性能基准测试模板（pytest-benchmark）

用法:
  pytest system/tests/test_performance.py --benchmark-only
  pytest system/tests/test_performance.py --benchmark-histogram=benchmarks
"""

import gc
import time
import pytest

pytestmark = pytest.mark.performance

_has_benchmark = False
try:
    pytest.importorskip("pytest_benchmark")
    _has_benchmark = True
except (ImportError, pytest.skip.Exception):
    pass


def _make_articles(n: int) -> list:
    brands = ['比亚迪', '特斯拉', '小米', '华为', '理想', '蔚来', '小鹏', '极氪']
    articles = []
    for i in range(n):
        brand = brands[i % len(brands)]
        articles.append({
            'title': f'{brand} 测试文章标题 {i}：新车发布及市场分析',
            'content': ' '.join([f'{brand}最新动态'] * 50),
            'source': '新浪汽车',
            'source_level': 1,
            'brand': brand,
        })
    return articles


class TestBrandMatcherBenchmark:
    def test_brand_match_throughput(self, benchmark):
        articles = _make_articles(1000)
        from processor.brand_matcher import match_brand

        def run():
            for a in articles:
                match_brand(a['title'], a['content'])

        benchmark(run)

    def test_strip_html_throughput(self, benchmark):
        html_pieces = [
            '<p>比亚迪秦L</p>' * 100,
            '<div><b>特斯拉</b>FSD</div>' * 100,
            '<article><h1>小米SU7</h1><p>产能提升</p></article>' * 100,
        ] * 10
        from processor.brand_matcher import strip_html

        def run():
            for h in html_pieces:
                strip_html(h)

        benchmark(run)


class TestScoringBenchmark:
    def test_score_calculation(self, benchmark):
        articles = _make_articles(500)
        from processor.scoring import calc_article_score

        def run():
            for a in articles:
                calc_article_score(
                    a['title'], a['content'], a['source'],
                    brand_hit_title=True, source_level=a['source_level'],
                )

        benchmark(run)


class TestSimhashBenchmark:
    def test_simhash_compute(self, benchmark):
        articles = _make_articles(500)
        from processor.deduplicator import compute_simhash

        def run():
            for a in articles:
                compute_simhash(a['title'] + ' ' + a['content'][:300])

        benchmark(run)


class TestMemoryUsage:
    def test_brand_matcher_memory(self):
        from processor.brand_matcher import match_brand

        gc.collect()
        before = len(gc.get_objects())

        for i in range(1000):
            match_brand(f"比亚迪测试文章标题 {i}", "")

        gc.collect()
        after = len(gc.get_objects())

        leaked = after - before
        assert leaked < 2000, f"疑似对象泄漏: {leaked} objects"


class TestConcurrencyPattern:
    @pytest.mark.asyncio
    async def test_db_queue_not_blocking(self, in_memory_db):
        start = time.perf_counter()
        for i in range(20):
            in_memory_db.enqueue('insert_article', {
                'url_hash': f'perf_hash_{i}',
                'title': f'测试 {i}', 'url': f'http://test/{i}',
                'source': 'test', 'brand': 'test',
                'created_at': '2026-01-01 00:00:00',
            })
        elapsed = time.perf_counter() - start
        assert elapsed < 5.0, f"enqueue 20 条耗时 {elapsed:.2f}s"
        assert in_memory_db.queue_size <= 500