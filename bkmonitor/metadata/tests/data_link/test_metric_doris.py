"""通过公开 RT 入口验证资源身份、独立停启和汇总换代。"""

import os
import time
from copy import deepcopy
from datetime import datetime
from zoneinfo import ZoneInfo
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from metadata import models
from metadata.config import DATABASE_CONNECTION_NAME
from metadata.models.data_link import DataBusConfig, DataIdConfig, DataLink, DorisJobConfig, MetricDorisPipeline
from metadata.models.data_link.constants import DataLinkKind
from metadata.models.data_link.utils import find_registered_bkdata_data_id_name
from metadata.resources.resources import CreateResultTableResource, ModifyResultTableResource
from metadata.service import doris_job
from metadata.service.metric_aggregate import successful_cutover
from metadata.service.metric_doris import compose_metric_configs
from metadata.service.metric_doris_reconcile import reconcile_pipeline

pytestmark = pytest.mark.django_db(databases=[DATABASE_CONNECTION_NAME])
RAW = "arbitrary_name.__default__"
AGG = "timeseries_agg_testing.__default__"
INGEST = {
    "metrics": ["rpc_client_handled_total", "rpc_client_handled_seconds_bucket"],
    "dimensions": {
        "service_name": "service_name",
        "le": "le",
        "caller_ip": "caller_ip",
        "11": "dimension_11",
        "target": "dimension_target",
    },
    "dimension_filters": {"service_name": "foo"},
    "task_num": 4,
}
AGGREGATE = {"source_table_id": RAW, "without": ["caller_ip"], "output_prefix": "sum_"}


def create(name, cluster=42, tenant="system", data_id=123456):
    return CreateResultTableResource()(
        bk_tenant_id=tenant,
        bk_data_id=data_id,
        bk_biz_id=2,
        operator="tester",
        table_id=name,
        table_name_zh=name,
        schema_type="free",
        is_custom_table=True,
        default_storage="doris",
        default_storage_config={
            "storage_cluster_id": cluster,
            "expire_days": 7,
            "doris_storage_config": {"replication_num": 1, "buckets": 1},
        },
        is_time_field_only=True,
        is_sync_db=False,
    )


def modify(name, **changes):
    return ModifyResultTableResource()(bk_tenant_id="system", table_id=name, operator="tester", **changes)


def pipeline(name):
    return MetricDorisPipeline.objects.get(result_table__table_id=name, result_table__bk_tenant_id="system")


