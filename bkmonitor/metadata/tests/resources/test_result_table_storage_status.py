import datetime
import threading

import pytest

from metadata import models
from metadata.resources import GetResultTableStorageStatus
from metadata.service.result_table_storage_status import (
    BoundedExecutor,
    ClusterProbeScheduler,
    MAX_PROBE_WORKERS,
    MAX_PROBE_WORKERS_PER_CLUSTER,
    ResultTableStorageStatusBatchService,
    ResultTableStorageStatusService,
    SchedulerQueueFullError,
    build_doris_storage_runtime,
)


TENANT_ID = "storage-status-tenant"


def _create_result_table(table_id: str, default_storage: str) -> models.ResultTable:
    return models.ResultTable.objects.create(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        table_name_zh=table_id,
        is_custom_table=False,
        schema_type=models.ResultTable.SCHEMA_TYPE_FREE,
        default_storage=default_storage,
        creator="system",
        last_modify_user="system",
    )


def _create_cluster(cluster_id: int, cluster_type: str) -> models.ClusterInfo:
    return models.ClusterInfo.objects.create(
        bk_tenant_id=TENANT_ID,
        cluster_id=cluster_id,
        cluster_name=f"{cluster_type}-{cluster_id}",
        display_name=f"cluster-{cluster_id}",
        cluster_type=cluster_type,
        domain_name=f"cluster-{cluster_id}.example.com",
        port=9200 if cluster_type == models.ClusterInfo.TYPE_ES else 9030,
        description="",
        is_default_cluster=False,
        username="secret-user",
        password="secret-password",
        version="7.10" if cluster_type == models.ClusterInfo.TYPE_ES else "2.1",
    )


def _create_segment(
    table_id: str,
    cluster_id: int,
    enable_time: datetime.datetime,
    *,
    is_current: bool,
) -> models.StorageClusterRecord:
    return models.StorageClusterRecord.objects.create(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        cluster_id=cluster_id,
        enable_time=enable_time,
        is_current=is_current,
        creator="system",
    )


def _available_connectivity(cluster: models.ClusterInfo, timeout: int | None = None) -> dict:
    return {
        "is_connected": True,
        "error": None,
    }


