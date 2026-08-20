"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest.mock import MagicMock, patch

import pytest

from alarm_backends.core.cache import key
from alarm_backends.core.detect_result.clean import CleanResult


def test_clean_expired_detect_result_executes_existing_cleanup_commands():
    client = MagicMock()
    pipeline = client.pipeline.return_value
    client.hkeys.return_value = ["checkpoint.dimension-md5.1"]
    pipeline.execute.side_effect = [[], [1], []]
    strategy = {"id": 1, "items": [{"id": 11}]}

    with (
        patch.object(key.LAST_CHECKPOINTS_CACHE_KEY, "_cache", client),
        patch.object(key.CHECK_RESULT_CACHE_KEY, "get_key", return_value="check-result-key"),
        patch("alarm_backends.core.detect_result.clean.StrategyCacheManager.get_strategy_ids", return_value=[1]),
        patch(
            "alarm_backends.core.detect_result.clean.StrategyCacheManager.get_strategy_by_ids",
            return_value=[strategy],
        ),
        patch("alarm_backends.core.detect_result.clean.detect_result_point_required", return_value=2),
    ):
        CleanResult.clean_expired_detect_result()

    client.hkeys.assert_called_once()
    pipeline.zremrangebyrank.assert_called_once_with("check-result-key", 0, -2)
    pipeline.zcard.assert_called_once_with("check-result-key")
    pipeline.hdel.assert_not_called()


def test_scan_last_checkpoint_page_returns_cursor_and_deduplicated_fields():
    client = MagicMock()
    client.hscan.return_value = (17, ["field-1", "field-1", "field-2"])

    next_cursor, fields = CleanResult.scan_last_checkpoint_page(
        client,
        "last-checkpoints-key",
        cursor=0,
        count=256,
        max_fields=2048,
    )

    assert next_cursor == 17
    assert fields == ("field-1", "field-2")
    client.hscan.assert_called_once_with("last-checkpoints-key", cursor=0, count=256)


def test_scan_last_checkpoint_page_rejects_actual_page_over_hard_limit():
    client = MagicMock()
    client.hscan.return_value = (0, ["field-1", "field-1", "field-2"])

    with pytest.raises(ValueError, match="3 fields exceeds hard limit 2"):
        CleanResult.scan_last_checkpoint_page(
            client,
            "last-checkpoints-key",
            cursor=9,
            count=1,
            max_fields=2,
        )


def test_chunk_fields_never_exceeds_command_limit():
    chunks = list(CleanResult.chunk_fields(["a", "b", "c", "d", "e"], command_limit=2))

    assert chunks == [("a", "b"), ("c", "d"), ("e",)]
