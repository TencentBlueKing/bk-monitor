import pytest

from bk_monitor_base.infras.declaratives.time_parse import time_converter


@pytest.mark.parametrize(
    "duration, result",
    [
        (1, 1),
        ("60", 60),
        ("1s", 1),
        ("1m", 60),
        ("1h", 3600),
        ("1d", 86400),
        ("1d1h1m1s", 90061),
        ("1d1h1m", 90060),
        ("2.5h", 9000),
    ],
)
def test_time_converter(duration, result):
    assert time_converter(duration) == result
