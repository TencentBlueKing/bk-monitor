"""业务存储关联回归：真实 ORM 关联、租户边界、共存和批量查询。"""

import json
from concurrent.futures import Future
from unittest import mock

import pytest
from django.db import connections
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from bkmonitor.views.resource_storage import QueryResourceStorageSerializer
from metadata import models
from metadata.models.record_rule.v4.models import RecordRuleV4
from metadata.resources.resource_storage import QueryResourceStorageResource
from metadata.service.resource_storage import ResourceStorageQuery

pytestmark = pytest.mark.django_db(databases="__all__")


def create_source(data_id, table_ids, tenant="system", name=None, **kwargs):
    models.DataSource.objects.bulk_create(
        [
            models.DataSource(
                bk_data_id=data_id,
                bk_tenant_id=tenant,
                data_name=name or f"source_{data_id}",
                data_description="test",
                mq_cluster_id=0,
                mq_config_id=0,
                etl_config="bk_standard_v2_time_series",
                is_custom_source=False,
                creator="test",
                last_modify_user="test",
                **kwargs,
            )
        ]
    )
    for table in table_ids:
        models.ResultTable.objects.bulk_create(
            [
                models.ResultTable(
                    table_id=table,
                    bk_tenant_id=tenant,
                    table_name_zh=table,
                    is_custom_table=False,
                    schema_type="fixed",
                    default_storage="influxdb",
                    creator="test",
                    last_modify_user="test",
                    bk_biz_id=0,
                )
            ]
        )
        models.DataSourceResultTable.objects.bulk_create(
            [
                models.DataSourceResultTable(
                    bk_data_id=data_id,
                    table_id=table,
                    bk_tenant_id=tenant,
                    creator="test",
                )
            ]
        )


def create_cluster(cluster_id, name, kind="victoria_metrics", tenant="system"):
    models.ClusterInfo.objects.bulk_create(
        [
            models.ClusterInfo(
                cluster_id=cluster_id,
                cluster_name=name,
                cluster_type=kind,
                bk_tenant_id=tenant,
                domain_name="private-storage.example",
                port=1234,
                description="test",
                is_default_cluster=False,
                username="secret-user",
                password="secret-password",
            )
        ]
    )


def ref(data_id=None, resource_id="1", **kwargs):
    return {
        "scene": "custom_metric",
        "resource_id": resource_id,
        "resource_name": "示例资源",
        "resource_status": "enabled",
        "data_type": "metric",
        "bk_data_id": data_id,
        "expand_tables": True,
        **kwargs,
    }


def query(resources, tenant="system", **kwargs):
    return ResourceStorageQuery(tenant, 100).query(
        **{
            "resources": resources,
            "selectors": [{"scene": "custom_metric"}],
            "include_runtime": False,
            "page": 1,
            "page_size": 100,
            **kwargs,
        }
    )


def test_retains_all_vm_mappings_and_separates_physical_binding():
    create_source(600001, ["plugin.metrics"])
    create_cluster(91, "vm-query")
    create_cluster(92, "vm-business-storage")
    models.AccessVMRecord.objects.bulk_create(
        [
            models.AccessVMRecord(
                result_table_id="plugin.metrics", bk_base_data_id=101, vm_result_table_id="vm_old", vm_cluster_id=91
            ),
            models.AccessVMRecord(
                result_table_id="plugin.metrics", bk_base_data_id=102, vm_result_table_id="vm_new", vm_cluster_id=91
            ),
        ]
    )
    models.ResultTableConfig.objects.bulk_create(
        [
            models.ResultTableConfig(
                bk_biz_id=100,
                bk_tenant_id="system",
                namespace="bkmonitor",
                name="new-rt",
                table_id="plugin.metrics",
                bkbase_table_id="vm_new",
            )
        ]
    )
    models.VMStorageBindingConfig.objects.bulk_create(
        [
            models.VMStorageBindingConfig(
                bk_biz_id=100,
                bk_tenant_id="system",
                namespace="bkmonitor",
                name="new-binding",
                table_id="plugin.metrics",
                bkbase_result_table_name="new-rt",
                vm_cluster_name="vm-business-storage",
            )
        ]
    )
    with mock.patch.object(ResourceStorageQuery, "add_runtime") as runtime:
        item = query([ref(600001)])["items"][0]
    runtime.assert_not_called()
    assert {(s["role"], s["table"], s["cluster"]["cluster_name"]) for s in item["storages"]} == {
        ("query", "vm_old", "vm-query"),
        ("query", "vm_new", "vm-query"),
        ("storage", "vm_new", "vm-business-storage"),
    }
    assert "private-storage" not in json.dumps(item)
    assert "secret-" not in json.dumps(item)