@pytest.fixture
def setup_links(mocker, settings):
    settings.DEFAULT_BKDATA_BIZ_ID = 23456
    settings.ENABLE_MULTI_TENANT_MODE = False
    settings.DATA_LINK_COMPONENT_REUSE_STRATEGIES = set()
    models.Label.objects.get_or_create(label_id="others", defaults={"label_type": "result_table_label"})
    for cid, kind in ((41, "kafka"), (42, "doris"), (43, "doris")):
        models.ClusterInfo.objects.create(
            cluster_id=cid,
            cluster_type=kind,
            cluster_name=f"test{cid}",
            domain_name="localhost",
            port=9030,
            is_default_cluster=False,
            bk_tenant_id="system",
        )
    ds = models.DataSource.objects.create(
        bk_data_id=123456,
        bk_tenant_id="system",
        data_name="test_metrics",
        mq_cluster_id=41,
        mq_config_id=1,
        is_custom_source=False,
        etl_config="bk_standard_v2_time_series",
    )
    models.KafkaTopicInfo.objects.create(bk_data_id=ds.pk, topic="existing_topic", partition=4)
    DataIdConfig.objects.create(
        name="primary_metrics", bk_data_id=ds.pk, bk_biz_id=2, namespace="bkmonitor", bk_tenant_id="system"
    )
    vm = DataLink.objects.create(
        data_link_name="unrelated_vm",
        bk_data_id=ds.pk,
        bk_tenant_id="system",
        namespace="bkmonitor",
        data_link_strategy=DataLink.BK_STANDARD_V2_TIME_SERIES,
        table_ids=["original.__default__"],
    )
    DataBusConfig.objects.create(
        name="original_shipper",
        bk_data_id=ds.pk,
        bk_biz_id=2,
        bk_tenant_id="system",
        namespace="bkmonitor",
        data_link_name=vm.pk,
        consumer_group="existing_vm_group",
    )
    primary = {
        "metadata": {"name": "primary_metrics"},
        "spec": {
            "predefined": {
                "channel": {"kind": "KafkaChannel", "namespace": "bkmonitor", "name": "actual_channel"},
                "topic": "existing_topic",
                "dataId": ds.pk,
            }
        },
    }
    remote = {("bkmonitor", "dataids", "primary_metrics"): primary}

    def apply(*, config, bk_tenant_id):
        for item in config:
            meta = item["metadata"]
            remote[meta["namespace"], DataLinkKind.get_choice_value(item["kind"]), meta["name"]] = {
                **deepcopy(item),
                "status": {"phase": "Ok"},
            }

    def get(*, namespace, kind, name, **kwargs):
        return deepcopy(remote.get((namespace, kind, name)))

    mocker.patch("metadata.models.data_link.data_link.api.bkdata.get_data_link", side_effect=get)
    mocker.patch("metadata.models.data_link.data_link.api.bkdata.apply_data_link", side_effect=apply)
    mocker.patch("metadata.resources.resources.ModifyResultTableResource._push_result_table_routes")
    mocker.patch("metadata.service.metric_doris_reconcile.refresh_routes")
    mocker.patch("metadata.task.datalink.reconcile_metric_doris_rt.delay")
    return ds, remote


