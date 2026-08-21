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
from django.conf import settings
from django.test import override_settings

from alarm_backends.core.cache import key
from alarm_backends.core.detect_result import tasks as detect_result_tasks
from alarm_backends.core.detect_result.clean import CleanResult


HSCAN_SETTINGS = {
    "ENABLE_CHECK_RESULT_CLEAN_HSCAN": True,
    "CHECK_RESULT_CLEAN_HSCAN_COUNT": 256,
    "CHECK_RESULT_CLEAN_HSCAN_MAX_FIELDS": 2048,
    "CHECK_RESULT_CLEAN_PIPELINE_COMMAND_LIMIT": 2,
}


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
    client.hscan.assert_not_called()
    pipeline.zremrangebyrank.assert_called_once_with("check-result-key", 0, -2)
    pipeline.zcard.assert_called_once_with("check-result-key")
    pipeline.hdel.assert_not_called()


def test_hscan_clean_is_disabled_by_default():
    assert settings.ENABLE_CHECK_RESULT_CLEAN_HSCAN is False
    assert settings.CHECK_RESULT_CLEAN_HSCAN_COUNT == 256
    assert settings.CHECK_RESULT_CLEAN_HSCAN_MAX_FIELDS == 2048
    assert settings.CHECK_RESULT_CLEAN_PIPELINE_COMMAND_LIMIT == 256


@override_settings(**HSCAN_SETTINGS)
def test_clean_expired_detect_result_scans_all_pages_after_each_page_is_complete():
    operations = []
    client = MagicMock()
    pipeline = client.pipeline.return_value
    strategy = {"id": 1, "items": [{"id": 11}]}

    def hscan(_key, *, cursor, count):
        operations.append(("hscan", cursor, count))
        if cursor == 0:
            return 17, [
                "detect.result.dimension-a.1",
                "detect.result.dimension-b.2",
                "detect.result.dimension-c.3",
            ]
        return 0, ["detect.result.dimension-d.4"]

    def execute():
        operations.append(("execute",))
        execute_count = sum(operation == ("execute",) for operation in operations)
        return {1: [], 2: [], 3: [0, 0], 4: [0], 5: [], 6: [], 7: [], 8: [1]}[execute_count]

    client.hscan.side_effect = hscan
    pipeline.execute.side_effect = execute
    pipeline.zremrangebyrank.side_effect = lambda cache_key, start, end: operations.append(
        ("zremrangebyrank", cache_key, start, end)
    )
    pipeline.zcard.side_effect = lambda cache_key: operations.append(("zcard", cache_key))
    pipeline.hdel.side_effect = lambda cache_key, field: operations.append(("hdel", cache_key, field))

    with (
        patch.object(key.LAST_CHECKPOINTS_CACHE_KEY, "_cache", client),
        patch.object(
            key.CHECK_RESULT_CACHE_KEY,
            "get_key",
            side_effect=lambda **kwargs: f"check.{kwargs['dimensions_md5']}.{kwargs['level']}",
        ),
        patch("alarm_backends.core.detect_result.clean.StrategyCacheManager.get_strategy_ids", return_value=[1]),
        patch(
            "alarm_backends.core.detect_result.clean.StrategyCacheManager.get_strategy_by_ids",
            return_value=[strategy],
        ),
        patch("alarm_backends.core.detect_result.clean.detect_result_point_required", return_value=2),
    ):
        CleanResult.clean_expired_detect_result()

    client.hkeys.assert_not_called()
    assert operations == [
        ("hscan", 0, 256),
        ("zremrangebyrank", "check.dimension-a.1", 0, -2),
        ("zremrangebyrank", "check.dimension-b.2", 0, -2),
        ("execute",),
        ("zremrangebyrank", "check.dimension-c.3", 0, -2),
        ("execute",),
        ("zcard", "check.dimension-a.1"),
        ("zcard", "check.dimension-b.2"),
        ("execute",),
        ("zcard", "check.dimension-c.3"),
        ("execute",),
        ("hdel", key.LAST_CHECKPOINTS_CACHE_KEY.get_key(strategy_id=1, item_id=11), "detect.result.dimension-a.1"),
        ("hdel", key.LAST_CHECKPOINTS_CACHE_KEY.get_key(strategy_id=1, item_id=11), "detect.result.dimension-b.2"),
        ("execute",),
        ("hdel", key.LAST_CHECKPOINTS_CACHE_KEY.get_key(strategy_id=1, item_id=11), "detect.result.dimension-c.3"),
        ("execute",),
        ("hscan", 17, 256),
        ("zremrangebyrank", "check.dimension-d.4", 0, -2),
        ("execute",),
        ("zcard", "check.dimension-d.4"),
        ("execute",),
    ]


