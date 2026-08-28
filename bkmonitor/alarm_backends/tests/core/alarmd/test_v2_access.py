import json
import os
import threading
from types import SimpleNamespace

import pytest

from alarm_backends.core.alarmd import v2_access
from alarm_backends.core.alarmd.v2_access import (
    AccessV2PublishError,
    KafkaExecutionEnvelopePublisher,
    apply_access_batch_context,
    build_access_publish_jobs,
    export_access_batch_context,
)
from alarm_backends.core.alarmd.v2_writer import build_execution_messages
from alarm_backends.service.access.data.records import DataRecord


def _strategy(
    strategy_id,
    item_id,
    *,
    threshold,
    selected=True,
    level=1,
    priority=None,
    business_id=2,
    uptime=None,
):
    config = {
        "id": strategy_id,
        "bk_biz_id": business_id,
        "update_time": 1725000000 + strategy_id,
        "items": [
            {
                "id": item_id,
                "query_md5": "query-group-1",
                "query_configs": [{"agg_interval": 60, "agg_dimension": ["host"], "unit": "%"}],
                "algorithms": [
                    {
                        "type": "Threshold",
                        "level": level,
                        "unit_prefix": "",
                        "config": [{"method": "gt", "threshold": threshold}],
                    }
                ],
            }
        ],
        "detects": [
            {
                "level": level,
                "connector": "and",
                "trigger_config": {"count": 1, "check_window": 2},
                "recovery_config": {"check_window": 3},
            }
        ],
    }
    if priority is not None:
        config["detects"][0]["priority"] = priority
    if uptime is not None:
        config["detects"][0]["trigger_config"]["uptime"] = uptime
    strategy = SimpleNamespace(
        id=strategy_id,
        bk_biz_id=business_id,
        bk_tenant_id="default",
        scenario="performance",
        config=config,
    )
    item = SimpleNamespace(
        id=item_id,
        strategy=strategy,
        algorithms=config["items"][0]["algorithms"],
        query_configs=config["items"][0]["query_configs"],
        expression="A",
        functions=[],
        time_delay=0,
        unit="%",
        bk_tenant_id="default",
        data_sources=[],
        metric_ids=[],
        query=SimpleNamespace(
            dimensions=["host"],
            metrics=[{"field": "metric", "method": "AVG"}],
            is_partial=False,
        ),
    )
    return item, selected


def test_builds_query_group_data_once_plans_many_with_item_selectors():
    item_a, selected_a = _strategy(1001, 11, threshold=1)
    item_b, selected_b = _strategy(1002, 22, threshold=2, selected=False)
    record = SimpleNamespace(
        data={"time": 1725000000, "value": 3.0, "dimensions": {"host": "127.0.0.1"}},
        is_retains={11: selected_a, 22: selected_b},
        inhibitions={11: False, 22: False},
        clean_dimension_fields=lambda: ["host"],
    )
    processor = SimpleNamespace(
        items=[item_b, item_a],
        strategy_group_key="query-group-1",
        from_timestamp=1724999700,
        until_timestamp=1725000060,
        alarmd_v2_execution_id="execution-1",
        alarmd_v2_evaluation_time=1725000060,
        alarmd_v2_query_result={"completeness": "FULL"},
    )

    job = build_access_publish_jobs(processor, [record], received_time=1725000061)[0]
    message = build_execution_messages(
        job, max_records=10, max_envelope_bytes=64 * 1024, message_id_factory=lambda: "message-1"
    )[0][0]
    envelope = json.loads(message.payload)

    assert [plan["plan_id"] for plan in envelope["plan_set"]["evaluation_plans"]] == ["1001", "1002"]
    assert len(envelope["records"]) == 1
    assert envelope["selectors"][0]["selector"]["ranges"] == [{"start": 0, "end": 1}]
    assert envelope["selectors"][1]["selector"]["ranges"] == []
    assert envelope["records"][0]["values"] == {"value": 3.0}
    assert envelope["records"][0]["business_id"] == "2"