@pytest.mark.django_db(databases="__all__")
def test_query_mixed_storage_history_deduplicates_clusters_and_projects_runtime(mocker):
    table_id = "2_bklog.storage_status"
    _create_result_table(table_id, models.ClusterInfo.TYPE_ES)
    es_cluster = _create_cluster(91001, models.ClusterInfo.TYPE_ES)
    doris_cluster = _create_cluster(91002, models.ClusterInfo.TYPE_DORIS)
    models.ESStorage.objects.create(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        storage_cluster_id=es_cluster.cluster_id,
        index_set="bklog_index_set_1",
        need_create_index=False,
    )
    models.DorisStorage.objects.create(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        storage_cluster_id=doris_cluster.cluster_id,
        bkbase_table_id="2_bklog_storage_status",
        index_set="bklog_index_set_1",
    )
    first_es_segment = _create_segment(
        table_id,
        es_cluster.cluster_id,
        datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        is_current=False,
    )
    doris_segment = _create_segment(
        table_id,
        doris_cluster.cluster_id,
        datetime.datetime(2026, 2, 1, tzinfo=datetime.timezone.utc),
        is_current=False,
    )
    second_es_segment = _create_segment(
        table_id,
        es_cluster.cluster_id,
        datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc),
        is_current=True,
    )

    connectivity_check = mocker.patch.object(
        models.ClusterInfo,
        "check_connectivity",
        autospec=True,
        side_effect=_available_connectivity,
    )
    es_runtime = mocker.patch(
        "metadata.service.result_table_storage_status.query_es_storage_runtime",
        return_value=(
            {
                "indices": {"count": 1, "items": [{"index": "external-20260301", "docs_count": 3}]},
                "aliases": {
                    "queried": False,
                    "reason": "need_create_index_false",
                    "count": 0,
                    "relation_count": 0,
                    "items": [],
                },
            },
            [],
        ),
    )
    doris_runtime = mocker.patch.object(
        models.DorisStorage,
        "query_physical_storage_metadata",
        autospec=True,
        return_value={
            "request_table_id": table_id,
            "doris_binding": {
                "name": "storage-status",
                "namespace": "bklog",
                "status": {"phase": "Ok", "message": "ready", "raw": "ignored"},
                "physical_table_name": "bklog.storage_status",
                "physical_table_name_source": "annotation",
                "storage_config": {"password": "ignored"},
            },
            "physical_metadata": {
                "tables": [{"TABLE_NAME": "storage_status", "TABLE_ROWS": 3, "RAW_FIELD": "ignored"}],
                "columns": [
                    {
                        "COLUMN_NAME": "dtEventTimeStamp",
                        "ORDINAL_POSITION": 1,
                        "IS_NULLABLE": "NO",
                        "DATA_TYPE": "bigint",
                        "RAW_FIELD": "ignored",
                    }
                ],
                "partitions": [{"PARTITION_NAME": "p20260301", "TABLE_ROWS": 3, "RAW_FIELD": "ignored"}],
            },
            "warnings": [],
            "errors": [],
        },
    )

    result = ResultTableStorageStatusService(bk_tenant_id=TENANT_ID, table_id=table_id, timeout=15).query()

    assert [segment["id"] for segment in result["segments"]] == [
        first_es_segment.id,
        doris_segment.id,
        second_es_segment.id,
    ]
    assert list(result["cluster_results"]) == [str(es_cluster.cluster_id), str(doris_cluster.cluster_id)]
    es_result = result["cluster_results"][str(es_cluster.cluster_id)]
    doris_result = result["cluster_results"][str(doris_cluster.cluster_id)]
    assert "segment_ids" not in es_result
    assert es_result["is_current_segment"] is True
    assert es_result["is_configured_current"] is True
    assert "HISTORICAL_CONFIG_NOT_SNAPSHOTTED" in {warning["code"] for warning in es_result["warnings"]}
    assert es_result["runtime"]["aliases"]["queried"] is False
    assert doris_result["runtime"]["table"] == {"name": "storage_status", "rows": 3}
    assert doris_result["runtime"]["columns"] == [
        {"name": "dtEventTimeStamp", "position": 1, "is_nullable": False, "data_type": "bigint"}
    ]
    assert doris_result["runtime"]["partitions"] == [{"name": "p20260301", "rows": 3}]
    assert result["storage_configs"][models.ClusterInfo.TYPE_ES]["storage_cluster_id"] == es_cluster.cluster_id
    assert "password" not in result["storage_configs"][models.ClusterInfo.TYPE_ES]
    assert "username" not in es_result["cluster"]
    assert es_result["connectivity"] == {"is_connected": True, "error": None}
    assert doris_result["connectivity"] == {"is_connected": True, "error": None}
    assert "health" not in es_result
    assert "health" not in doris_result
    assert connectivity_check.call_count == 2
    assert {item.kwargs["timeout"] for item in connectivity_check.call_args_list} == {15}
    es_runtime.assert_called_once()
    assert es_runtime.call_args.kwargs["timeout"] == 15
    doris_runtime.assert_called_once()
    assert doris_runtime.call_args.kwargs == {
        "storage_cluster_id": doris_cluster.cluster_id,
        "timeout": 15,
        "include_create_table": False,
    }