def test_legacy_vm_mapping_does_not_claim_physical_cluster():
    create_source(600002, ["legacy.metrics"])
    models.AccessVMRecord.objects.bulk_create(
        [
            models.AccessVMRecord(
                result_table_id="legacy.metrics",
                bk_base_data_id=200,
                vm_result_table_id="legacy_vm",
                vm_cluster_id=91,
            )
        ]
    )
    storages = query([ref(600002)])["items"][0]["storages"]
    assert len(storages) == 1
    assert storages[0]["role"] == "query"


def test_duplicate_result_table_names_do_not_cross_tenants():
    create_source(600003, ["shared.name"], tenant="tenant-a")
    create_source(600004, ["shared.name"], tenant="tenant-b")
    models.KafkaStorage.objects.bulk_create(
        [
            models.KafkaStorage(
                table_id="shared.name", bk_tenant_id="tenant-a", topic="a_topic", partition=1, storage_cluster_id=1
            ),
            models.KafkaStorage(
                table_id="shared.name", bk_tenant_id="tenant-b", topic="b_topic", partition=1, storage_cluster_id=2
            ),
        ]
    )
    result = query([ref(600003)], tenant="tenant-a")
    assert result["total"] == 1
    assert result["items"][0]["bk_data_id"] == 600003
    assert {k["topic"] for k in result["items"][0]["kafka"] if k["stage"] == "cleaned"} == {"a_topic"}
    missing = query([ref(600004)], tenant="tenant-a")["items"][0]
    assert missing["result_table_id"] is None
    assert missing["errors"]


def test_builtin_source_uses_tenant_result_tables_before_shared_tables(settings):
    settings.SNAPSHOT_DATAID = 1001
    create_source(1001, ["system.cpu"], is_platform_data_id=True)
    models.ResultTable.objects.bulk_create(
        [
            models.ResultTable(
                table_id="system.cpu@tenant-a",
                bk_tenant_id="tenant-a",
                table_name_zh="cpu",
                is_custom_table=False,
                schema_type="fixed",
                default_storage="influxdb",
                creator="test",
                last_modify_user="test",
            )
        ]
    )
    models.DataSourceResultTable.objects.bulk_create(
        [
            models.DataSourceResultTable(
                bk_data_id=1001,
                table_id="system.cpu@tenant-a",
                bk_tenant_id="tenant-a",
                creator="test",
            )
        ]
    )
    result = query([ref(1001, is_builtin=True)], tenant="tenant-a")
    assert [row["result_table_id"] for row in result["items"]] == ["system.cpu@tenant-a"]


def test_explicit_apm_table_does_not_expand_other_shared_tables():
    create_source(600005, ["apm.first", "apm.second"])
    result = query([ref(600005, table_id="apm.first", expand_tables=False)])
    assert [row["result_table_id"] for row in result["items"]] == ["apm.first"]