def test_configured_missing_dimension_is_preserved_as_explicit_null_identity():
    item, _ = _strategy(1001, 11, threshold=1)
    record = DataRecord(item, {"_time_": 1725000000, "_result_": 3.0}).clean()
    processor = SimpleNamespace(
        items=[item],
        strategy_group_key="query-group-1",
        from_timestamp=1724999700,
        until_timestamp=1725000060,
        alarmd_v2_execution_id="execution-1",
        alarmd_v2_evaluation_time=1725000060,
        alarmd_v2_query_result={"completeness": "FULL"},
    )

    job = build_access_publish_jobs(processor, [record], received_time=1725000061)[0]
    message = build_execution_messages(
        job, max_records=10, max_envelope_bytes=64 * 1024, message_id_factory=lambda: "message-1"
    )[0][0]
    envelope = json.loads(message.payload)

    assert job.record_count == 1
    assert envelope["dataset_contract"]["identity_fields"] == ["host"]
    assert envelope["records"][0]["dimension_identity"]["fields"] == [{"name": "host", "value": None}]
    assert (
        envelope["records"][0]["dimension_identity"]["digest"]
        == "248cb04ea988fcad43b087a7377e931b6ae200866a2e314af91677d8cbe16a87"
    )
    assert envelope["records"][0]["dimensions"] == {"host": None}


def test_nested_supplemental_dimension_is_excluded_without_dropping_record():
    item, _ = _strategy(1001, 11, threshold=1)
    record = SimpleNamespace(
        data={
            "time": 1725000000,
            "value": 3.0,
            "dimensions": {
                "host": "127.0.0.1",
                "bk_target_cloud_id": "0",
                "bk_topo_node": ["biz|2", "set|3"],
            },
        },
        is_retains={11: True},
        inhibitions={11: False},
        clean_dimension_fields=lambda: ["host"],
    )
    processor = SimpleNamespace(
        items=[item],
        strategy_group_key="query-group-1",
        from_timestamp=1724999700,
        until_timestamp=1725000060,
        alarmd_v2_execution_id="execution-1",
        alarmd_v2_evaluation_time=1725000060,
        alarmd_v2_query_result={"completeness": "FULL"},
    )

    job = build_access_publish_jobs(processor, [record], received_time=1725000061)[0]
    envelope = json.loads(
        build_execution_messages(
            job, max_records=10, max_envelope_bytes=64 * 1024, message_id_factory=lambda: "message-1"
        )[0][0].payload
    )

    assert job.record_count == 1
    assert envelope["records"][0]["dimension_identity"]["fields"] == [{"name": "host", "value": "127.0.0.1"}]
    assert envelope["records"][0]["dimensions"] == {
        "bk_target_cloud_id": "0",
        "host": "127.0.0.1",
    }


def test_invalid_identity_value_reports_bounded_detail_reason(caplog):
    caplog.set_level("WARNING", logger="alarmd.shadow")
    item, _ = _strategy(1001, 11, threshold=1)
    record = SimpleNamespace(
        data={"time": 1725000000, "value": 3.0, "dimensions": {"host": ["127.0.0.1"]}},
        is_retains={11: True},
        inhibitions={11: False},
        clean_dimension_fields=lambda: ["host"],
    )
    processor = SimpleNamespace(
        items=[item],
        strategy_group_key="query-group-1",
        from_timestamp=1724999700,
        until_timestamp=1725000060,
        alarmd_v2_execution_id="execution-1",
        alarmd_v2_evaluation_time=1725000060,
        alarmd_v2_query_result={"completeness": "FULL"},
    )

    job = build_access_publish_jobs(processor, [record], received_time=1725000061)[0]

    assert job.record_count == 0
    assert "reason=RECORD_INVALID" in caplog.text
    assert "detail_reasons=IDENTITY_DIMENSION_INVALID:1" in caplog.text


def test_non_scalar_record_value_reports_bounded_detail_reason(caplog):
    caplog.set_level("WARNING", logger="alarmd.shadow")
    item, _ = _strategy(1001, 11, threshold=1)
    record = SimpleNamespace(
        data={"time": 1725000000, "value": {"nested": 3.0}, "dimensions": {"host": "127.0.0.1"}},
        is_retains={11: True},
        inhibitions={11: False},
        clean_dimension_fields=lambda: ["host"],
    )
    processor = SimpleNamespace(
        items=[item],
        strategy_group_key="query-group-1",
        from_timestamp=1724999700,
        until_timestamp=1725000060,
        alarmd_v2_execution_id="execution-1",
        alarmd_v2_evaluation_time=1725000060,
        alarmd_v2_query_result={"completeness": "FULL"},
    )

    job = build_access_publish_jobs(processor, [record], received_time=1725000061)[0]

    assert job.record_count == 0
    assert "detail_reasons=RECORD_VALUE_INVALID:1" in caplog.text