def test_independent_ingest_and_multiple_aggregates(setup_links, mocker):
    ds, remote = setup_links
    conn = mocker.patch("metadata.service.doris_job.connect_cluster")
    conn.return_value.cursor.return_value.__enter__.return_value.fetchone.return_value = {
        "Create Table": '"dynamic_partition.start" = "-7"'
    }
    create(RAW)
    modify(RAW, option={"metric_ingest": INGEST})
    raw = pipeline(RAW)
    reconcile_pipeline(raw.pk)
    raw.refresh_from_db()
    assert (raw.phase, raw.status_reason) == ("", "")
    ids = (raw.data_link_id, raw.output.name)
    configs = compose_metric_configs(raw.data_link, data_source=ds, table_id=RAW)
    alias, rt, binding, bus = configs
    assert alias["spec"]["eventType"] == "log"
    assert alias["spec"]["predefined"] == {
        "dataId": ds.pk,
        "topic": "existing_topic",
        "channel": {"kind": "KafkaChannel", "namespace": "bkmonitor", "name": "actual_channel"},
    }
    assert rt["metadata"]["name"].startswith("bkm_mdr_123456_")
    assert binding["spec"]["storage_config"]["table_type"] == "duplicate_table"
    assert (bus["spec"]["subTaskNum"], bus["spec"]["autoOffsetReset"]) == (4, "latest")
    assert bus["spec"]["sources"][0]["name"] == alias["metadata"]["name"]
    clean = bus["spec"]["transforms"][0]
    assert clean["filter_rules"]["And"]["lval"]["Or"]["rval"]["BinOp"]["Eq"]["rval"] == {
        "Const": "rpc_client_handled_seconds_bucket"
    }
    assert (
        dict((r["output_id"], r["operator"].get("key_index")) for r in clean["rules"])["dimension_11"]
        == 'dimension."11"'
    )
    assert list(
        models.ResultTableField.objects.filter(table_id=RAW, field_name="metric_value").values_list(
            "field_type", flat=True
        )
    ) == ["double"]
    assert find_registered_bkdata_data_id_name(ds, "bklog") is None
    assert find_registered_bkdata_data_id_name(ds, "bkmonitor") == "primary_metrics"

    for name, without in ((AGG, ["caller_ip"]), ("another.__default__", ["caller_ip", "target"])):
        create(name)
        modify(name, option={"metric_aggregate": {**AGGREGATE, "without": without}})
        agg = pipeline(name)
        assert agg.source_id == raw.pk and agg.output.name.startswith("bkm_mda_")
        assert not DataBusConfig.objects.filter(data_link_name=agg.data_link_id).exists()
    create("wrong.__default__", cluster=43)
    with pytest.raises(ValueError, match="同一个 Doris 集群"):
        modify("wrong.__default__", option={"metric_aggregate": AGGREGATE})
    assert models.ResultTableOption.objects.filter(table_id="wrong.__default__", name="metric_aggregate").count() == 0

    group = bus["spec"]["consumerGroup"]
    for params, stopped in (
        ({"is_enable": False}, True),
        ({"is_enable": True}, False),
        ({"option": {}}, True),
        ({"option": {"metric_ingest": INGEST}}, False),
        ({"table_name_zh": "renamed"}, False),
    ):
        modify(RAW, **params)
        reconcile_pipeline(raw.pk)
        observed = remote["bklog", "databuses", rt["metadata"]["name"]]
        assert observed["metadata"]["annotations"]["task_stopped"] == str(stopped).lower()
        assert observed["spec"]["consumerGroup"] == group
        assert (pipeline(RAW).data_link_id, pipeline(RAW).output.name) == ids
    models.ResultTable.objects.create(
        table_id="original.__default__",
        table_name_zh="VM",
        bk_tenant_id="system",
        bk_biz_id=2,
        is_custom_table=True,
        schema_type="free",
        default_storage="influxdb",
    )
    models.DataSourceResultTable.objects.create(
        table_id="original.__default__", bk_data_id=ds.pk, bk_tenant_id="system"
    )
    mocker.patch.object(models.DataSource, "get_transfer_storage_conf", return_value=[])
    transfer_tables = {row["result_table"] for row in ds.to_json(is_consul_config=True)["result_table_list"]}
    assert "original.__default__" in transfer_tables
    assert transfer_tables.isdisjoint({RAW, AGG, "another.__default__"})
    assert DataBusConfig.objects.get(name="original_shipper").consumer_group == "existing_vm_group"
    assert remote["bkmonitor", "dataids", "primary_metrics"]["spec"].get("eventType") is None


def test_retry_and_cluster_selection_keep_the_consumer(setup_links, mocker):
    ds, remote = setup_links
    create(RAW)
    modify(RAW, option={"metric_ingest": INGEST})
    p = pipeline(RAW)
    original = p.output.name
    failure = mocker.patch.object(DataLink, "apply_data_link_with_retry", side_effect=RuntimeError("BKBase offline"))
    reconcile_pipeline(p.pk)
    assert pipeline(RAW).status_reason == "BKBase offline"
    mocker.stop(failure)
    conn = mocker.patch("metadata.service.doris_job.connect_cluster")
    conn.return_value.cursor.return_value.__enter__.return_value.fetchone.return_value = {
        "Create Table": '"dynamic_partition.start" = "-7"'
    }
    reconcile_pipeline(p.pk)
    assert pipeline(RAW).output.name == original
    bus = DataBusConfig.objects.get(data_link_name=p.data_link_id)
    modify(RAW, external_storage={"doris": {"storage_cluster_id": 43}})
    assert models.DorisStorage.objects.get(table_id=RAW).storage_cluster_id == 42
    assert pipeline(RAW).output.name != original
    reconcile_pipeline(p.pk)
    assert models.DorisStorage.objects.get(table_id=RAW).storage_cluster_id == 43
    assert DataBusConfig.objects.get(data_link_name=p.data_link_id).consumer_group == bus.consumer_group
    assert remote["bklog", "databuses", bus.name]["spec"]["sinks"][0]["name"] == pipeline(RAW).output.name
    assert find_registered_bkdata_data_id_name(ds, "bkmonitor") == "primary_metrics"