@pytest.mark.django_db(databases="__all__")
def test_connectivity_failure_skips_runtime_and_returns_error(mocker):
    table_id = "2_bklog.storage_unavailable"
    _create_result_table(table_id, models.ClusterInfo.TYPE_ES)
    cluster = _create_cluster(92001, models.ClusterInfo.TYPE_ES)
    models.ESStorage.objects.create(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        storage_cluster_id=cluster.cluster_id,
        need_create_index=False,
    )
    _create_segment(
        table_id,
        cluster.cluster_id,
        datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        is_current=True,
    )
    mocker.patch.object(
        models.ClusterInfo,
        "check_connectivity",
        return_value={
            "is_connected": False,
            "error": {"code": "CONNECTION_FAILED", "message": "timeout", "details": {}},
        },
    )
    es_runtime = mocker.patch("metadata.service.result_table_storage_status.query_es_storage_runtime")

    result = ResultTableStorageStatusService(bk_tenant_id=TENANT_ID, table_id=table_id).query()

    cluster_result = result["cluster_results"][str(cluster.cluster_id)]
    assert cluster_result["runtime_skipped"] is True
    assert cluster_result["runtime"] is None
    assert cluster_result["errors"][0]["code"] == "STORAGE_CONNECTIVITY_CHECK_FAILED"
    es_runtime.assert_not_called()


@pytest.mark.django_db(databases="__all__")
def test_virtual_result_table_uses_origin_history(mocker):
    physical_table_id = "2_bklog.storage_physical"
    virtual_table_id = "2_bklog.storage_virtual"
    _create_result_table(virtual_table_id, models.ClusterInfo.TYPE_ES)
    cluster = _create_cluster(93001, models.ClusterInfo.TYPE_ES)
    models.ESStorage.objects.create(
        bk_tenant_id=TENANT_ID,
        table_id=virtual_table_id,
        origin_table_id=physical_table_id,
        storage_cluster_id=cluster.cluster_id,
        need_create_index=False,
    )
    models.DorisStorage.objects.create(
        bk_tenant_id=TENANT_ID,
        table_id=physical_table_id,
        storage_cluster_id=cluster.cluster_id + 1,
        bkbase_table_id="2_bklog_storage_physical",
    )
    doris_cluster = _create_cluster(cluster.cluster_id + 1, models.ClusterInfo.TYPE_DORIS)
    segment = _create_segment(
        physical_table_id,
        cluster.cluster_id,
        datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        is_current=True,
    )
    doris_segment = _create_segment(
        physical_table_id,
        doris_cluster.cluster_id,
        datetime.datetime(2025, 12, 1, tzinfo=datetime.timezone.utc),
        is_current=False,
    )
    mocker.patch.object(models.ClusterInfo, "check_connectivity", autospec=True, side_effect=_available_connectivity)
    es_runtime = mocker.patch(
        "metadata.service.result_table_storage_status.query_es_storage_runtime",
        return_value=({"indices": {}, "aliases": {}}, []),
    )
    doris_runtime = mocker.patch.object(
        models.DorisStorage,
        "query_physical_storage_metadata",
        return_value={"physical_metadata": {}, "warnings": [], "errors": []},
    )

    result = ResultTableStorageStatusService(bk_tenant_id=TENANT_ID, table_id=virtual_table_id).query()

    assert result["result_table"]["table_id"] == virtual_table_id
    assert result["history_table_id"] == physical_table_id
    assert [item["id"] for item in result["segments"]] == [doris_segment.id, segment.id]
    assert result["storage_configs"][models.ClusterInfo.TYPE_ES]["effective_table_id"] == physical_table_id
    assert result["storage_configs"][models.ClusterInfo.TYPE_DORIS]["table_id"] == physical_table_id
    assert result["warnings"][0]["code"] == "EFFECTIVE_STORAGE_CONFIG_USED"
    assert es_runtime.call_args.kwargs["es_storage"].table_id == virtual_table_id
    doris_runtime.assert_called_once()


