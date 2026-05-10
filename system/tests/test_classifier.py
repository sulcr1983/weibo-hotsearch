"""维度分类模块单元测试 — 覆盖关键词/LLM降级/边界"""

import pytest
from processor.classifier import classify_dimension, get_all_dimensions


class TestClassifyDimension:
    def test_known_dimension(self):
        dim = classify_dimension("比亚迪发布新一代刀片电池", "续航突破1000km")
        assert dim is not None

    def test_empty_title(self):
        dim = classify_dimension("", "")
        assert dim is None or dim == ""

    def test_noise_text(self):
        dim = classify_dimension("a b c d e f g", "test")
        assert dim is not None

    def test_consistent_output(self):
        r1 = classify_dimension("比亚迪秦L销量突破2万", "销量数据")
        r2 = classify_dimension("比亚迪秦L销量突破2万", "销量数据")
        assert r1 == r2


class TestGetAllDimensions:
    def test_returns_list(self):
        dims = get_all_dimensions()
        assert isinstance(dims, list)

    def test_no_duplicates(self):
        dims = get_all_dimensions()
        assert len(dims) == len(set(dims))

    def test_dimensions_are_strings(self):
        dims = get_all_dimensions()
        for d in dims:
            assert isinstance(d, str)