def test_candidate_keeps_published_target_until_success(setup_links):
    create(RAW)
    modify(RAW, option={"metric_ingest": INGEST})
    create(AGG)
    modify(AGG, option={"metric_aggregate": AGGREGATE})
    first = pipeline(AGG)
    first_binding = first.output.name
    modify(AGG, option={"metric_aggregate": {**AGGREGATE, "lookback_minutes": 20}})
    assert pipeline(AGG).output.name == first_binding
    modify(AGG, option={"metric_aggregate": {**AGGREGATE, "without": ["target", "caller_ip"]}})
    assert pipeline(AGG).output.name != first_binding
    assert pipeline(AGG).layout["labels"] == ["dimension_11", "dimension_target", "le", "service_name"]
    assert models.DorisStorage.objects.get(table_id=AGG).bkbase_table_id is None
    assert not DorisJobConfig.objects.exists()
    assert not first.data_link._get_absent_components_to_delete([], force_delete=True)
    # 一个后台的通用 sync 不得把尚未就绪的候选发布成当前 RT。
    models.DorisStorage.objects.filter(table_id=AGG).update(bkbase_table_id=first.output.bkbase_table_id)
    first.data_link.sync_metadata(AGG, storage_cluster_id=42)
    mapping = models.BkBaseResultTable.objects.get(data_link_name=first.data_link_id)
    assert mapping.bkbase_rt_name == first_binding


def test_create_dispatches_after_commit_and_isolates_same_table_id(
    setup_links, django_capture_on_commit_callbacks, mocker
):
    ds, remote = setup_links
    from metadata.task.datalink import reconcile_metric_doris_rt

    with django_capture_on_commit_callbacks(using=DATABASE_CONNECTION_NAME, execute=True):
        CreateResultTableResource()(
            bk_tenant_id="system",
            bk_data_id=ds.pk,
            bk_biz_id=2,
            operator="tester",
            table_id=RAW,
            table_name_zh="raw",
            schema_type="free",
            is_custom_table=True,
            is_time_field_only=True,
            default_storage="doris",
            default_storage_config={"storage_cluster_id": 42},
            option={"metric_ingest": INGEST},
        )
        reconcile_metric_doris_rt.delay.assert_not_called()
        assert len(remote) == 1
    reconcile_metric_doris_rt.delay.assert_called_once_with(pipeline(RAW).pk)
    models.ResultTableOption.create_option(RAW, "foreign", "private", "tester", bk_tenant_id="another")
    response = modify(RAW, table_name_zh="new")
    assert "foreign" not in response["option"]
    assert response["option"]["metric_ingest"]["task_num"] == 4


def test_cutover_requires_successful_full_window():
    cursor = MagicMock()
    job = SimpleNamespace(remote_id=4, template_inputs={"params": {"window_minutes": 2, "lookback_minutes": 10}})
    old = SimpleNamespace(remote_id=3, template_inputs={"params": {"window_minutes": 3, "lookback_minutes": 12}})
    cursor.fetchone.return_value = None
    assert successful_cutover(cursor, job, old, 300) is None
    cursor.fetchone.return_value = {"started": 495, "finished": 496}
    # B=360 是 2/3 分钟的共同边界，最后一个旧点为 360，新窗口 (360,480]。
    assert successful_cutover(cursor, job, old, 300) == 361
    assert successful_cutover(cursor, job, old, 400) is None
    cursor.fetchone.return_value = {"started": 495, "finished": 1250}
    assert successful_cutover(cursor, job, old, 300) is None