def test_apm_shared_and_business_bindings_resolve_their_actual_tenants():
    from apm.models import ApmApplication
    from apm.models.datasource import MetricDataSource, TraceDataSource
    from monitor_web.scene_view.resources.resource_storage import apm_references

    ApmApplication.objects.bulk_create(
        [ApmApplication(bk_tenant_id="tenant-a", bk_biz_id=100, app_name="checkout", app_alias="结算")]
    )
    TraceDataSource.objects.bulk_create(
        [
            TraceDataSource(
                bk_biz_id=100,
                app_name="checkout",
                bk_data_id=600051,
                result_table_id="apm.shared_trace",
                shared_datasource_id=1,
            )
        ]
    )
    MetricDataSource.objects.bulk_create(
        [MetricDataSource(bk_biz_id=100, app_name="checkout", bk_data_id=600052, result_table_id="apm.metric")]
    )
    create_source(600051, ["apm.shared_trace"])
    create_source(600052, ["apm.metric"], tenant="tenant-a")
    create_source(600053, ["apm.shared_trace"], tenant="tenant-a")
    create_cluster(51, "shared-es", kind="elasticsearch")
    create_cluster(52, "business-es", kind="elasticsearch", tenant="tenant-a")
    models.ESStorage.objects.bulk_create(
        [
            models.ESStorage(table_id="apm.shared_trace", index_set="shared_trace", storage_cluster_id=51),
            models.ESStorage(
                table_id="apm.shared_trace",
                bk_tenant_id="tenant-a",
                index_set="other_trace",
                storage_cluster_id=52,
            ),
        ]
    )
    references = apm_references("tenant-a", 100)
    serializer = QueryResourceStorageResource.RequestSerializer(
        data={"bk_biz_id": 100, "bk_tenant_id": "tenant-a", "resources": references}
    )
    assert serializer.is_valid(), serializer.errors
    references = serializer.validated_data["resources"]
    connection = connections[models.DataSource.objects.db]
    with CaptureQueriesContext(connection) as single:
        result = query(references, tenant="tenant-a", selectors=[{"scene": "apm"}])
    with CaptureQueriesContext(connection) as batch:
        batch_result = query(
            [{**reference, "resource_id": f"app-{index}"} for index in range(40) for reference in references],
            tenant="tenant-a",
            selectors=[{"scene": "apm"}],
        )
    assert batch_result["total"] == 80
    assert len(single) == len(batch)
    rows = {row["data_type"]: row for row in result["items"]}
    assert rows["metric"]["bk_data_id"] == 600052
    assert rows["trace"]["bk_data_id"] == 600051
    assert rows["trace"]["errors"] == []
    assert rows["trace"]["storages"][0]["cluster"]["cluster_name"] == "shared-es"
    ordinary = query([ref(600051)], tenant="tenant-a")["items"][0]
    assert ordinary["result_table_id"] is None and ordinary["errors"]


def test_missing_explicit_data_source_does_not_use_another_tables_data_id():
    create_source(600054, ["apm.metric"])
    item = query([ref(600055, table_id="apm.metric", expand_tables=False)])["items"][0]
    assert item["bk_data_id"] == 600055
    assert item["result_table_id"] == "apm.metric"
    assert "未找到数据源与结果表关联" in item["errors"]


def test_split_tables_and_cmdb_relationships_are_retained():
    create_source(600006, ["custom.base", "custom.cpu"])
    create_source(600007, ["custom.cmdb"])
    models.CMDBLevelRecord.objects.bulk_create(
        [
            models.CMDBLevelRecord(
                source_table_id="custom.base",
                target_table_id="custom.cmdb",
                bk_data_id=600007,
                cmdb_level="module",
                bk_tenant_id="system",
            )
        ]
    )
    result = query([ref(600006), ref(600006)])
    assert result["total"] == 3
    assert {(row["bk_data_id"], row["result_table_id"]) for row in result["items"]} == {
        (600006, "custom.base"),
        (600006, "custom.cpu"),
        (600007, "custom.cmdb"),
    }


def test_pagination_is_stable_and_precedes_storage_queries():
    create_source(600008, ["custom.c", "custom.a", "custom.b"])
    with mock.patch.object(
        ResourceStorageQuery, "prefetch_storage", wraps=ResourceStorageQuery.prefetch_storage
    ) as prefetch:
        result = query([ref(600008)], page=2, page_size=1)
    assert result["total"] == 3
    assert [row["result_table_id"] for row in result["items"]] == ["custom.b"]
    assert len(prefetch.call_args.args[1]) == 1