def test_resource_timeout_serializer_defaults_and_validates_range():
    default_serializer = GetResultTableStorageStatus.RequestSerializer(
        data={"bk_tenant_id": TENANT_ID, "table_ids": ["2_bklog.demo"]}
    )
    assert default_serializer.is_valid(), default_serializer.errors
    assert default_serializer.validated_data["timeout"] == 15
    assert default_serializer.validated_data["total_timeout"] == 60

    valid_serializer = GetResultTableStorageStatus.RequestSerializer(
        data={"bk_tenant_id": TENANT_ID, "table_ids": [f"2_bklog.demo_{index}" for index in range(50)], "timeout": 30}
    )
    assert valid_serializer.is_valid(), valid_serializer.errors

    for timeout in (0, 31):
        serializer = GetResultTableStorageStatus.RequestSerializer(
            data={"bk_tenant_id": TENANT_ID, "table_ids": ["2_bklog.demo"], "timeout": timeout}
        )
        assert not serializer.is_valid()

    for total_timeout in (0, 301):
        serializer = GetResultTableStorageStatus.RequestSerializer(
            data={"bk_tenant_id": TENANT_ID, "table_ids": ["2_bklog.demo"], "total_timeout": total_timeout}
        )
        assert not serializer.is_valid()

    for table_ids in ([], ["2_bklog.demo"] * 2, [f"2_bklog.demo_{index}" for index in range(51)]):
        serializer = GetResultTableStorageStatus.RequestSerializer(
            data={"bk_tenant_id": TENANT_ID, "table_ids": table_ids}
        )
        assert not serializer.is_valid()

    legacy_serializer = GetResultTableStorageStatus.RequestSerializer(
        data={"bk_tenant_id": TENANT_ID, "table_id": "2_bklog.demo"}
    )
    assert not legacy_serializer.is_valid()


@pytest.mark.django_db(databases="__all__")
def test_resource_request_reports_missing_result_table():
    result = GetResultTableStorageStatus().request({"bk_tenant_id": TENANT_ID, "table_ids": ["2_bklog.not_exists"]})

    assert result == {
        "items": [
            {
                "table_id": "2_bklog.not_exists",
                "data": None,
                "error": {
                    "code": "RESULT_TABLE_NOT_FOUND",
                    "message": "结果表不存在: table_id=2_bklog.not_exists",
                    "details": {"table_id": "2_bklog.not_exists"},
                },
            }
        ]
    }


def test_batch_service_preserves_input_order_and_isolates_table_failure(mocker):
    def query(service):
        if service.table_id == "2_bklog.missing":
            raise ValueError(f"结果表不存在: table_id={service.table_id}")
        return {"result_table": {"table_id": service.table_id}}

    mocker.patch.object(ResultTableStorageStatusService, "query", autospec=True, side_effect=query)

    result = ResultTableStorageStatusBatchService(
        bk_tenant_id=TENANT_ID,
        table_ids=["2_bklog.second", "2_bklog.missing", "2_bklog.first"],
    ).query()

    assert [item["table_id"] for item in result["items"]] == [
        "2_bklog.second",
        "2_bklog.missing",
        "2_bklog.first",
    ]
    assert result["items"][0]["data"]["result_table"]["table_id"] == "2_bklog.second"
    assert result["items"][1]["data"] is None
    assert result["items"][1]["error"]["code"] == "RESULT_TABLE_NOT_FOUND"
    assert result["items"][2]["data"]["result_table"]["table_id"] == "2_bklog.first"


def test_batch_service_stops_waiting_and_cancels_pending_tables_at_deadline(mocker):
    executor = BoundedExecutor(max_workers=1, max_queued_tasks=1, thread_name_prefix="test-storage-table-query")
    started = threading.Event()
    release = threading.Event()

    def query(_service):
        started.set()
        assert release.wait(timeout=3)
        return {}

    mocker.patch(
        "metadata.service.result_table_storage_status.shared_table_query_executor",
        executor,
    )
    mocker.patch.object(ResultTableStorageStatusService, "query", autospec=True, side_effect=query)

    try:
        result = ResultTableStorageStatusBatchService(
            bk_tenant_id=TENANT_ID,
            table_ids=["2_bklog.first", "2_bklog.second", "2_bklog.third"],
            total_timeout=1,
        ).query()
        assert started.is_set()
        assert [item["error"]["code"] for item in result["items"]] == [
            "BATCH_DEADLINE_EXCEEDED",
            "BATCH_DEADLINE_EXCEEDED",
            "BATCH_DEADLINE_EXCEEDED",
        ]
    finally:
        release.set()
        executor.shutdown()