@override_settings(
    ENABLE_CHECK_RESULT_CLEAN_HSCAN=True,
    CHECK_RESULT_CLEAN_HSCAN_COUNT=1,
    CHECK_RESULT_CLEAN_HSCAN_MAX_FIELDS=2,
    CHECK_RESULT_CLEAN_PIPELINE_COMMAND_LIMIT=2,
)
def test_clean_expired_detect_result_rejects_page_before_cleanup_commands():
    client = MagicMock()
    pipeline = client.pipeline.return_value
    client.hscan.return_value = (0, ["field-1", "field-1", "field-2"])
    strategy = {"id": 1, "items": [{"id": 11}]}

    with (
        patch.object(key.LAST_CHECKPOINTS_CACHE_KEY, "_cache", client),
        patch("alarm_backends.core.detect_result.clean.StrategyCacheManager.get_strategy_ids", return_value=[1]),
        patch(
            "alarm_backends.core.detect_result.clean.StrategyCacheManager.get_strategy_by_ids",
            return_value=[strategy],
        ),
        patch("alarm_backends.core.detect_result.clean.detect_result_point_required", return_value=2),
        pytest.raises(ValueError, match="3 fields exceeds hard limit 2"),
    ):
        CleanResult.clean_expired_detect_result()

    client.hkeys.assert_not_called()
    pipeline.zremrangebyrank.assert_not_called()
    pipeline.zcard.assert_not_called()
    pipeline.hdel.assert_not_called()


@override_settings(**HSCAN_SETTINGS)
def test_hscan_clean_task_stops_without_sleep_or_second_attempt():
    error = RuntimeError("hscan failed")
    client = MagicMock()
    client.hscan.side_effect = error
    strategy = {"id": 1, "items": [{"id": 11}]}

    with (
        patch.object(key.LAST_CHECKPOINTS_CACHE_KEY, "_cache", client),
        patch("alarm_backends.core.detect_result.clean.StrategyCacheManager.get_strategy_ids", return_value=[1]),
        patch(
            "alarm_backends.core.detect_result.clean.StrategyCacheManager.get_strategy_by_ids",
            return_value=[strategy],
        ),
        patch("alarm_backends.core.detect_result.clean.detect_result_point_required", return_value=2),
        patch("alarm_backends.core.detect_result.tasks.time.sleep") as sleep,
        pytest.raises(RuntimeError, match="hscan failed"),
    ):
        detect_result_tasks.async_clean_expired_detect_result((0, 10))

    client.hscan.assert_called_once_with(
        key.LAST_CHECKPOINTS_CACHE_KEY.get_key(strategy_id=1, item_id=11), cursor=0, count=256
    )
    client.hkeys.assert_not_called()
    sleep.assert_not_called()


@override_settings(ENABLE_CHECK_RESULT_CLEAN_HSCAN=False)
def test_legacy_clean_task_keeps_sleep_and_second_attempt():
    error = RuntimeError("hkeys failed")

    with (
        patch.object(CleanResult, "clean_expired_detect_result", side_effect=[error, None]) as clean,
        patch("alarm_backends.core.detect_result.tasks.time.sleep") as sleep,
    ):
        detect_result_tasks.async_clean_expired_detect_result((0, 10))

    assert clean.call_count == 2
    sleep.assert_called_once_with(60)


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
