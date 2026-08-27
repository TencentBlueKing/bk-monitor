import base64
import gzip
import json
from collections import defaultdict

from django.conf import settings

from alarm_backends.service.access.data import processor as access_processor
from alarm_backends.service.access.data.processor import AccessDataProcess, BaseAccessDataProcess


def test_alarmd_shadow_master_switch_is_the_only_writer_gate(mocker):
    mocker.patch.object(settings, "ALARMD_SHADOW_ENABLED", True)

    assert access_processor._alarmd_v2_shadow_enabled()


def test_alarmd_v2_gate_off_does_not_import_v2_modules(mocker):
    mocker.patch.object(settings, "ALARMD_SHADOW_ENABLED", False)
    imported = mocker.patch("builtins.__import__", wraps=__import__)

    assert not access_processor._alarmd_v2_shadow_enabled()
    assert not any(call.args[0].startswith("alarm_backends.core.alarmd.v2_") for call in imported.call_args_list)


def test_access_push_prepares_priority_once_before_shadow_and_main_branch(mocker):
    processor = object.__new__(AccessDataProcess)
    processor.strategy_group_key = "group"
    processor.record_list = [
        mocker.MagicMock(
            is_duplicate=False,
            is_retains=defaultdict(lambda: True),
            inhibitions=defaultdict(bool),
        )
    ]
    processor.sub_task_id = "1.1"
    processor.process_counts = {}
    processor.alarmd_v2_execution_id = "execution-1"
    processor.dup_obj = mocker.MagicMock()
    processor._limit_records_by_time_points = mocker.MagicMock(return_value=(processor.record_list, None, []))
    processor._can_merge_access_detect = mocker.MagicMock(return_value=False)
    priority = mocker.patch.object(access_processor.PriorityChecker, "check_records")
    submit = mocker.patch("alarm_backends.core.alarmd.v2_access.submit_access_shadow")
    main_push = mocker.patch.object(BaseAccessDataProcess, "push")

    processor.push()

    priority.assert_called_once_with(processor.record_list)
    submit.assert_called_once_with(processor, processor.record_list)
    main_push.assert_called_once_with(records=processor.record_list, output_client=None, prepared=True)


def test_access_push_off_does_not_import_or_build_v2(mocker):
    processor = object.__new__(AccessDataProcess)
    processor.strategy_group_key = "group"
    processor.record_list = [
        mocker.MagicMock(
            is_duplicate=False,
            is_retains=defaultdict(lambda: True),
            inhibitions=defaultdict(bool),
        )
    ]
    processor.sub_task_id = "1.1"
    processor.process_counts = {}
    processor.alarmd_v2_execution_id = None
    processor.dup_obj = mocker.MagicMock()
    processor._limit_records_by_time_points = mocker.MagicMock(return_value=(processor.record_list, None, []))
    processor._can_merge_access_detect = mocker.MagicMock(return_value=False)
    priority = mocker.patch.object(access_processor.PriorityChecker, "check_records")
    main_push = mocker.patch.object(BaseAccessDataProcess, "push")
    imported = mocker.patch("builtins.__import__", wraps=__import__)

    processor.push()

    priority.assert_called_once_with(processor.record_list)
    main_push.assert_called_once_with(records=processor.record_list, output_client=None, prepared=True)
    assert not any(call.args[0] == "alarm_backends.core.alarmd.v2_access" for call in imported.call_args_list)


def test_query_failure_is_preserved_as_unavailable_before_empty_fallback(mocker):
    processor = AccessDataProcess("group")
    processor.alarmd_v2_execution_id = "execution-1"
    item = mocker.MagicMock()
    item.strategy.id = 1
    item.data_source_types = set()
    item.data_source_labels = set()
    item.query_record.side_effect = RuntimeError("query failed")
    processor.items = [item]
    processor.from_timestamp = 1
    processor.until_timestamp = 2

    assert processor.query_data(now_timestamp=3) == []
    assert processor.alarmd_v2_query_result == {
        "completeness": "UNAVAILABLE",
        "reason_code": "QUERY_UNAVAILABLE",
    }


def test_query_outcome_off_stays_none(mocker):
    processor = AccessDataProcess("group")
    item = mocker.MagicMock()
    item.strategy.id = 1
    item.data_source_types = set()
    item.data_source_labels = set()
    item.query_record.side_effect = RuntimeError("query failed")
    processor.items = [item]
    processor.from_timestamp = 1
    processor.until_timestamp = 2

    assert processor.query_data(now_timestamp=3) == []
    assert processor.alarmd_v2_execution_id is None
    assert processor.alarmd_v2_query_result is None


def test_partial_double_check_group_semantics_match_with_shadow_off_and_on(mocker):
    mocker.patch.object(settings, "DOUBLE_CHECK_SUM_STRATEGY_IDS", [2])
    for execution_id in (None, "execution-1"):
        processor = AccessDataProcess("group")
        first_item = mocker.MagicMock()
        first_item.strategy.id = 1
        first_item.data_source_types = set()
        first_item.data_source_labels = set()
        first_item.query_record.return_value = [{"_time_": 1, "value": 1}]
        first_item.query.is_partial = True
        sibling_item = mocker.MagicMock()
        sibling_item.strategy.id = 2
        processor.items = [first_item, sibling_item]
        processor.from_timestamp = 1
        processor.until_timestamp = 2
        processor.alarmd_v2_execution_id = execution_id

        assert processor.query_data(now_timestamp=3) == []
        assert processor.alarmd_v2_query_result == (
            {"completeness": "PARTIAL", "reason_code": "QUERY_PARTIAL"} if execution_id else None
        )


def test_batch_payload_off_keeps_legacy_list_format(mocker):
    processor = object.__new__(AccessDataProcess)
    processor.strategy_group_key = "group"
    processor.items = [mocker.MagicMock()]
    processor.items[0].strategy.id = 1
    processor.alarmd_v2_execution_id = None
    client = mocker.MagicMock()
    mocker.patch.object(access_processor.key.ACCESS_BATCH_DATA_KEY, "_cache", client)
    batch_task = mocker.patch("alarm_backends.service.access.tasks.run_access_batch_data")

    first_batch = processor.send_batch_data(
        [
            {"_time_": 1, "value": 1},
            {"_time_": 2, "value": 2},
            {"_time_": 3, "value": 3},
        ],
        batch_threshold=1,
    )

    assert first_batch == [{"_time_": 1, "value": 1}]
    stored = client.set.call_args.args[1]
    assert json.loads(gzip.decompress(base64.b64decode(stored)).decode("utf-8")) == [
        {"_time_": 2, "value": 2},
        {"_time_": 3, "value": 3},
    ]
    batch_task.delay.assert_called_once()