def test_cluster_probe_scheduler_limits_same_cluster_to_five_concurrent_tasks():
    assert MAX_PROBE_WORKERS == 20
    assert MAX_PROBE_WORKERS_PER_CLUSTER == 5

    scheduler = ClusterProbeScheduler(max_workers=20, max_workers_per_cluster=5, max_queued_tasks=10)
    lock = threading.Lock()
    five_started = threading.Event()
    release = threading.Event()
    active = 0
    max_active = 0

    def probe(index):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
            if active == 5:
                five_started.set()
        try:
            assert release.wait(timeout=2)
            return index
        finally:
            with lock:
                active -= 1

    try:
        futures = [scheduler.submit((TENANT_ID, 1), probe, index) for index in range(6)]
        assert five_started.wait(timeout=1)
        assert max_active == 5

        release.set()
        assert [future.result(timeout=2) for future in futures] == list(range(6))
        assert max_active == 5
    finally:
        release.set()
        scheduler.shutdown()


def test_cluster_probe_scheduler_allows_different_clusters_in_parallel():
    scheduler = ClusterProbeScheduler(max_workers=2, max_workers_per_cluster=1, max_queued_tasks=2)
    barrier = threading.Barrier(2)

    def probe(cluster_id):
        barrier.wait(timeout=1)
        return cluster_id

    try:
        first_future = scheduler.submit((TENANT_ID, 1), probe, 1)
        second_future = scheduler.submit((TENANT_ID, 2), probe, 2)
        assert first_future.result(timeout=2) == 1
        assert second_future.result(timeout=2) == 2
    finally:
        scheduler.shutdown()


def test_cluster_probe_scheduler_rejects_when_bounded_queue_stays_full():
    scheduler = ClusterProbeScheduler(max_workers=1, max_workers_per_cluster=1, max_queued_tasks=1)
    started = threading.Event()
    release = threading.Event()

    def probe():
        started.set()
        assert release.wait(timeout=2)

    try:
        first = scheduler.submit((TENANT_ID, 1), probe)
        assert started.wait(timeout=1)
        second = scheduler.submit((TENANT_ID, 1), probe)
        with pytest.raises(SchedulerQueueFullError):
            scheduler.submit((TENANT_ID, 1), probe, enqueue_timeout=0)

        release.set()
        first.result(timeout=2)
        second.result(timeout=2)
    finally:
        release.set()
        scheduler.shutdown()


@pytest.mark.django_db(databases="__all__")
def test_runtime_error_is_returned_without_failing_whole_response(mocker):
    table_id = "2_bklog.storage_partial"
    _create_result_table(table_id, models.ClusterInfo.TYPE_DORIS)
    cluster = _create_cluster(94001, models.ClusterInfo.TYPE_DORIS)
    models.DorisStorage.objects.create(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        storage_cluster_id=cluster.cluster_id,
        bkbase_table_id="2_bklog_storage_partial",
    )
    _create_segment(
        table_id,
        cluster.cluster_id,
        datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        is_current=True,
    )
    mocker.patch.object(models.ClusterInfo, "check_connectivity", autospec=True, side_effect=_available_connectivity)
    mocker.patch.object(
        models.DorisStorage,
        "query_physical_storage_metadata",
        return_value={
            "physical_metadata": {},
            "warnings": [],
            "errors": [{"code": "DORIS_PHYSICAL_METADATA_QUERY_FAILED", "message": "query timeout"}],
        },
    )

    result = ResultTableStorageStatusService(bk_tenant_id=TENANT_ID, table_id=table_id).query()

    assert result["errors"] == []
    cluster_result = result["cluster_results"][str(cluster.cluster_id)]
    assert cluster_result["runtime_skipped"] is False
    assert cluster_result["errors"] == [{"code": "DORIS_PHYSICAL_METADATA_QUERY_FAILED", "message": "query timeout"}]