def test_full_empty_still_builds_one_self_contained_message():
    item, _ = _strategy(1001, 11, threshold=1)
    processor = SimpleNamespace(
        items=[item],
        strategy_group_key="query-group-1",
        from_timestamp=1724999700,
        until_timestamp=1725000060,
        alarmd_v2_execution_id="execution-1",
        alarmd_v2_evaluation_time=1725000060,
        alarmd_v2_query_result={"completeness": "FULL"},
    )
    job = build_access_publish_jobs(processor, [], received_time=1725000061)[0]
    messages, drops = build_execution_messages(
        job, max_records=10, max_envelope_bytes=64 * 1024, message_id_factory=lambda: "message-1"
    )
    envelope = json.loads(messages[0].payload)

    assert drops == []
    assert envelope["records"] == []
    assert envelope["selectors"][0]["selector"]["ranges"] == []
    assert envelope["query_result"] == {"completeness": "FULL"}


def test_unavailable_ignores_record_schemas_and_builds_one_empty_dataset():
    item, _ = _strategy(1001, 11, threshold=1)
    records = [
        SimpleNamespace(clean_dimension_fields=lambda: ["host"]),
        SimpleNamespace(clean_dimension_fields=lambda: ["host", "zone"]),
    ]
    processor = SimpleNamespace(
        items=[item],
        strategy_group_key="query-group-1",
        from_timestamp=1724999700,
        until_timestamp=1725000060,
        alarmd_v2_execution_id="execution-1",
        alarmd_v2_evaluation_time=1725000060,
        alarmd_v2_query_result={"completeness": "UNAVAILABLE", "reason_code": "QUERY_UNAVAILABLE"},
    )

    jobs = build_access_publish_jobs(processor, records, received_time=1725000061)

    assert len(jobs) == 1
    assert jobs[0].record_count == 0
    assert list(jobs[0].snapshot["dataset_contract"]["identity_fields"]) == ["host"]
    assert dict(jobs[0].snapshot["query_result"]) == {
        "completeness": "UNAVAILABLE",
        "reason_code": "QUERY_UNAVAILABLE",
    }


def test_unknown_level_with_explicit_priority_passes_through_without_core_change():
    item, _ = _strategy(1001, 11, threshold=1, level=5, priority=1)
    processor = SimpleNamespace(
        items=[item],
        strategy_group_key="query-group-1",
        from_timestamp=1724999700,
        until_timestamp=1725000060,
        alarmd_v2_execution_id="execution-1",
        alarmd_v2_evaluation_time=1725000060,
        alarmd_v2_query_result={"completeness": "FULL"},
    )

    job = build_access_publish_jobs(processor, [], received_time=1725000061)[0]
    envelope = json.loads(
        build_execution_messages(
            job, max_records=10, max_envelope_bytes=64 * 1024, message_id_factory=lambda: "message-1"
        )[0][0].payload
    )

    assert envelope["plan_set"]["evaluation_plans"][0]["strategy_ir"]["levels"][0]["definition"] == {
        "level_id": 5,
        "priority": 1,
    }


def test_uptime_uses_business_timezone_reference_without_hot_path_lookup():
    uptime = {
        "time_ranges": [{"start": "09:00", "end": "18:00"}],
        "calendars": [],
        "active_calendars": [],
    }
    item, _ = _strategy(1001, 11, threshold=1, uptime=uptime)
    processor = SimpleNamespace(
        items=[item],
        strategy_group_key="query-group-1",
        from_timestamp=1724999700,
        until_timestamp=1725000060,
        alarmd_v2_execution_id="execution-1",
        alarmd_v2_evaluation_time=1725000060,
        alarmd_v2_query_result={"completeness": "FULL"},
    )

    job = build_access_publish_jobs(processor, [], received_time=1725000061)[0]
    envelope = json.loads(
        build_execution_messages(
            job, max_records=10, max_envelope_bytes=64 * 1024, message_id_factory=lambda: "message-1"
        )[0][0].payload
    )
    trigger_config = envelope["plan_set"]["evaluation_plans"][0]["strategy_ir"]["levels"][0]["trigger_plan"]["config"]

    assert trigger_config["uptime"] == uptime
    assert trigger_config["timezone_ref"] == "BUSINESS_LOCAL"


@pytest.mark.parametrize(
    "uptime",
    [
        {"time_ranges": [], "calendars": [], "active_calendars": []},
        {
            "time_ranges": [{"start": "00:00", "end": "23:59"}],
            "calendars": [],
            "active_calendars": [],
        },
        {
            "time_ranges": [{"start": "00:00:00", "end": "23:59:59"}],
            "calendars": [],
            "active_calendars": [],
        },
    ],
)
def test_always_active_uptime_without_calendars_is_omitted(uptime):
    item, _ = _strategy(1001, 11, threshold=1, uptime=uptime)
    trigger_config = v2_access._build_plan(item, ["host"], 60)["strategy_ir"]["levels"][0]["trigger_plan"]["config"]

    assert "uptime" not in trigger_config
    assert "timezone_ref" not in trigger_config


