"""CHECK_RESULT member-count retention rules."""

import pytest

from alarm_backends.core.detect_result_retention import (
    InvalidRetentionConfig,
    rank_trim_stop,
)


def test_rank_trim_stop_keeps_exact_retention_count():
    assert rank_trim_stop(12) == -13


@pytest.mark.parametrize("invalid", [True, 0, -1])
def test_rank_trim_stop_rejects_invalid_count(invalid):
    with pytest.raises(InvalidRetentionConfig):
        rank_trim_stop(invalid)