@pytest.mark.skipif(not os.getenv("METRIC_DORIS_TEST_HOST"), reason="需要独立的 Doris 测试集群")
def test_fe_job_and_historical_minutes(setup_links, mocker):
    """真实 FE/BE，仅模拟 BKBase API；明细物理表模拟 Binding 建表后的状态。"""
    from contextlib import closing
    from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
    from metadata.service.metric_aggregate import qualified
    from metadata.service.metric_doris import binding_for, physical_ref

    host = os.environ["METRIC_DORIS_TEST_HOST"]
    models.ClusterInfo.objects.filter(pk=42).update(
        domain_name=host,
        port=int(os.getenv("METRIC_DORIS_TEST_PORT", "9030")),
        username=os.getenv("METRIC_DORIS_TEST_USER", "root"),
    )
    cluster = models.ClusterInfo.objects.get(pk=42)
    cluster.password = os.getenv("METRIC_DORIS_TEST_PASSWORD", "")
    cluster.save()
    tables = []
    with closing(doris_job.connect_cluster("system", 42)) as conn, conn.cursor() as cur:

        def mod_and_track(option, name=AGG):
            modify(name, option={"metric_aggregate": option})
            p = pipeline(name)
            table = qualified(physical_ref(binding_for(p.output)))
            if table not in tables:
                tables.append(table)
            return p

        def converge(name, timeout=210):
            until = time.monotonic() + timeout
            while time.monotonic() < until:
                p = pipeline(name)
                for job in p.data_link.doris_jobs.all():
                    doris_job.reconcile_job(job.pk)
                reconcile_pipeline(p.pk)
                p.refresh_from_db()
                assert not p.status_reason, p.status_reason
                if not p.phase:
                    return p
                time.sleep(2)
            pytest.fail(f"{name} 超时，phase={p.phase}")

        create(RAW)
        modify(RAW, option={"metric_ingest": INGEST})
        p = pipeline(RAW)
        raw_ref = physical_ref(binding_for(p.output))
        raw = qualified(raw_ref)
        tables.append(raw)
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{raw_ref['database']}`")
        conn.select_db(raw_ref["database"])
        cur.execute(f"""CREATE TABLE {raw} (thedate INT, dtEventTimeStamp BIGINT, metric_name STRING,
            metric_value DOUBLE, target STRING, le STRING, caller_ip STRING, service_name STRING,
            dimension_target STRING, dimension_11 STRING) DUPLICATE KEY(thedate,dtEventTimeStamp)
            PARTITION BY RANGE(thedate) () DISTRIBUTED BY HASH(dtEventTimeStamp) BUCKETS 1 PROPERTIES
            ("replication_num"="1","dynamic_partition.enable"="true","dynamic_partition.time_unit"="DAY",
             "dynamic_partition.time_zone"="Asia/Shanghai","dynamic_partition.start"="-7","dynamic_partition.end"="1",
             "dynamic_partition.prefix"="p","dynamic_partition.create_history_partition"="true","dynamic_partition.buckets"="1")""")
        try:
            converge(RAW)
            cur.execute("SELECT (UNIX_TIMESTAMP() DIV 60)*60000 AS t")
            end = int(cur.fetchone()["t"])

            def insert(ts, val, ip):
                day = datetime.fromtimestamp(ts / 1000, ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d")
                cur.execute(
                    f"INSERT INTO {raw} VALUES (%s,%s,'rpc_client_handled_total',%s,NULL,'+Inf',%s,'foo',NULL,'x')",
                    (day, ts, val, ip),
                )

            insert(end - 60000, 11, "ip1")
            insert(end - 59999, 3, "ip1")
            insert(end, 4, "ip2")
            create(AGG)
            first = mod_and_track(AGGREGATE)
            other = "independent_rollup.__default__"
            create(other)
            sibling = mod_and_track({**AGGREGATE, "without": ["target", "caller_ip"]}, other)
            reconcile_pipeline(sibling.pk)
            doris_job.reconcile_job(sibling.data_link.doris_jobs.get().pk)
            converge(AGG)
            converge(other)
            old_job = first.data_link.doris_jobs.get()
            old_id = old_job.remote_id
            old_table = qualified(physical_ref(binding_for(first.output)))
            cur.execute(
                f"SELECT metric_value,source_sample_count,le,target,dtEventTime FROM {old_table} WHERE dtEventTimeStamp=%s",
                (end,),
            )
            row = cur.fetchone()
            assert row == {
                "metric_value": 7.0,
                "source_sample_count": 2,
                "le": "+Inf",
                "target": "",
                "dtEventTime": datetime.fromtimestamp(end / 1000, ZoneInfo("Asia/Shanghai")).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            }
            cur.execute(f"SELECT metric_value FROM {old_table} WHERE dtEventTimeStamp=%s", (end - 60000,))
            assert cur.fetchone()["metric_value"] == 11
            insert(end - 1000, 5, "ip3")
            mod_and_track({**AGGREGATE, "lookback_minutes": 15})
            converge(AGG)
            old_job.refresh_from_db()
            assert old_id != old_job.remote_id and old_job.name == first.output.name
            # 等新同名 Job 实际重算，验证迟到样本覆盖旧分组。
            deadline = time.monotonic() + 115
            while time.monotonic() < deadline:
                cur.execute(
                    f"SELECT metric_value,source_sample_count FROM {old_table} WHERE dtEventTimeStamp=%s", (end,)
                )
                if cur.fetchone() == {"metric_value": 12.0, "source_sample_count": 3}:
                    break
                time.sleep(2)
            else:
                pytest.fail("迟到窗口未补齐")

            second = mod_and_track({**AGGREGATE, "without": []})
            assert second.output_id != first.output_id
            failed_prepare = mocker.patch(
                "metadata.service.metric_doris_reconcile.create_aggregate_table",
                side_effect=RuntimeError("candidate offline"),
            )
            reconcile_pipeline(second.pk)
            assert pipeline(AGG).status_reason == "candidate offline"
            mocker.stop(failed_prepare)
            old_mapping = models.DorisStorage.objects.get(table_id=AGG).bkbase_table_id
            assert old_mapping == first.output.bkbase_table_id
            # 在交接边界两侧都有输入；共同边界当天的分区均已创建。
            start = int(second.output.create_time.timestamp() // 60 * 60000)
            for i in range(1, 5):
                insert(start + i * 60000, 10 + i, "ip1")
                insert(start + i * 60000, 20 + i, "ip2")
            converge(AGG, timeout=250)
            cur.execute('SELECT Status FROM jobs("type"="insert") WHERE Id=%s', (old_job.remote_id,))
            assert cur.fetchone()["Status"] == "PAUSED"
            routes, _ = SpaceTableIDRedis()._compose_log_table_id_detail(bk_tenant_id="system", table_id_list=[AGG])
            history = sorted(routes[AGG]["storage_cluster_records"], key=lambda h: h["enable_time"])
            assert [h["bkbase_table_id"] for h in history] == [old_mapping, second.output.bkbase_table_id]
            boundary = history[1]["enable_time"] * 1000
            cur.execute(
                f"""SELECT dtEventTimeStamp AS t,SUM(metric_value) AS v,SUM(source_sample_count) AS n FROM
                   (SELECT * FROM (SELECT dtEventTimeStamp,metric_value,source_sample_count FROM {old_table}
                       WHERE dtEventTimeStamp < %s) a UNION ALL SELECT dtEventTimeStamp,metric_value,source_sample_count
                       FROM {tables[-1]} WHERE dtEventTimeStamp >= %s) b
                   WHERE dtEventTimeStamp BETWEEN %s AND %s GROUP BY t ORDER BY t""",
                (boundary, boundary, boundary - 1000, boundary + 59000),
            )
            assert [(r["t"], r["v"], r["n"]) for r in cur.fetchall()] == [
                (ts, 30 + 2 * ((ts - start) // 60000), 2) for ts in (boundary - 1000, boundary + 59000)
            ]
            modify(AGG, is_enable=False)
            converge(AGG)
            cur.execute(
                'SELECT Status FROM jobs("type"="insert") WHERE Id=%s', (sibling.data_link.doris_jobs.get().remote_id,)
            )
            assert cur.fetchone()["Status"] == "RUNNING"
            modify(AGG, is_enable=True)
            converge(AGG)
            assert pipeline(AGG).output_id == second.output_id
        finally:
            for job in DorisJobConfig.objects.filter(
                data_link__metricdorispipeline__result_table__table_id__in=[AGG, "independent_rollup.__default__"]
            ):
                cur.execute('SELECT Id FROM jobs("type"="insert") WHERE Name=%s', (job.name,))
                row = cur.fetchone()
                if row and int(row["Id"]) == job.remote_id:
                    cur.execute("DROP JOB WHERE jobName=%s", (job.name,))
            for table in tables:
                cur.execute(f"DROP TABLE IF EXISTS {table} FORCE")


@pytest.mark.skipif(not os.getenv("METRIC_KAFKA_TEST_BROKERS"), reason="需要独立的 Kafka 测试集群")
def test_real_offsets_across_stop_and_resume(setup_links, mocker):
    from confluent_kafka import Consumer, Producer, TopicPartition
    from confluent_kafka.admin import AdminClient, NewTopic

    _, remote = setup_links
    brokers = os.environ["METRIC_KAFKA_TEST_BROKERS"]
    conn = mocker.patch("metadata.service.doris_job.connect_cluster")
    conn.return_value.cursor.return_value.__enter__.return_value.fetchone.return_value = {
        "Create Table": '"dynamic_partition.start" = "-7"'
    }
    create(RAW)
    modify(RAW, option={"metric_ingest": INGEST})
    raw = pipeline(RAW)
    topic = f"test-{raw.output.name}"
    remote["bkmonitor", "dataids", "primary_metrics"]["spec"]["predefined"]["topic"] = topic
    admin = AdminClient({"bootstrap.servers": brokers})
    admin.create_topics([NewTopic(topic, 1, 1)])[topic].result(timeout=20)
    producer = Producer({"bootstrap.servers": brokers})

    def consumer(spec):
        return Consumer(
            {
                "bootstrap.servers": brokers,
                "group.id": spec["consumerGroup"],
                "auto.offset.reset": spec["autoOffsetReset"],
                "enable.auto.commit": False,
            }
        )

    def publish(value):
        producer.produce(topic, value, partition=0)
        assert producer.flush(10) == 0

    try:
        reconcile_pipeline(raw.pk)
        key = ("bklog", "databuses", raw.output.name)
        before = remote[key]["spec"]
        alias = before["sources"][0]["name"]
        assert remote["bklog", "dataids", alias]["spec"]["predefined"]["topic"] == topic
        reader = consumer(before)
        try:
            reader.subscribe([topic])
            deadline = time.monotonic() + 15
            while not reader.assignment() and time.monotonic() < deadline:
                reader.poll(0.2)
            assert reader.assignment()
            reader.poll(0.5)
            publish(b"processed")
            msg = reader.poll(10)
            assert msg is not None and not msg.error() and msg.offset() == 0
            reader.commit(message=msg, asynchronous=False)
        finally:
            reader.close()
        modify(RAW, is_enable=False)
        reconcile_pipeline(raw.pk)
        publish(b"queued while stopped")
        modify(RAW, is_enable=True)
        reconcile_pipeline(raw.pk)
        reader = consumer(remote[key]["spec"])
        try:
            assert reader.committed([TopicPartition(topic, 0)], timeout=10)[0].offset == 1
            reader.subscribe([topic])
            msg = reader.poll(10)
            assert msg is not None and not msg.error()
            assert (msg.offset(), msg.value()) == (1, b"queued while stopped")
        finally:
            reader.close()
    finally:
        admin.delete_topics([topic])[topic].result(timeout=20)