@pytest.mark.parametrize("calendar_field", ["calendars", "active_calendars"])
def test_always_active_time_range_with_calendar_is_preserved(calendar_field):
    uptime = {
        "time_ranges": [{"start": "00:00", "end": "23:59"}],
        "calendars": [],
        "active_calendars": [],
    }
    uptime[calendar_field] = [7]
    item, _ = _strategy(1001, 11, threshold=1, uptime=uptime)
    trigger_config = v2_access._build_plan(item, ["host"], 60)["strategy_ir"]["levels"][0]["trigger_plan"]["config"]

    assert trigger_config["uptime"] == uptime
    assert trigger_config["timezone_ref"] == "BUSINESS_LOCAL"


def test_non_default_second_precision_uptime_is_preserved():
    uptime = {
        "time_ranges": [{"start": "00:00:01", "end": "23:59:59"}],
        "calendars": [],
        "active_calendars": [],
    }
    item, _ = _strategy(1001, 11, threshold=1, uptime=uptime)
    trigger_config = v2_access._build_plan(item, ["host"], 60)["strategy_ir"]["levels"][0]["trigger_plan"]["config"]

    assert trigger_config["uptime"] == uptime
    assert trigger_config["timezone_ref"] == "BUSINESS_LOCAL"


def test_negative_space_business_id_uses_signed_canonical_identity():
    item, _ = _strategy(1001, 11, threshold=1, business_id=-200)
    record = SimpleNamespace(
        data={"time": 1725000000, "value": 3.0, "dimensions": {"host": "127.0.0.1"}},
        is_retains={11: True},
        inhibitions={11: False},
        clean_dimension_fields=lambda: ["host"],
    )
    processor = SimpleNamespace(
        items=[item],
        strategy_group_key="query-group-1",
        from_timestamp=1724999700,
        until_timestamp=1725000060,
        alarmd_v2_execution_id="execution-1",
        alarmd_v2_evaluation_time=1725000060,
        alarmd_v2_query_result={"completeness": "FULL"},
    )

    job = build_access_publish_jobs(processor, [record], received_time=1725000061)[0]
    envelope = json.loads(
        build_execution_messages(
            job, max_records=10, max_envelope_bytes=64 * 1024, message_id_factory=lambda: "message-1"
        )[0][0].payload
    )

    assert envelope["records"][0]["business_id"] == "-200"
    assert envelope["records"][0]["dimension_identity"]["digest"] == (
        "f9611eb00eb305502f613efa65a958a05963117c1fc8f2722d5109753ad7defe"
    )


def test_multiple_items_terminalize_only_affected_plan_and_keep_sibling():
    item_a, _ = _strategy(1001, 11, threshold=1)
    item_a_duplicate, _ = _strategy(1001, 12, threshold=1)
    item_b, _ = _strategy(1002, 22, threshold=2)
    record = SimpleNamespace(
        data={"time": 1725000000, "value": 3.0, "dimensions": {"host": "127.0.0.1"}},
        is_retains={11: False, 12: True, 22: True},
        inhibitions={11: False, 12: False, 22: False},
        clean_dimension_fields=lambda: ["host"],
    )
    processor = SimpleNamespace(
        items=[item_b, item_a_duplicate, item_a],
        strategy_group_key="query-group-1",
        from_timestamp=1724999700,
        until_timestamp=1725000060,
        alarmd_v2_execution_id="execution-1",
        alarmd_v2_evaluation_time=1725000060,
        alarmd_v2_query_result={"completeness": "FULL"},
    )

    job = build_access_publish_jobs(processor, [record], received_time=1725000061)[0]
    envelope = json.loads(
        build_execution_messages(
            job, max_records=10, max_envelope_bytes=64 * 1024, message_id_factory=lambda: "message-1"
        )[0][0].payload
    )

    plans = envelope["plan_set"]["evaluation_plans"]
    assert [plan["plan_id"] for plan in plans] == ["1001", "1002"]
    assert plans[0] == {
        "plan_id": "1001",
        "strategy_ref": plans[0]["strategy_ref"],
        "terminal_reason_code": "MULTIPLE_EVALUATION_UNITS_UNSUPPORTED",
    }
    assert envelope["selectors"][0]["selector"]["ranges"] == [{"start": 0, "end": 1}]
    assert envelope["selectors"][1]["selector"]["ranges"] == [{"start": 0, "end": 1}]