@pytest.mark.django_db(databases="__all__")
def test_missing_cluster_and_other_tenant_history_are_reported_safely():
    table_id = "2_bklog.storage_missing_cluster"
    missing_cluster_id = 95001
    _create_result_table(table_id, models.ClusterInfo.TYPE_ES)
    models.ESStorage.objects.create(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        storage_cluster_id=missing_cluster_id,
        need_create_index=False,
    )
    own_segment = _create_segment(
        table_id,
        missing_cluster_id,
        datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        is_current=True,
    )
    models.StorageClusterRecord.objects.create(
        bk_tenant_id="other-tenant",
        table_id=table_id,
        cluster_id=96001,
        enable_time=datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc),
        is_current=False,
        creator="system",
    )

    result = ResultTableStorageStatusService(bk_tenant_id=TENANT_ID, table_id=table_id).query()

    assert [segment["id"] for segment in result["segments"]] == [own_segment.id]
    assert list(result["cluster_results"]) == [str(missing_cluster_id)]
    cluster_result = result["cluster_results"][str(missing_cluster_id)]
    assert cluster_result["is_current"] is True
    assert cluster_result["is_current_segment"] is True
    assert cluster_result["is_configured_current"] is True
    assert cluster_result["runtime_skipped"] is True
    assert cluster_result["errors"][0]["code"] == "STORAGE_CLUSTER_NOT_FOUND"


@pytest.mark.django_db(databases="__all__")
def test_storage_config_without_segment_is_still_reported_as_current(mocker):
    table_id = "2_bklog.config_without_segment"
    _create_result_table(table_id, models.ClusterInfo.TYPE_ES)
    cluster = _create_cluster(96002, models.ClusterInfo.TYPE_ES)
    models.ESStorage.objects.create(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        storage_cluster_id=cluster.cluster_id,
        need_create_index=False,
        index_set="external-*",
    )
    mocker.patch.object(models.ClusterInfo, "check_connectivity", autospec=True, side_effect=_available_connectivity)
    mocker.patch(
        "metadata.service.result_table_storage_status.query_es_storage_runtime",
        return_value=({"indices": {"count": 0, "items": []}, "aliases": {"queried": False}}, []),
    )

    result = ResultTableStorageStatusService(bk_tenant_id=TENANT_ID, table_id=table_id).query()

    cluster_result = result["cluster_results"][str(cluster.cluster_id)]
    assert cluster_result["is_current"] is True
    assert cluster_result["is_current_segment"] is False
    assert cluster_result["is_configured_current"] is True
    assert result["warnings"][0]["code"] == "STORAGE_CLUSTER_RECORD_MISSING"


def test_build_doris_storage_runtime_supports_case_differences_and_drops_raw_fields():
    runtime = build_doris_storage_runtime(
        {
            "request_table_id": "2_bklog.demo",
            "doris_binding": {
                "name": "demo",
                "namespace": "bklog",
                "status": {"PHASE": "Ok", "MESSAGE": "ready", "conditions": [{"raw": True}]},
                "physical_table_name": "db.demo",
                "physical_table_name_source": "spec.storage_config",
            },
            "physical_metadata": {
                "tables": [
                    {
                        "table_schema": "db",
                        "table_name": "demo",
                        "engine": "OLAP",
                        "table_rows": 12,
                        "data_length": 4096,
                        "unbounded_field": "ignored",
                    }
                ],
                "columns": [
                    {
                        "column_name": "value",
                        "ordinal_position": 2,
                        "is_nullable": "YES",
                        "column_type": "double",
                    }
                ],
                "partitions": [
                    {
                        "partition_name": "p1",
                        "partition_method": "RANGE",
                        "partition_description": "LESS THAN ('2026-08-04')",
                    }
                ],
            },
        },
        connection_cluster_id=42,
        is_historical_cluster=True,
    )

    assert runtime == {
        "request_table_id": "2_bklog.demo",
        "metadata_context": {
            "connection_cluster_id": 42,
            "is_historical_cluster": True,
            "binding_source": "current_doris_binding",
            "historical_binding_snapshot_available": False,
        },
        "binding": {
            "name": "demo",
            "namespace": "bklog",
            "phase": "Ok",
            "message": "ready",
            "physical_table_name": "db.demo",
            "physical_table_name_source": "spec.storage_config",
        },
        "table": {"schema": "db", "name": "demo", "engine": "OLAP", "rows": 12, "data_length_bytes": 4096},
        "columns": [{"name": "value", "position": 2, "is_nullable": True, "column_type": "double"}],
        "partitions": [{"name": "p1", "method": "RANGE", "description": "LESS THAN ('2026-08-04')"}],
    }


