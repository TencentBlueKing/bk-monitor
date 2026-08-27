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
    build_access_publish_job,
    export_access_batch_context,
)
from alarm_backends.core.alarmd.v2_writer import build_execution_messages


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
        query=SimpleNamespace(dimensions=["host"]),
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

    job = build_access_publish_job(processor, [record], received_time=1725000061)
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
    job = build_access_publish_job(processor, [], received_time=1725000061)
    messages, drops = build_execution_messages(
        job, max_records=10, max_envelope_bytes=64 * 1024, message_id_factory=lambda: "message-1"
    )
    envelope = json.loads(messages[0].payload)

    assert drops == []
    assert envelope["records"] == []
    assert envelope["selectors"][0]["selector"]["ranges"] == []
    assert envelope["query_result"] == {"completeness": "FULL"}


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

    job = build_access_publish_job(processor, [], received_time=1725000061)
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

    job = build_access_publish_job(processor, [], received_time=1725000061)
    envelope = json.loads(
        build_execution_messages(
            job, max_records=10, max_envelope_bytes=64 * 1024, message_id_factory=lambda: "message-1"
        )[0][0].payload
    )
    trigger_config = envelope["plan_set"]["evaluation_plans"][0]["strategy_ir"]["levels"][0]["trigger_plan"]["config"]

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

    job = build_access_publish_job(processor, [record], received_time=1725000061)
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

    job = build_access_publish_job(processor, [record], received_time=1725000061)
    envelope = json.loads(
        build_execution_messages(
            job, max_records=10, max_envelope_bytes=64 * 1024, message_id_factory=lambda: "message-1"
        )[0][0].payload
    )

    plans = envelope["plan_set"]["evaluation_plans"]
    assert [plan["plan_id"] for plan in plans] == ["1001", "1002"]
    assert plans[0]["strategy_ir"]["levels"][0]["detect_plan"]["algorithms"][0]["type"] == ("M1UnsupportedPlan")
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

    job = build_access_publish_job(processor, [record], received_time=1725000061)
    envelope = json.loads(
        build_execution_messages(
            job, max_records=10, max_envelope_bytes=64 * 1024, message_id_factory=lambda: "message-1"
        )[0][0].payload
    )

    assert job.selections == ((True,),)
    assert envelope["selectors"][0]["selector"]["ranges"] == [{"start": 0, "end": 1}]
    assert (
        envelope["plan_set"]["evaluation_plans"][0]["strategy_ir"]["levels"][0]["detect_plan"]["algorithms"][0]["type"]
        == "M1UnsupportedPlan"
    )


def test_record_identity_schema_conflict_isolates_only_that_record():
    item, _ = _strategy(1001, 11, threshold=1)
    records = [
        SimpleNamespace(
            data={"time": 1725000000, "value": 3.0, "dimensions": {"host": "127.0.0.1"}},
            is_retains={11: True},
            inhibitions={11: False},
            clean_dimension_fields=lambda: ["host"],
        ),
        SimpleNamespace(
            data={
                "time": 1725000060,
                "value": 4.0,
                "dimensions": {"host": "127.0.0.2", "zone": "test"},
            },
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

    job = build_access_publish_job(processor, records, received_time=1725000121)

    assert job.record_count == 1


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
    job = build_access_publish_job(child, [], received_time=1725000061)
    envelope = json.loads(
        build_execution_messages(
            job, max_records=10, max_envelope_bytes=64 * 1024, message_id_factory=lambda: "message-1"
        )[0][0].payload
    )

    assert envelope["execution_id"] == "execution-1"
    assert envelope["query_result"] == {"completeness": "UNAVAILABLE", "reason_code": "CONFIG_DRIFT"}


def test_kafka_client_is_initialized_only_in_async_worker(mocker):
    initialized_threads = []

    class StubKafkaPublisher:
        def __init__(self, *_args, **_kwargs):
            initialized_threads.append(threading.current_thread().name)

        def publish(self, job):
            return job.record_count

    mocker.patch.object(v2_access, "KafkaExecutionEnvelopePublisher", StubKafkaPublisher)
    mocker.patch.object(v2_access.settings, "ALARMD_V2_SHADOW_ASYNC_MAX_JOBS", 1, create=True)
    mocker.patch.object(v2_access.settings, "ALARMD_V2_SHADOW_ASYNC_MAX_RECORDS", 10, create=True)
    mocker.patch.object(v2_access.settings, "ALARMD_V2_SHADOW_ASYNC_MAX_BYTES", 100_000, create=True)
    mocker.patch.object(v2_access.settings, "ALARMD_V2_SHADOW_KAFKA_CONFIG", {}, create=True)
    mocker.patch.object(v2_access.settings, "ALARMD_V2_SHADOW_ALLOWED_TOPICS", (), create=True)
    mocker.patch.object(v2_access, "build_access_publish_job", lambda _source, _records: _minimal_job())
    publisher = v2_access._new_async_publisher()
    assert initialized_threads == []
    source = SimpleNamespace(records=[])
    assert publisher.submit(source, record_count=0, retained_bytes=1)
    assert publisher.wait_empty(timeout=1)
    assert publisher.close(timeout=1)
    assert initialized_threads == ["alarmd-v2-access-publisher"]


def test_submit_only_enqueues_source_reference_without_running_builder(mocker):
    class StubPublisher:
        submitted = None

        def submit(self, source, *, record_count, retained_bytes):
            self.submitted = (source, record_count, retained_bytes)
            return True

    publisher = StubPublisher()
    mocker.patch.object(v2_access.settings, "ALARMD_SHADOW_ENABLED", True, create=True)
    mocker.patch.object(v2_access.settings, "ALARMD_V2_SHADOW_WRITER_ENABLED", True, create=True)
    mocker.patch.object(v2_access, "_publisher", publisher)
    mocker.patch.object(v2_access, "_publisher_pid", os.getpid())
    mocker.patch.object(v2_access, "_record_stage")
    builder = mocker.patch.object(v2_access, "build_access_publish_job")
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
    job = build_access_publish_job(processor, records, received_time=1725000061)

    with pytest.raises(AccessV2PublishError) as raised:
        publisher.publish(job)

    evidence = raised.value.evidence
    assert (evidence.planned_messages, evidence.published_messages, evidence.acked_messages) == (2, 1, 1)
    assert (evidence.planned_records, evidence.published_records, evidence.acked_records) == (2, 1, 1)
    assert evidence.acked_bytes > 0


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
        publisher.publish(_minimal_job())

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
    return build_access_publish_job(processor, [], received_time=1725000061)