def test_single_item_terminal_plan_keeps_original_selection_for_receipt_conservation():
    item, _ = _strategy(1001, 11, threshold=1)
    item.query_configs[0]["agg_interval"] = "invalid"
    record = SimpleNamespace(
        data={"time": 1725000000, "value": 3.0, "dimensions": {"host": "127.0.0.1"}},
        is_retains={11: True},
        inhibitions={11: False},
        clean_dimension_fields=lambda: ["host"],
    )
    processor = SimpleNamespace(
        items=[item],
        strategy_group_key="query-group-1",
        from_timestamp=1724999700,
        until_timestamp=1725000060,
        alarmd_v2_execution_id="execution-1",
        alarmd_v2_evaluation_time=1725000060,
        alarmd_v2_query_result={"completeness": "FULL"},
    )

    job = build_access_publish_jobs(processor, [record], received_time=1725000061)[0]
    envelope = json.loads(
        build_execution_messages(
            job, max_records=10, max_envelope_bytes=64 * 1024, message_id_factory=lambda: "message-1"
        )[0][0].payload
    )

    assert job.selections == ((True,),)
    assert envelope["selectors"][0]["selector"]["ranges"] == [{"start": 0, "end": 1}]
    assert envelope["plan_set"]["evaluation_plans"][0]["terminal_reason_code"] == "PLAN_INVALID"
    assert set(envelope["plan_set"]["evaluation_plans"][0]) == {
        "plan_id",
        "strategy_ref",
        "terminal_reason_code",
    }


def test_mixed_record_identity_schemas_build_independent_datasets_without_rewriting_identity(caplog):
    item_a, _ = _strategy(1001, 11, threshold=1)
    item_b, _ = _strategy(1002, 22, threshold=2)
    records = [
        SimpleNamespace(
            data={"time": 1725000000, "value": 3.0, "dimensions": {"host": "127.0.0.1"}},
            is_retains={11: True, 22: True},
            inhibitions={11: False, 22: False},
            clean_dimension_fields=lambda: ["host"],
        ),
        SimpleNamespace(
            data={
                "time": 1725000060,
                "value": 4.0,
                "dimensions": {"host": "127.0.0.2", "zone": "test"},
            },
            is_retains={11: True, 22: True},
            inhibitions={11: False, 22: False},
            clean_dimension_fields=lambda: ["host", "zone"],
        ),
    ]
    processor = SimpleNamespace(
        items=[item_b, item_a],
        strategy_group_key="query-group-1",
        from_timestamp=1724999700,
        until_timestamp=1725000120,
        alarmd_v2_execution_id="execution-1",
        alarmd_v2_evaluation_time=1725000120,
        alarmd_v2_query_result={"completeness": "FULL"},
    )

    jobs = v2_access.build_access_publish_jobs(processor, records, received_time=1725000121)

    assert len(jobs) == 2
    envelopes = {}
    keys = set()
    for index, job in enumerate(jobs):
        message = build_execution_messages(
            job,
            max_records=10,
            max_envelope_bytes=64 * 1024,
            message_id_factory=lambda: f"message-{index}",
        )[0][0]
        envelope = json.loads(message.payload)
        identity_fields = tuple(envelope["dataset_contract"]["identity_fields"])
        envelopes[identity_fields] = envelope
        keys.add(message.key)

    assert set(envelopes) == {("host",), ("host", "zone")}
    assert len(keys) == 1
    assert {envelope["execution_id"] for envelope in envelopes.values()} == {"execution-1"}
    assert {envelope["query_group"]["key"] for envelope in envelopes.values()} == {"query-group-1"}
    assert {
        tuple(plan["plan_id"] for plan in envelope["plan_set"]["evaluation_plans"]) for envelope in envelopes.values()
    } == {("1001", "1002")}
    assert len({envelope["plan_set"]["plan_set_digest"] for envelope in envelopes.values()}) == 2
    assert {
        tuple(envelope["plan_set"]["evaluation_plans"][0]["input_projection"]["dimension_fields"])
        for envelope in envelopes.values()
    } == {("host",), ("host", "zone")}
    assert [record["dimensions"] for record in envelopes[("host",)]["records"]] == [{"host": "127.0.0.1"}]
    assert [record["dimensions"] for record in envelopes[("host", "zone")]["records"]] == [
        {"host": "127.0.0.2", "zone": "test"}
    ]
    assert all(
        all(selector["selector"]["ranges"] == [{"start": 0, "end": 1}] for selector in envelope["selectors"])
        for envelope in envelopes.values()
    )
    assert "reason=RECORD_IDENTITY_CONFLICT" not in caplog.text


