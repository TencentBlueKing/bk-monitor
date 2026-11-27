import re

import pytest

from bkmonitor.space.pinyin import pinyin_search_codepoints
from bkmonitor.space.pinyin_mysql5 import pinyin_hex_search_patterns


@pytest.mark.parametrize("query", ["ljys", "zhongqing", "abclj", "a"])
def test_every_possible_reading_survives_gb2312_prefilter(query):
    groups = pinyin_search_codepoints(query)
    patterns = pinyin_hex_search_patterns(query)
    assert len(patterns) == len(groups)
    for points, hex_pattern in zip(groups, patterns):
        expression = re.compile(bytes.fromhex(hex_pattern))
        assert all(expression.search(chr(point).encode("gb2312", "replace")) for point in points)


def test_character_boundaries_and_lossy_names():
    expressions = [re.compile(bytes.fromhex(pattern)) for pattern in pinyin_hex_search_patterns("ljys")]

    def included(name):
        return all(expr.search(name.encode("gb2312", "replace")) for expr in expressions)

    assert included("蓝鲸验收")
    assert included("LJys")
    assert included("𠮷")
    assert not included("合成空间-c0ffee")