def test_storage_query_count_does_not_grow_with_result_rows():
    create_source(600009, [f"batch.table_{index:03}" for index in range(40)])
    models.KafkaStorage.objects.bulk_create(
        [
            models.KafkaStorage(
                table_id=f"batch.table_{index:03}", topic=f"topic_{index}", partition=1, storage_cluster_id=10
            )
            for index in range(40)
        ]
    )
    connection = connections[models.DataSource.objects.db]
    with CaptureQueriesContext(connection) as single:
        query([ref(600009, table_id="batch.table_000", expand_tables=False)])
    with CaptureQueriesContext(connection) as batch:
        result = query([ref(600009)])
    assert len(result["items"]) == 40
    assert len(batch) == len(single)
    assert not any(statement["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for statement in batch)


def test_row_assembly_performs_no_queries():
    create_source(600010, ["custom.base"])
    service = ResourceStorageQuery("system", 100)
    rows = service.resolve_references([ref(600010)])
    context = service.prefetch_storage("system", rows)
    with CaptureQueriesContext(connections[models.DataSource.objects.db]) as queries:
        service.add_storage(rows[0], context)
    assert len(queries) == 0


def test_runtime_deduplicates_shared_link_and_filters_other_tables():
    create_source(600011, ["runtime.a", "runtime.b"])
    payload = {
        "branches": [
            {
                "result_table_id": "runtime.a",
                "kafka_host": "private:9092",
                "kafka_shipper_topic_name": "topic_a",
                "token": "secret",
            },
            {"result_table_id": "another_business", "kafka_shipper_topic_name": "private_topic"},
        ]
    }
    with mock.patch(
        "metadata.resources.bkdata_link.QueryDataLinkMetadataResource._fetch_bkbase_metadata", return_value=payload
    ) as fetch:
        result = query([ref(600011)], include_runtime=True)
    fetch.assert_called_once_with(600011, None, bk_tenant_id="system", timeout=3)
    assert result["items"][0]["runtime"]["bkbase"] == [
        {"result_table_id": "runtime.a", "kafka_shipper_topic_name": "topic_a"}
    ]
    assert result["items"][1]["runtime"]["bkbase"] == []
    assert "private" not in json.dumps(result)
    assert "secret" not in json.dumps(result)


def test_runtime_failure_preserves_configuration_and_hides_exception_details():
    create_source(600012, ["runtime.failed"])
    with mock.patch(
        "metadata.resources.bkdata_link.QueryDataLinkMetadataResource._fetch_bkbase_metadata",
        return_value={"_error": "private:9092 secret"},
    ):
        result = query([ref(600012)], include_runtime=True)
    assert result["items"][0]["result_table_id"] == "runtime.failed"
    assert result["items"][0]["runtime"]["errors"]
    assert "private" not in json.dumps(result)


def test_runtime_deadline_keeps_completed_results_and_marks_pending_requests():
    create_source(600056, ["runtime.done"])
    create_source(600057, ["runtime.pending"])
    completed = Future()
    completed.set_result({"branches": [{"result_table_id": "runtime.done"}]})
    pending = Future()
    executor = mock.Mock()
    executor.submit.side_effect = [completed, pending]
    with (
        mock.patch("metadata.service.resource_storage.ThreadPoolExecutor", return_value=executor),
        mock.patch("metadata.service.resource_storage.RUNTIME_TIMEOUT_SECONDS", 0),
    ):
        result = query([ref(600056, resource_id="1"), ref(600057, resource_id="2")], include_runtime=True)
    assert result["items"][0]["runtime"]["bkbase"] == [{"result_table_id": "runtime.done"}]
    assert result["items"][1]["result_table_id"] == "runtime.pending"
    assert result["items"][1]["runtime"]["errors"] == [{"source": "bkbase", "message": "运行信息查询失败或超时"}]
    executor.shutdown.assert_called_once_with(wait=False, cancel_futures=True)


def test_runtime_bkbase_timeout_reaches_http_client():
    from api.bkdata.default import GetDataLinkMetadataResource
    from metadata.resources.bkdata_link import QueryDataLinkMetadataResource

    client = GetDataLinkMetadataResource()
    client.session.get = mock.Mock()
    client.session.get.return_value.json.return_value = {"result": True, "code": 0, "data": {"branches": []}}
    client.session.get.return_value.status_code = 200
    with (
        mock.patch("metadata.resources.bkdata_link.api.bkdata.get_data_link_metadata", side_effect=client.request),
        mock.patch.object(client, "get_headers", return_value={}),
        mock.patch.object(client, "full_request_data", side_effect=lambda data: data),
    ):
        result = QueryDataLinkMetadataResource()._fetch_bkbase_metadata(
            600058, None, bk_tenant_id="tenant-a", timeout=3
        )
    assert result == {"branches": []}
    assert client.bk_tenant_id == "tenant-a"
    assert client.session.get.call_args.kwargs["timeout"] == 3


@pytest.mark.parametrize(
    "payload",
    [
        {"bk_biz_id": 100, "selectors": [{"scene": "unknown"}]},
        {"bk_biz_id": 100, "selectors": [{"scene": "recording_rule_v4"}]},
        {"bk_biz_id": 100, "selectors": [{"scene": "recording_rule", "data_types": ["trace"]}]},
        {"bk_biz_id": 100, "selectors": [{"scene": "bcs", "data_types": ["trace"]}]},
        {"bk_biz_id": 100, "page": 0},
        {"bk_biz_id": 100, "page_size": 1001},
    ],
)
def test_request_validation(payload):
    assert not QueryResourceStorageSerializer(data=payload).is_valid()


def test_internal_serializer_preserves_resource_references():
    serializer = QueryResourceStorageResource.RequestSerializer(
        data={
            "bk_biz_id": 100,
            "bk_tenant_id": "system",
            "resources": [ref(600013)],
        }
    )
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["resources"][0]["bk_data_id"] == 600013


def test_bcs_six_data_types_and_federal_tables():
    for index in range(6):
        create_source(600020 + index, [f"bcs.type_{index}"])
    cluster = models.BCSClusterInfo(
        cluster_id="BCS-K8S-1",
        bcs_api_cluster_id="BCS-K8S-1",
        bk_biz_id=100,
        bk_tenant_id="system",
        project_id="p",
        domain_name="private",
        port=443,
        K8sMetricDataID=600020,
        CustomMetricDataID=600021,
        K8sEventDataID=600022,
        CustomEventDataID=600023,
        SystemLogDataID=600024,
        CustomLogDataID=600025,
    )
    models.BCSClusterInfo.objects.bulk_create([cluster])
    create_source(600026, ["bcs.federal"])
    models.BcsFederalClusterInfo.objects.bulk_create(
        [
            models.BcsFederalClusterInfo(
                bk_tenant_id="system",
                fed_cluster_id="BCS-K8S-1",
                sub_cluster_id="BCS-K8S-2",
                host_cluster_id="BCS-K8S-3",
                fed_builtin_metric_table_id="bcs.federal",
            )
        ]
    )
    result = query([], selectors=[{"scene": "bcs"}])
    assert result["total"] == 7
    selected = query([], selectors=[{"scene": "bcs", "resource_ids": ["BCS-K8S-1"], "data_types": ["k8s_metric"]}])
    assert {row["result_table_id"] for row in selected["items"]} == {"bcs.type_0", "bcs.federal"}


def test_host_legacy_and_business_data_coexist_when_multitenancy_enabled(settings):
    create_source(1001, ["system.cpu"], is_platform_data_id=True)
    create_source(600030, ["business.cpu"], name="business_base", space_uid="bkcc__100")
    models.DataSource.objects.filter(bk_data_id=1001).update(etl_config="bk_system_basereport")
    models.DataSource.objects.filter(bk_data_id=600030).update(etl_config="bk_multi_tenancy_basereport")
    settings.ENABLE_MULTI_TENANT_MODE = True
    result = query([], selectors=[{"scene": "host"}])
    assert {row["bk_data_id"] for row in result["items"]} == {1001, 600030}


def test_kafka_stages_and_multiple_cleaned_mappings():
    create_source(600040, ["kafka.metrics_a", "kafka.metrics_b"])
    create_cluster(41, "entry", kind="kafka")
    create_cluster(42, "cleaned", kind="kafka")
    topic = models.KafkaTopicInfo(bk_data_id=600040, topic="raw_topic", partition=1)
    models.KafkaTopicInfo.objects.bulk_create([topic])
    models.DataSource.objects.filter(bk_data_id=600040).update(mq_cluster_id=41, mq_config_id=topic.pk)
    models.KafkaStorage.objects.bulk_create(
        [
            models.KafkaStorage(table_id="kafka.metrics_a", topic="cleaned_a", partition=1, storage_cluster_id=42),
            models.KafkaStorage(table_id="kafka.metrics_b", topic="cleaned_b", partition=1, storage_cluster_id=42),
        ]
    )
    kafka = [stage for row in query([ref(600040)])["items"] for stage in row["kafka"]]
    assert {(item["stage"], item["topic"], item["cluster"]["cluster_id"]) for item in kafka} == {
        ("ingestion", "raw_topic", 41),
        ("cleaned", "cleaned_a", 42),
        ("cleaned", "cleaned_b", 42),
    }


def test_virtual_storages_follow_explicit_physical_records():
    create_source(600041, ["logs.virtual"])
    models.ESStorage.objects.bulk_create(
        [
            models.ESStorage(
                table_id="logs.virtual", origin_table_id="logs.physical", index_set="virtual", storage_cluster_id=1
            ),
            models.ESStorage(table_id="logs.physical", index_set="real_es_index", storage_cluster_id=42),
        ]
    )
    models.DorisStorage.objects.bulk_create(
        [
            models.DorisStorage(
                table_id="logs.virtual",
                origin_table_id="logs.physical",
                bkbase_table_id="virtual",
                storage_cluster_id=1,
            ),
            models.DorisStorage(table_id="logs.physical", bkbase_table_id="real_doris_table", storage_cluster_id=43),
        ]
    )
    storages = query([ref(600041)])["items"][0]["storages"]
    assert {(s["type"], s["table"], s["cluster"]["cluster_id"]) for s in storages} == {
        ("elasticsearch", "real_es_index", 42),
        ("doris", "real_doris_table", 43),
    }


def test_runtime_es_queries_once_per_cluster_and_has_no_lazy_db_access():
    create_source(600042, ["logs.a", "logs.b"])
    create_cluster(44, "es", kind="elasticsearch")
    models.ESStorage.objects.bulk_create(
        [models.ESStorage(table_id=table, index_set=table, storage_cluster_id=44) for table in ("logs.a", "logs.b")]
    )
    client = mock.Mock()
    client.cat.indices.return_value = [
        {"index": "logs_a_20261022_0"},
        {"index": "logs_b_20261022_0"},
        {"index": "private_other_20261022_0"},
    ]
    with (
        mock.patch("metadata.utils.es_tools.get_client_by_datasource_info", return_value=client) as build_client,
        mock.patch(
            "metadata.resources.bkdata_link.QueryDataLinkMetadataResource._fetch_bkbase_metadata",
            return_value={"branches": []},
        ),
        mock.patch.object(models.ESStorage, "get_client", side_effect=AssertionError("lazy client query")),
    ):
        result = query([ref(600042)], include_runtime=True)
    build_client.assert_called_once()
    client.cat.indices.assert_called_once()
    assert result["items"][0]["runtime"]["elasticsearch"][0]["indices"] == ["logs_a_20261022_0"]
    assert result["items"][1]["runtime"]["elasticsearch"][0]["indices"] == ["logs_b_20261022_0"]


def test_vm_same_resource_name_in_another_namespace_is_not_attached():
    create_source(600043, ["vm.metrics"])
    models.ResultTableConfig.objects.bulk_create(
        [
            models.ResultTableConfig(
                bk_biz_id=100,
                bk_tenant_id="system",
                namespace="owned",
                name="metrics",
                table_id="vm.metrics",
                bkbase_table_id="vm_owned",
            )
        ]
    )
    models.VMStorageBindingConfig.objects.bulk_create(
        [
            models.VMStorageBindingConfig(
                bk_biz_id=100,
                bk_tenant_id="system",
                namespace=namespace,
                name=f"binding-{namespace}",
                bkbase_result_table_name="metrics",
                vm_cluster_name=f"vm-{namespace}",
            )
            for namespace in ("owned", "other")
        ]
    )
    storages = query([ref(600043)])["items"][0]["storages"]
    assert [item["cluster"]["cluster_name"] for item in storages] == ["vm-owned"]


def test_influxdb_proxy_and_instance_cluster_are_distinct():
    create_source(600044, ["system.cpu"])
    create_cluster(45, "influx-proxy", kind="influxdb")
    proxy = models.InfluxDBProxyStorage(
        proxy_cluster_id=45, service_name="proxy", instance_cluster_name="influx-instance"
    )
    models.InfluxDBProxyStorage.objects.bulk_create([proxy])
    models.InfluxDBStorage.objects.bulk_create(
        [
            models.InfluxDBStorage(
                table_id="system.cpu",
                storage_cluster_id=45,
                real_table_name="cpu",
                database="system",
                source_duration_time="30d",
                influxdb_proxy_storage_id=proxy.pk,
            )
        ]
    )
    storage = query([ref(600044)])["items"][0]["storages"][0]
    assert storage["table"] == "cpu"
    assert storage["database"] == "system"
    assert storage["cluster"]["cluster_name"] == "influx-instance"
    assert storage["query_cluster"]["cluster_name"] == "influx-proxy"


@pytest.mark.parametrize("multi_tenant", [False, True])
def test_uptime_same_business_queries_both_saved_storage_routes(settings, multi_tenant):
    from monitor.models import UptimeCheckTask
    from monitor_web.scene_view.resources.resource_storage import uptime_references

    settings.ENABLE_MULTI_TENANT_MODE = multi_tenant
    settings.ENABLE_UPTIMECHECK_BKDATA = True
    settings.UPTIMECHECK_HTTP_DATAID = 1011
    UptimeCheckTask.objects.bulk_create(
        [
            UptimeCheckTask(id=12, bk_biz_id=100, name="legacy", protocol="HTTP", indepentent_dataid=False),
            UptimeCheckTask(id=34, bk_biz_id=100, name="business", protocol="HTTP", indepentent_dataid=True),
        ]
    )
    create_source(1011, ["uptimecheck.http"], is_platform_data_id=True)
    create_source(600045, ["business.http"], name="uptimecheck_http_100")
    models.KafkaStorage.objects.bulk_create(
        [
            models.KafkaStorage(table_id="uptimecheck.http", topic="shared_topic", partition=1, storage_cluster_id=1),
            models.KafkaStorage(table_id="business.http", topic="business_topic", partition=1, storage_cluster_id=2),
        ]
    )
    result = query(uptime_references(100), selectors=[{"scene": "uptime_check"}])
    assert {(item["resource_id"], item["bk_data_id"], item["kafka"][0]["topic"]) for item in result["items"]} == {
        ("12", 1011, "shared_topic"),
        ("34", 600045, "business_topic"),
    }


def create_recording_rule(rule_id, create_output=True, **fields):
    rule = RecordRuleV4(
        **{
            "id": rule_id,
            "name": f"规则组 {rule_id}",
            "bk_tenant_id": "system",
            "space_type": "bkcc",
            "space_id": "100",
            "flow_name": f"rule_{rule_id}",
            "table_id": f"recording_rule.group_{rule_id}",
            "dst_vm_table_id": f"vm_rule_{rule_id}",
            "dst_vm_storage_name": "vm-business-storage",
            **fields,
        }
    )
    RecordRuleV4.objects.bulk_create([rule])
    if create_output:
        models.ResultTable.objects.bulk_create(
            [
                models.ResultTable(
                    table_id=rule.table_id,
                    bk_tenant_id=rule.bk_tenant_id,
                    table_name_zh=rule.name,
                    is_custom_table=False,
                    schema_type="fixed",
                    default_storage="victoria_metrics",
                    creator="test",
                    last_modify_user="test",
                )
            ]
        )
    return rule


def test_recording_rule_uses_v4_output_without_data_source_or_local_binding():
    rule = create_recording_rule(1, desired_status="stopped")
    create_cluster(91, "vm-query")
    create_cluster(92, "vm-business-storage")
    models.AccessVMRecord.objects.bulk_create(
        [
            models.AccessVMRecord(
                result_table_id=rule.table_id,
                bk_base_data_id=0,
                vm_result_table_id=rule.dst_vm_table_id,
                vm_cluster_id=91,
            )
        ]
    )
    models.RecordRule.objects.bulk_create(
        [models.RecordRule(space_type="bkcc", space_id="100", table_id="legacy.rule", record_name="旧版规则")]
    )
    with mock.patch.object(ResourceStorageQuery, "add_runtime") as runtime:
        result = query([], selectors=[])
    runtime.assert_not_called()
    assert result["total"] == 1
    item = result["items"][0]
    assert (item["scene"], item["resource_id"], item["resource_status"]) == ("recording_rule", "1", "stopped")
    assert item["result_table_id"] == rule.table_id
    assert item["result_table_name"] == rule.name
    assert item["bk_data_id"] is None and item["data_name"] is None
    assert item["kafka"] == [] and item["errors"] == []
    assert {(s["role"], s["table"], s["cluster"]["cluster_id"]) for s in item["storages"]} == {
        ("query", rule.dst_vm_table_id, 91),
        ("storage", rule.dst_vm_table_id, 92),
    }
    assert not any(key.startswith("_") for key in item)
    assert "private-storage" not in json.dumps(item)
    assert "secret-" not in json.dumps(item)


def test_recording_rule_filters_tenant_business_deleted_and_requested_groups():
    rule = create_recording_rule(1, bk_tenant_id="tenant-a")
    create_recording_rule(2, bk_tenant_id="tenant-b", table_id=rule.table_id, dst_vm_table_id=rule.dst_vm_table_id)
    create_recording_rule(3, bk_tenant_id="tenant-a", space_id="200")
    create_recording_rule(4, bk_tenant_id="tenant-a", deleted_at=timezone.now())
    create_recording_rule(5, bk_tenant_id="tenant-a", desired_status="deleted")
    create_recording_rule(6, bk_tenant_id="tenant-a")
    create_cluster(91, "vm-business-storage", tenant="tenant-a")
    create_cluster(92, "vm-business-storage", tenant="tenant-b")
    result = query([], tenant="tenant-a", selectors=[{"scene": "recording_rule"}])
    assert [row["resource_id"] for row in result["items"]] == ["1", "6"]
    assert result["items"][0]["storages"][0]["cluster"]["cluster_id"] == 91
    selected = query(
        [], tenant="tenant-a", selectors=[{"scene": "recording_rule", "resource_ids": ["6"], "data_types": ["metric"]}]
    )
    assert [row["resource_id"] for row in selected["items"]] == ["6"]
    assert query([], tenant="tenant-a", selectors=[{"scene": "recording_rule", "resource_ids": ["99"]}])["total"] == 0


def test_recording_rule_resolves_business_space_once():
    create_recording_rule(1, space_type="bkci", space_id="project-a")
    create_recording_rule(2, space_type="bkci", space_id="project-b")
    with mock.patch("bkm_space.utils.bk_biz_id_to_space_uid", return_value="bkci__project-a") as resolve:
        result = query([], selectors=[{"scene": "recording_rule"}])
    resolve.assert_called_once_with(100)
    assert [row["resource_id"] for row in result["items"]] == ["1"]


def test_recording_rule_excludes_soft_deleted_groups():
    create_recording_rule(1, is_deleted=True)
    create_recording_rule(2, desired_status="stopped")
    result = query([], selectors=[{"scene": "recording_rule"}])
    assert [row["resource_id"] for row in result["items"]] == ["2"]


def test_recording_rule_keeps_partial_output_without_inventing_storage():
    rule = create_recording_rule(1, create_output=False, dst_vm_storage_name="")
    create_cluster(91, "vm-default")
    item = query([], selectors=[{"scene": "recording_rule"}])["items"][0]
    assert item["result_table_id"] == rule.table_id
    assert item["errors"] == ["结果表元数据不存在"]
    assert item["storages"] == [
        {"type": "victoria_metrics", "table": rule.dst_vm_table_id, "role": "storage", "cluster": None}
    ]
    assert not models.ResultTable.objects.filter(table_id=rule.table_id).exists()
    assert not models.AccessVMRecord.objects.filter(result_table_id=rule.table_id).exists()


def test_recording_rule_storage_query_count_is_constant_and_row_assembly_is_sql_free():
    for index in range(1, 41):
        create_recording_rule(index)
    create_cluster(91, "vm-business-storage")
    connection = connections[RecordRuleV4.objects.db]
    with CaptureQueriesContext(connection) as single:
        query([], selectors=[{"scene": "recording_rule", "resource_ids": ["1"]}])
    with CaptureQueriesContext(connection) as batch:
        result = query([], selectors=[{"scene": "recording_rule"}])
    assert result["total"] == 40
    assert len(single) == len(batch)
    assert not any(statement["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for statement in batch)
    service = ResourceStorageQuery("system", 100)
    rows = service.recording_rule_rows([])
    context = service.prefetch_storage("system", rows)
    with CaptureQueriesContext(connection) as assembly:
        for row in rows:
            service.add_storage(row, context)
    assert len(assembly) == 0


def test_recording_rule_runtime_queries_output_table_once_and_only_on_current_page():
    rule = create_recording_rule(1)
    create_recording_rule(2)
    models.AccessVMRecord.objects.bulk_create(
        [
            models.AccessVMRecord(
                result_table_id=rule.table_id,
                bk_base_data_id=0,
                vm_result_table_id=rule.dst_vm_table_id,
                vm_cluster_id=91,
            )
        ]
    )
    with mock.patch(
        "metadata.resources.bkdata_link.QueryDataLinkMetadataResource._fetch_bkbase_metadata",
        return_value={"branches": [{"result_table_id": rule.dst_vm_table_id}, {"result_table_id": "other_business"}]},
    ) as fetch:
        result = query([], selectors=[{"scene": "recording_rule"}], include_runtime=True, page_size=1)
    fetch.assert_called_once_with(None, rule.dst_vm_table_id, bk_tenant_id="system", timeout=3)
    assert result["total"] == 2 and len(result["items"]) == 1
    assert result["items"][0]["runtime"]["bkbase"] == [{"result_table_id": rule.dst_vm_table_id}]


def test_recording_rule_runtime_failure_keeps_saved_output_without_vm_record():
    rule = create_recording_rule(1)
    with mock.patch(
        "metadata.resources.bkdata_link.QueryDataLinkMetadataResource._fetch_bkbase_metadata",
        side_effect=TimeoutError("private-host:1234 token=secret"),
    ) as fetch:
        item = query([], selectors=[{"scene": "recording_rule"}], include_runtime=True)["items"][0]
    fetch.assert_called_once_with(None, rule.dst_vm_table_id, bk_tenant_id="system", timeout=3)
    assert item["storages"][0]["table"] == rule.dst_vm_table_id
    assert item["runtime"]["errors"] == [{"source": "bkbase", "message": "运行信息查询失败或超时"}]
    assert "private-host" not in json.dumps(item) and "secret" not in json.dumps(item)