def test_data_record_dynamic_dimensions_preserve_each_real_identity_schema():
    item, _ = _strategy(1001, 11, threshold=1)
    item.query.dimensions = None
    records = [
        DataRecord(item, {"_time_": 1725000000, "_result_": 3.0, "host": "127.0.0.1"}).clean(),
        DataRecord(
            item,
            {
                "_time_": 1725000060,
                "_result_": 4.0,
                "host": "127.0.0.2",
                "zone": "test",
            },
        ).clean(),
    ]
    processor = SimpleNamespace(
        items=[item],
        strategy_group_key="query-group-1",
        from_timestamp=1724999700,
        until_timestamp=1725000120,
        alarmd_v2_execution_id="execution-1",
        alarmd_v2_evaluation_time=1725000120,
        alarmd_v2_query_result={"completeness": "FULL"},
    )

    jobs = build_access_publish_jobs(processor, records, received_time=1725000121)

    assert [list(job.snapshot["dataset_contract"]["identity_fields"]) for job in jobs] == [
        ["host"],
        ["host", "zone"],
    ]
    assert [job.record_count for job in jobs] == [1, 1]
    assert [record["dimensions"] for job in jobs for record in job.records] == [
        {"host": "127.0.0.1"},
        {"host": "127.0.0.2", "zone": "test"},
    ]


def test_interleaved_identity_schemas_preserve_source_record_order():
    item, _ = _strategy(1001, 11, threshold=1)

    def record(source_time, dimensions, identity_fields):
        return SimpleNamespace(
            data={"time": source_time, "value": 3.0, "dimensions": dimensions},
            is_retains={11: True},
            inhibitions={11: False},
            clean_dimension_fields=lambda: identity_fields,
        )

    records = [
        record(1725000000, {"host": "host-1"}, ["host"]),
        record(1725000060, {"host": "host-2", "zone": "test"}, ["host", "zone"]),
        record(1725000120, {"host": "host-3"}, ["host"]),
    ]
    processor = SimpleNamespace(
        items=[item],
        strategy_group_key="query-group-1",
        from_timestamp=1724999700,
        until_timestamp=1725000180,
        alarmd_v2_execution_id="execution-1",
        alarmd_v2_evaluation_time=1725000180,
        alarmd_v2_query_result={"completeness": "FULL"},
    )

    jobs = build_access_publish_jobs(processor, records, received_time=1725000181)

    assert [list(job.snapshot["dataset_contract"]["identity_fields"]) for job in jobs] == [
        ["host"],
        ["host", "zone"],
        ["host"],
    ]
    assert [record["source_time"] for job in jobs for record in job.records] == [
        1725000000,
        1725000060,
        1725000120,
    ]
    assert [job.selections for job in jobs] == [((True,),), ((True,),), ((True,),)]


def test_invalid_identity_schema_isolated_with_execution_context(caplog):
    caplog.set_level("WARNING", logger="alarmd.shadow")
    item, _ = _strategy(1001, 11, threshold=1)
    valid = SimpleNamespace(
        data={"time": 1725000000, "value": 3.0, "dimensions": {"host": "127.0.0.1"}},
        is_retains={11: True},
        inhibitions={11: False},
        clean_dimension_fields=lambda: ["host"],
    )
    invalid = SimpleNamespace(clean_dimension_fields=lambda: ["host", "host"])
    processor = SimpleNamespace(
        items=[item],
        strategy_group_key="query-group-1",
        from_timestamp=1724999700,
        until_timestamp=1725000060,
        alarmd_v2_execution_id="execution-1",
        alarmd_v2_evaluation_time=1725000060,
        alarmd_v2_query_result={"completeness": "FULL"},
    )

    jobs = build_access_publish_jobs(processor, [invalid, valid], received_time=1725000061)

    assert len(jobs) == 1
    assert jobs[0].record_count == 1
    assert "reason=RECORD_IDENTITY_INVALID" in caplog.text
    assert "execution_id=execution-1" in caplog.text
    assert "query_group_key=query-group-1" in caplog.text
    assert "first_record_ordinal=0" in caplog.text