@pytest.mark.django_db(databases="__all__")
def test_historical_doris_uses_current_binding_with_explicit_best_effort_context(mocker):
    table_id = "2_bklog.doris_history"
    _create_result_table(table_id, models.ClusterInfo.TYPE_DORIS)
    old_cluster = _create_cluster(97001, models.ClusterInfo.TYPE_DORIS)
    current_cluster = _create_cluster(97002, models.ClusterInfo.TYPE_DORIS)
    models.DorisStorage.objects.create(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        storage_cluster_id=current_cluster.cluster_id,
        bkbase_table_id="2_bklog_doris_history",
    )
    _create_segment(
        table_id,
        old_cluster.cluster_id,
        datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc),
        is_current=False,
    )
    _create_segment(
        table_id,
        current_cluster.cluster_id,
        datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
        is_current=True,
    )
    mocker.patch.object(models.ClusterInfo, "check_connectivity", autospec=True, side_effect=_available_connectivity)
    mocker.patch.object(
        models.DorisStorage,
        "query_physical_storage_metadata",
        return_value={
            "request_table_id": table_id,
            "doris_binding": {
                "physical_table_name": "current_db.current_table",
                "physical_table_name_source": "metadata.annotations.PhysicalTableName",
            },
            "physical_metadata": {},
            "warnings": [],
            "errors": [],
        },
    )

    result = ResultTableStorageStatusService(bk_tenant_id=TENANT_ID, table_id=table_id).query()

    old_result = result["cluster_results"][str(old_cluster.cluster_id)]
    current_result = result["cluster_results"][str(current_cluster.cluster_id)]
    assert old_result["is_current"] is False
    assert old_result["runtime"]["metadata_context"] == {
        "connection_cluster_id": old_cluster.cluster_id,
        "is_historical_cluster": True,
        "binding_source": "current_doris_binding",
        "historical_binding_snapshot_available": False,
    }
    assert "HISTORICAL_DORIS_BINDING_NOT_SNAPSHOTTED" in {warning["code"] for warning in old_result["warnings"]}
    assert current_result["runtime"]["metadata_context"]["is_historical_cluster"] is False


@pytest.mark.django_db(databases="__all__")
def test_conflicting_origin_tables_block_runtime_probe(mocker):
    table_id = "2_bklog.origin_conflict"
    _create_result_table(table_id, models.ClusterInfo.TYPE_ES)
    es_cluster = _create_cluster(98001, models.ClusterInfo.TYPE_ES)
    doris_cluster = _create_cluster(98002, models.ClusterInfo.TYPE_DORIS)
    models.ESStorage.objects.create(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        origin_table_id="2_bklog.origin_es",
        storage_cluster_id=es_cluster.cluster_id,
        need_create_index=False,
        index_set="external-*",
    )
    models.DorisStorage.objects.create(
        bk_tenant_id=TENANT_ID,
        table_id=table_id,
        origin_table_id="2_bklog.origin_doris",
        storage_cluster_id=doris_cluster.cluster_id,
        bkbase_table_id="2_bklog_origin_doris",
    )
    connectivity_check = mocker.patch.object(models.ClusterInfo, "check_connectivity")

    result = ResultTableStorageStatusService(bk_tenant_id=TENANT_ID, table_id=table_id).query()

    assert result["history_table_id"] is None
    assert result["segments"] == []
    assert result["cluster_results"] == {}
    assert result["errors"][0]["code"] == "STORAGE_ORIGIN_TABLE_CONFLICT"
    connectivity_check.assert_not_called()