def test_batch_context_keeps_execution_and_detects_source_config_drift():
    item, _ = _strategy(1001, 11, threshold=1)
    parent = SimpleNamespace(
        items=[item],
        strategy_group_key="query-group-1",
        from_timestamp=1724999700,
        until_timestamp=1725000060,
        alarmd_v2_execution_id="execution-1",
        alarmd_v2_evaluation_time=1725000060,
        alarmd_v2_query_result={"completeness": "FULL"},
    )
    context = export_access_batch_context(parent)
    child = SimpleNamespace(items=[item], strategy_group_key="query-group-1")
    apply_access_batch_context(child, context)

    item.strategy.config["update_time"] += 1
    job = build_access_publish_jobs(child, [], received_time=1725000061)[0]
    envelope = json.loads(
        build_execution_messages(
            job, max_records=10, max_envelope_bytes=64 * 1024, message_id_factory=lambda: "message-1"
        )[0][0].payload
    )

    assert envelope["execution_id"] == "execution-1"
    assert envelope["query_result"] == {"completeness": "UNAVAILABLE", "reason_code": "CONFIG_DRIFT"}


def test_kafka_client_is_initialized_only_in_async_worker(mocker):
    initialized_threads = []
    published_dataset_counts = []

    class StubKafkaPublisher:
        def __init__(self, *_args, **_kwargs):
            initialized_threads.append(threading.current_thread().name)

        def publish(self, jobs):
            published_dataset_counts.append(len(jobs))
            return v2_access.AccessPublishEvidence(
                planned_messages=1,
                planned_records=0,
                planned_bytes=1,
                published_messages=1,
                published_records=0,
                published_bytes=1,
                acked_messages=1,
                acked_records=0,
                acked_bytes=1,
                dropped_records=0,
            )

    mocker.patch.object(v2_access, "KafkaExecutionEnvelopePublisher", StubKafkaPublisher)
    mocker.patch.object(v2_access.settings, "ALARMD_V2_SHADOW_ASYNC_MAX_JOBS", 1, create=True)
    mocker.patch.object(v2_access.settings, "ALARMD_V2_SHADOW_ASYNC_MAX_RECORDS", 10, create=True)
    mocker.patch.object(v2_access.settings, "ALARMD_V2_SHADOW_ASYNC_MAX_BYTES", 100_000, create=True)
    mocker.patch.object(v2_access.settings, "ALARMD_V2_SHADOW_KAFKA_CONFIG", {}, create=True)
    mocker.patch.object(v2_access.settings, "ALARMD_V2_SHADOW_ALLOWED_TOPICS", (), create=True)
    mocker.patch.object(v2_access, "build_access_publish_jobs", lambda _source, _records: (_minimal_job(),))
    publisher = v2_access._new_async_publisher()
    assert initialized_threads == []
    source = SimpleNamespace(records=[])
    assert publisher.submit(source, record_count=0, retained_bytes=1)
    assert publisher.wait_empty(timeout=1)
    assert publisher.close(timeout=1)
    assert initialized_threads == ["alarmd-v2-access-publisher"]
    assert published_dataset_counts == [1]


def test_submit_only_enqueues_source_reference_without_running_builder(mocker):
    class StubPublisher:
        submitted = None

        def submit(self, source, *, record_count, retained_bytes):
            self.submitted = (source, record_count, retained_bytes)
            return True

    publisher = StubPublisher()
    mocker.patch.object(v2_access.settings, "ALARMD_SHADOW_ENABLED", True)
    mocker.patch.object(v2_access, "_publisher", publisher)
    mocker.patch.object(v2_access, "_publisher_pid", os.getpid())
    mocker.patch.object(v2_access, "_record_stage")
    builder = mocker.patch.object(v2_access, "build_access_publish_jobs")
    item, _ = _strategy(1001, 11, threshold=1)
    records = [object()]
    processor = SimpleNamespace(
        items=[item],
        strategy_group_key="query-group-1",
        from_timestamp=1724999700,
        until_timestamp=1725000060,
        alarmd_v2_execution_id="execution-1",
        alarmd_v2_evaluation_time=1725000060,
        alarmd_v2_query_result={"completeness": "FULL"},
    )

    assert v2_access.submit_access_shadow(processor, records)

    builder.assert_not_called()
    source, record_count, retained_bytes = publisher.submitted
    assert source.records is records
    assert source.items is processor.items
    assert record_count == 1
    assert retained_bytes > 0


def test_partial_publish_failure_preserves_known_ack_evidence():
    class StubProducer:
        calls = 0

        def produce(self, *, on_delivery, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                on_delivery(None, None)
                return
            raise RuntimeError("second message rejected")

        def poll(self, _timeout):
            return None

        def flush(self, *, timeout):
            return 0

    producer = StubProducer()
    publisher = KafkaExecutionEnvelopePublisher(
        {
            "topic": "alarmd-v2",
            "alarm.engine.max.records.per.message": 1,
            "alarm.engine.max.envelope.bytes": 64 * 1024,
        },
        ["alarmd-v2"],
        producer_factory=lambda _config: producer,
    )
    item, _ = _strategy(1001, 11, threshold=1)
    records = [
        SimpleNamespace(
            data={"time": 1725000000 + index, "value": 3.0, "dimensions": {"host": f"host-{index}"}},
            is_retains={11: True},
            inhibitions={11: False},
            clean_dimension_fields=lambda: ["host"],
        )
        for index in range(2)
    ]
    processor = SimpleNamespace(
        items=[item],
        strategy_group_key="query-group-1",
        from_timestamp=1724999700,
        until_timestamp=1725000060,
        alarmd_v2_execution_id="execution-1",
        alarmd_v2_evaluation_time=1725000060,
        alarmd_v2_query_result={"completeness": "FULL"},
    )
    jobs = build_access_publish_jobs(processor, records, received_time=1725000061)

    with pytest.raises(AccessV2PublishError) as raised:
        publisher.publish(jobs)

    evidence = raised.value.evidence
    assert (evidence.planned_messages, evidence.published_messages, evidence.acked_messages) == (2, 1, 1)
    assert (evidence.planned_records, evidence.published_records, evidence.acked_records) == (2, 1, 1)
    assert evidence.acked_bytes > 0


def test_publisher_flushes_identity_schema_datasets_once_and_aggregates_ack_evidence():
    class StubProducer:
        flush_calls = 0

        def produce(self, *, on_delivery, **_kwargs):
            on_delivery(None, None)

        def poll(self, _timeout):
            return None

        def flush(self, *, timeout):
            self.flush_calls += 1
            return 0

    producer = StubProducer()
    publisher = KafkaExecutionEnvelopePublisher(
        {
            "topic": "alarmd-v2",
            "alarm.engine.max.records.per.message": 10,
            "alarm.engine.max.envelope.bytes": 64 * 1024,
        },
        ["alarmd-v2"],
        producer_factory=lambda _config: producer,
    )
    item, _ = _strategy(1001, 11, threshold=1)
    records = [
        SimpleNamespace(
            data={"time": 1725000000, "value": 3.0, "dimensions": {"host": "127.0.0.1"}},
            is_retains={11: True},
            inhibitions={11: False},
            clean_dimension_fields=lambda: ["host"],
        ),
        SimpleNamespace(
            data={"time": 1725000060, "value": 4.0, "dimensions": {"host": "127.0.0.2", "zone": "test"}},
            is_retains={11: True},
            inhibitions={11: False},
            clean_dimension_fields=lambda: ["host", "zone"],
        ),
    ]
    processor = SimpleNamespace(
        items=[item],
        strategy_group_key="query-group-1",
        from_timestamp=1724999700,
        until_timestamp=1725000120,
        alarmd_v2_execution_id="execution-1",
        alarmd_v2_evaluation_time=1725000120,
        alarmd_v2_query_result={"completeness": "FULL"},
    )

    evidence = publisher.publish(v2_access.build_access_publish_jobs(processor, records, received_time=1725000121))

    assert producer.flush_calls == 1
    assert (evidence.planned_messages, evidence.planned_records) == (2, 2)
    assert (evidence.published_messages, evidence.published_records) == (2, 2)
    assert (evidence.acked_messages, evidence.acked_records) == (2, 2)
    assert evidence.dropped_records == 0


def test_plan_set_budget_failure_is_not_reported_as_kafka_failure():
    publisher = KafkaExecutionEnvelopePublisher(
        {
            "topic": "alarmd-v2",
            "alarm.engine.max.records.per.message": 1,
            "alarm.engine.max.envelope.bytes": 64,
        },
        ["alarmd-v2"],
        producer_factory=lambda _config: object(),
    )

    with pytest.raises(AccessV2PublishError) as raised:
        publisher.publish((_minimal_job(),))

    assert raised.value.reason_code == "MESSAGE_BUDGET_EXCEEDED"
    assert raised.value.evidence.dropped_records == 0


def _minimal_job():
    item, _ = _strategy(1001, 11, threshold=1)
    processor = SimpleNamespace(
        items=[item],
        strategy_group_key="query-group-1",
        from_timestamp=1724999700,
        until_timestamp=1725000060,
        alarmd_v2_execution_id="execution-1",
        alarmd_v2_evaluation_time=1725000060,
        alarmd_v2_query_result={"completeness": "FULL"},
    )
    return build_access_publish_jobs(processor, [], received_time=1725000061)[0]
