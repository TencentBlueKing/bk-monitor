"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

"""
``QueryDataLinkMetadataResource`` v2 改造单元测试

覆盖范围:
    - 入参校验 (RequestSerializer)
    - 纯函数 helpers (无 DB 依赖): _parse_index_shard_num / _format_dt / _safe_json_loads
    - _resolve_bcs_cluster_id 三路兜底 (基于 mock context)
    - _derive_effective_storage 派生 (InfluxDB → VM 自动判定)
    - _resolve_targets 入参分支 (优先级)

集成测试 (perform_request 端到端) 详见 test_query_datalink_metadata_v2_integration.py.
"""
import datetime
import json
from unittest import mock


from metadata.resources.bkdata_link import QueryDataLinkMetadataResource


# ============================================================
# RequestSerializer
# ============================================================


class TestRequestSerializer:
    def _make_serializer(self, data):
        return QueryDataLinkMetadataResource.RequestSerializer(data=data)

    def test_empty_input_fails_validation(self):
        ser = self._make_serializer({"bk_tenant_id": "system"})
        assert not ser.is_valid()
        # 至少一个查询参数
        assert "non_field_errors" in ser.errors or any("At least one" in str(v) for v in ser.errors.values())

    def test_with_bk_data_id_passes(self):
        ser = self._make_serializer({"bk_tenant_id": "system", "bk_data_id": "123"})
        assert ser.is_valid(), ser.errors

    def test_with_result_table_id_passes(self):
        ser = self._make_serializer({"bk_tenant_id": "system", "result_table_id": "2_bklog.foo"})
        assert ser.is_valid(), ser.errors

    def test_with_vm_result_table_id_passes(self):
        ser = self._make_serializer({"bk_tenant_id": "system", "vm_result_table_id": "2_bkm_xxx"})
        assert ser.is_valid(), ser.errors

    def test_with_component_name_passes(self):
        # P3 reserved
        ser = self._make_serializer({"bk_tenant_id": "system", "component_name": "bklog-bklog_301_xxx"})
        assert ser.is_valid(), ser.errors

    def test_missing_tenant_fails(self):
        ser = self._make_serializer({"bk_data_id": "123"})
        assert not ser.is_valid()
        assert "bk_tenant_id" in ser.errors


# ============================================================
# Pure helpers (无 DB 依赖)
# ============================================================


class TestSafeJsonLoads:
    def test_none(self):
        assert QueryDataLinkMetadataResource._safe_json_loads(None) is None

    def test_empty_string(self):
        assert QueryDataLinkMetadataResource._safe_json_loads("") is None

    def test_valid_json_string(self):
        assert QueryDataLinkMetadataResource._safe_json_loads('{"a": 1}') == {"a": 1}

    def test_invalid_json(self):
        assert QueryDataLinkMetadataResource._safe_json_loads("not-json") is None

    def test_already_dict(self):
        # 已经是 dict 直接返回
        d = {"a": 1}
        assert QueryDataLinkMetadataResource._safe_json_loads(d) is d


class TestParseIndexShardNum:
    def test_valid_settings(self):
        s = json.dumps({"number_of_shards": 3, "number_of_replicas": 1})
        assert QueryDataLinkMetadataResource._parse_index_shard_num(s) == 3

    def test_string_number(self):
        s = json.dumps({"number_of_shards": "5"})
        assert QueryDataLinkMetadataResource._parse_index_shard_num(s) == 5

    def test_missing_field(self):
        s = json.dumps({"number_of_replicas": 1})
        assert QueryDataLinkMetadataResource._parse_index_shard_num(s) is None

    def test_invalid_json(self):
        assert QueryDataLinkMetadataResource._parse_index_shard_num("not-json") is None

    def test_none(self):
        assert QueryDataLinkMetadataResource._parse_index_shard_num(None) is None

    def test_non_int_value(self):
        s = json.dumps({"number_of_shards": "abc"})
        assert QueryDataLinkMetadataResource._parse_index_shard_num(s) is None


class TestFormatDt:
    def test_none(self):
        assert QueryDataLinkMetadataResource._format_dt(None) is None

    def test_naive_datetime(self):
        dt = datetime.datetime(2026, 5, 13, 10, 0, 0)
        out = QueryDataLinkMetadataResource._format_dt(dt)
        assert out.startswith("2026-05-13")

    def test_aware_datetime(self):
        dt = datetime.datetime(2026, 5, 13, 10, 0, 0, tzinfo=datetime.timezone.utc)
        out = QueryDataLinkMetadataResource._format_dt(dt)
        assert "2026-05-13" in out


class TestBcsClusterPattern:
    """正则 ``bcs[_-]k8s[_-](\\d+)`` 匹配 V3/V4 两种命名."""

    def test_lowercase_underscore(self):
        m = QueryDataLinkMetadataResource.BCS_CLUSTER_PATTERN.search("space_99001_bklog_bcs_k8s_99001_std")
        assert m and m.group(1) == "99001"

    def test_uppercase_hyphen(self):
        m = QueryDataLinkMetadataResource.BCS_CLUSTER_PATTERN.search("2_bklog_BCS-K8S-99002_stdout_all")
        assert m and m.group(1) == "99002"

    def test_no_match(self):
        m = QueryDataLinkMetadataResource.BCS_CLUSTER_PATTERN.search("regular_data_name_no_bcs")
        assert m is None


# ============================================================
# _resolve_bcs_cluster_id 三路兜底 (基于 mock context)
# ============================================================


class TestResolveBcsClusterId:
    def _make_resource(self):
        return QueryDataLinkMetadataResource()

    def _make_ds(self, data_name):
        ds = mock.MagicMock()
        ds.data_name = data_name
        return ds

    def _make_rt(self, table_id):
        rt = mock.MagicMock()
        rt.table_id = table_id
        return rt

    def test_path_1_name_parse(self):
        """data_name 含 bcs_k8s_xxx → name_parse 命中."""
        r = self._make_resource()
        ds = self._make_ds("space_99001_bklog_bcs_k8s_99001_std_json")
        rt = self._make_rt("space_99001_bklog.bcs_k8s_99001_std")
        ctx = {"vm_records": {}, "bcs_cluster_by_data_id": {}}
        cid, source = r._resolve_bcs_cluster_id(100001, ds, rt, ctx)
        assert cid == "BCS-K8S-99001"
        assert source == "name_parse"

    def test_path_2_access_vm_record(self):
        """data_name 无 bcs 关键字, 但 AccessVMRecord.bcs_cluster_id 有值."""
        r = self._make_resource()
        ds = self._make_ds("regular_data")
        rt = self._make_rt("foo.bar")
        vm = mock.MagicMock()
        vm.bcs_cluster_id = "BCS-K8S-99006"
        ctx = {"vm_records": {"foo.bar": [vm]}, "bcs_cluster_by_data_id": {}}
        cid, source = r._resolve_bcs_cluster_id(100, ds, rt, ctx)
        assert cid == "BCS-K8S-99006"
        assert source == "access_vm_record"

    def test_path_3_bcs_cluster_info(self):
        """前两路都无, BCSClusterInfo 反查命中."""
        r = self._make_resource()
        ds = self._make_ds("regular_data")
        rt = self._make_rt("foo.bar")
        ctx = {"vm_records": {}, "bcs_cluster_by_data_id": {200: "BCS-K8S-99999"}}
        cid, source = r._resolve_bcs_cluster_id(200, ds, rt, ctx)
        assert cid == "BCS-K8S-99999"
        assert source == "bcs_cluster_info"

    def test_all_paths_miss(self):
        r = self._make_resource()
        ds = self._make_ds("regular_data")
        rt = self._make_rt("foo.bar")
        ctx = {"vm_records": {}, "bcs_cluster_by_data_id": {}}
        cid, source = r._resolve_bcs_cluster_id(300, ds, rt, ctx)
        assert cid is None
        assert source is None

    def test_name_parse_priority_over_other_paths(self):
        """name_parse 命中时不会尝试 path 2/3."""
        r = self._make_resource()
        ds = self._make_ds("bcs-k8s-99999")
        rt = self._make_rt("foo.bar")
        # 即使 vm_records 也有, 仍然优先 name_parse
        vm = mock.MagicMock()
        vm.bcs_cluster_id = "BCS-K8S-99097"
        ctx = {"vm_records": {"foo.bar": [vm]}, "bcs_cluster_by_data_id": {1: "BCS-K8S-99098"}}
        cid, source = r._resolve_bcs_cluster_id(1, ds, rt, ctx)
        assert cid == "BCS-K8S-99999"
        assert source == "name_parse"


# ============================================================
# _derive_effective_storage (InfluxDB → VM 自动判定)
# ============================================================


class TestDeriveEffectiveStorage:
    def _make_resource(self):
        return QueryDataLinkMetadataResource()

    def test_influxdb_with_vm_record_becomes_vm(self):
        r = self._make_resource()
        ctx = {"vm_records": {"foo.bar": [mock.MagicMock()]}}
        result = r._derive_effective_storage("influxdb", "foo.bar", ctx)
        assert result == "victoria_metrics"

    def test_influxdb_without_vm_record_stays(self):
        r = self._make_resource()
        ctx = {"vm_records": {}}
        result = r._derive_effective_storage("influxdb", "foo.bar", ctx)
        assert result == "influxdb"

    def test_es_unchanged(self):
        r = self._make_resource()
        ctx = {"vm_records": {}}
        result = r._derive_effective_storage("elasticsearch", "foo.bar", ctx)
        assert result == "elasticsearch"

    def test_vm_unchanged(self):
        r = self._make_resource()
        ctx = {"vm_records": {"foo.bar": [mock.MagicMock()]}}
        result = r._derive_effective_storage("victoria_metrics", "foo.bar", ctx)
        assert result == "victoria_metrics"


# ============================================================
# _resolve_bk_base_data_id 派生
# ============================================================


class TestResolveBkBaseDataId:
    def _make_resource(self):
        return QueryDataLinkMetadataResource()

    def test_v3_with_vm_record(self):
        r = self._make_resource()
        ds = mock.MagicMock()
        ds.created_from = "bkgse"
        vm = mock.MagicMock()
        vm.bk_base_data_id = 100012
        ctx = {"vm_records": {"foo.bar": [vm]}}
        result = r._resolve_bk_base_data_id("foo.bar", 100002, ds, ctx)
        assert result == 100012

    def test_v4_native_fallback_to_data_id(self):
        r = self._make_resource()
        ds = mock.MagicMock()
        ds.created_from = "bkdata"
        ctx = {"vm_records": {}}
        result = r._resolve_bk_base_data_id("foo.bar", 100003, ds, ctx)
        assert result == 100003

    def test_v3_no_vm_record(self):
        r = self._make_resource()
        ds = mock.MagicMock()
        ds.created_from = "bkgse"
        ctx = {"vm_records": {}}
        result = r._resolve_bk_base_data_id("foo.bar", 100, ds, ctx)
        assert result is None


# ============================================================
# _build_kafka_frontend_block
# ============================================================


class TestBuildKafkaFrontendBlock:
    def _make_resource(self):
        return QueryDataLinkMetadataResource()

    def test_full_kafka_info(self):
        r = self._make_resource()
        ds = mock.MagicMock()
        ds.mq_cluster_id = 12
        ds.mq_config_id = 100

        cluster = mock.MagicMock()
        cluster.cluster_id = 12
        cluster.cluster_name = "kafka-test"
        cluster.domain_name = "kafka.example.com"

        kt = mock.MagicMock()
        kt.topic = "0bkmonitor_test"
        kt.partition = 4

        ctx = {"clusters": {12: cluster}, "kafka_topics": {100: kt}}
        out = r._build_kafka_frontend_block(ds, ctx)
        assert out["kafka_instance_id"] == 12
        assert out["kafka_inner_cluster_name"] == "kafka-test"
        assert out["kafka_host"] == "kafka.example.com"
        assert out["topic_name"] == "0bkmonitor_test"
        assert out["current_partition_num"] == 4
        assert out["kafka_app"] is None  # placeholder

    def test_missing_cluster_returns_nones(self):
        r = self._make_resource()
        ds = mock.MagicMock()
        ds.mq_cluster_id = None
        ds.mq_config_id = None
        ctx = {"clusters": {}, "kafka_topics": {}}
        out = r._build_kafka_frontend_block(ds, ctx)
        assert out["kafka_host"] is None
        assert out["topic_name"] is None


# ============================================================
# _build_transfer_block
# ============================================================


class TestBuildTransferBlock:
    def _make_resource(self):
        return QueryDataLinkMetadataResource()

    def test_with_transfer_cluster(self):
        r = self._make_resource()
        ds = mock.MagicMock()
        ds.transfer_cluster_id = "default"
        out = r._build_transfer_block(ds)
        assert out["transfer_cluster"] == "default"
        assert out["transfer_cluster_pod_num"] is None

    def test_no_transfer_cluster(self):
        r = self._make_resource()
        ds = mock.MagicMock()
        ds.transfer_cluster_id = ""
        out = r._build_transfer_block(ds)
        assert out["transfer_cluster"] is None


# ============================================================
# _build_es_block
# ============================================================


class TestBuildEsBlock:
    def _make_resource(self):
        return QueryDataLinkMetadataResource()

    def test_full_es_storage(self):
        r = self._make_resource()
        es = mock.MagicMock()
        es.storage_cluster_id = 27
        es.index_set = "test_index"
        es.retention = 7
        es.slice_size = 50
        es.slice_gap = 1440
        es.time_zone = 8
        es.index_settings = json.dumps({"number_of_shards": 3, "number_of_replicas": 1})
        es.mapping_settings = json.dumps({"properties": {"foo": {"type": "keyword"}}})

        cluster = mock.MagicMock()
        cluster.domain_name = "es.example.com"
        cluster.cluster_name = "es-cluster"

        ctx = {"es_storages": {"foo.bar": es}, "clusters": {27: cluster}}
        out = r._build_es_block("foo.bar", ctx)
        assert out["es_cluster_id"] == 27
        assert out["es_cluster_domain"] == "es.example.com"
        assert out["es_index_name"] == "test_index"
        assert out["es_retention_days"] == 7
        assert out["es_slice_size_gb"] == 50
        assert out["es_slice_gap_minutes"] == 1440
        assert out["es_time_zone"] == 8
        assert out["es_index_shard_num"] == 3
        assert out["es_index_settings"] == {"number_of_shards": 3, "number_of_replicas": 1}
        # Runtime fields are null in P1
        assert out["es_current_index_name"] is None
        assert out["es_should_rotate_index"] is None
        assert out["es_app"] is None

    def test_no_es_storage(self):
        r = self._make_resource()
        ctx = {"es_storages": {}, "clusters": {}}
        out = r._build_es_block("foo.bar", ctx)
        assert all(v is None or v == 0 for v in out.values())


# ============================================================
# _build_doris_block
# ============================================================


class TestBuildDorisBlock:
    def _make_resource(self):
        return QueryDataLinkMetadataResource()

    def test_full_doris_storage(self):
        r = self._make_resource()
        doris = mock.MagicMock()
        doris.storage_cluster_id = 102
        doris.bkbase_table_id = "fake_db.fake_doris_table"
        doris.table_type = "duplicate"
        doris.expire_days = 30

        cluster = mock.MagicMock()
        cluster.domain_name = "doris.example.com"
        cluster.cluster_name = "doris-cluster"

        ctx = {"doris_storages": {"foo.bar": doris}, "clusters": {102: cluster}}
        out = r._build_doris_block("foo.bar", ctx)
        assert out["doris_cluster_id"] == 102
        assert out["doris_cluster_domain"] == "doris.example.com"
        assert out["doris_table_name"] == "fake_db.fake_doris_table"
        assert out["doris_table_type"] == "duplicate"
        assert out["doris_expire_days"] == 30
        assert out["doris_bucket_size"] is None  # P2
        assert out["doris_app"] is None  # placeholder

    def test_no_doris(self):
        r = self._make_resource()
        ctx = {"doris_storages": {}, "clusters": {}}
        out = r._build_doris_block("foo.bar", ctx)
        assert all(v is None for v in out.values())


# ============================================================
# _build_vm_block
# ============================================================


class TestBuildVmBlock:
    def _make_resource(self):
        return QueryDataLinkMetadataResource()

    def test_single_vm_record(self):
        r = self._make_resource()
        vm = mock.MagicMock()
        vm.vm_cluster_id = 36
        vm.vm_result_table_id = "2_bkm_test"
        vm.storage_cluster_id = 50
        vm.create_time = datetime.datetime(2026, 5, 13, tzinfo=datetime.timezone.utc)

        cluster = mock.MagicMock()
        cluster.domain_name = "vm.example.com"
        cluster.cluster_name = "vm-cluster"

        ctx = {"vm_records": {"foo.bar": [vm]}, "clusters": {36: cluster}}
        out = r._build_vm_block("foo.bar", ctx)
        assert out["vm_rt_name"] == "2_bkm_test"
        assert out["vm_cluster_id"] == 36
        assert out["vm_cluster_domain"] == "vm.example.com"
        assert out["vm_cluster_name"] == "vm-cluster"
        assert out["vm_records_count"] == 1

    def test_multi_vm_record_picks_latest(self):
        r = self._make_resource()
        vm1 = mock.MagicMock(create_time=datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc))
        vm1.vm_cluster_id = 1
        vm1.vm_result_table_id = "old_vm"
        vm1.storage_cluster_id = 10

        vm2 = mock.MagicMock(create_time=datetime.datetime(2026, 5, 1, tzinfo=datetime.timezone.utc))
        vm2.vm_cluster_id = 2
        vm2.vm_result_table_id = "new_vm"
        vm2.storage_cluster_id = 20

        cluster_new = mock.MagicMock(domain_name="vm-new.example.com", cluster_name="vm-new")
        ctx = {"vm_records": {"foo.bar": [vm1, vm2]}, "clusters": {2: cluster_new}}
        out = r._build_vm_block("foo.bar", ctx)
        # Should pick vm2 (latest)
        assert out["vm_rt_name"] == "new_vm"
        assert out["vm_cluster_id"] == 2
        assert out["vm_records_count"] == 2

    def test_no_vm_record(self):
        r = self._make_resource()
        ctx = {"vm_records": {}, "clusters": {}}
        out = r._build_vm_block("foo.bar", ctx)
        assert out["vm_rt_name"] is None
        assert out["vm_records_count"] == 0


# ============================================================
# _build_kafka_backend_block
# ============================================================


class TestBuildKafkaBackendBlock:
    def _make_resource(self):
        return QueryDataLinkMetadataResource()

    def test_with_kafka_storage(self):
        r = self._make_resource()
        ks = mock.MagicMock()
        ks.storage_cluster_id = 5
        ks.topic = "backend_topic"
        ks.partition = 8

        cluster = mock.MagicMock()
        cluster.domain_name = "backend-kafka.example.com"

        ctx = {"kafka_storages": {"foo.bar": ks}, "clusters": {5: cluster}}
        out = r._build_kafka_backend_block("foo.bar", ctx)
        assert out["backend_kafka_cluster_id"] == 5
        assert out["backend_kafka_host"] == "backend-kafka.example.com"
        assert out["backend_kafka_topic"] == "backend_topic"
        assert out["backend_kafka_partition"] == 8

    def test_no_kafka_storage(self):
        r = self._make_resource()
        ctx = {"kafka_storages": {}, "clusters": {}}
        out = r._build_kafka_backend_block("foo.bar", ctx)
        assert all(v is None for v in out.values())


# ============================================================
# _build_v4_databus_block (P1 本地字段)
# ============================================================


class TestBuildV4DatabusBlock:
    def _make_resource(self):
        return QueryDataLinkMetadataResource()

    def test_v3_returns_all_null(self):
        r = self._make_resource()
        ds = mock.MagicMock(created_from="bkgse")
        ctx = {"bkbase_rts": {}, "databus_configs": {}, "components_by_link": {}}
        out = r._build_v4_databus_block("foo.bar", ds, ctx)
        assert out["bkbase_status"] is None
        assert out["bkbase_table_id"] is None
        assert out["bkbase_components"] is None

    def test_v4_with_bkbase_rt(self):
        r = self._make_resource()
        ds = mock.MagicMock(created_from="bkdata")
        br = mock.MagicMock()
        br.status = "Ok"
        br.bkbase_table_id = "2_bkm_foo"
        br.bkbase_rt_name = "bkm_foo"
        br.data_link_name = "bkm_foo_link"

        dc = mock.MagicMock()
        dc.name = "bkm_foo_databus"

        comps = [
            {
                "kind": "DataId",
                "name": "bkm_foo",
                "namespace": "bkmonitor",
                "data_link_name": "bkm_foo_link",
                "status": None,
                "message": None,
                "status_error": None,
            },
            {
                "kind": "VmStorageBinding",
                "name": "bkm_foo",
                "namespace": "bkmonitor",
                "data_link_name": "bkm_foo_link",
                "status": None,
                "message": None,
                "status_error": None,
            },
        ]
        ctx = {
            "bkbase_rts": {"foo.bar": br},
            "databus_configs": {"bkm_foo_link": dc},
            "components_by_link": {"bkm_foo_link": comps},
        }
        out = r._build_v4_databus_block("foo.bar", ds, ctx)
        assert out["bkbase_status"] == "Ok"
        assert out["bkbase_table_id"] == "2_bkm_foo"
        assert out["bkbase_rt_name"] == "bkm_foo"
        assert out["databus_name"] == "bkm_foo_databus"
        assert out["bkbase_components"] == comps
        # Runtime fields are null in P1
        assert out["dispatch_cluster"] is None
        assert out["databus_kafka_host"] is None

    def test_v4_migration_no_bkbase_rt(self):
        """V3 → V4 迁移: created_from=bkdata 但本地无 BkBaseResultTable."""
        r = self._make_resource()
        ds = mock.MagicMock(created_from="bkdata")
        ctx = {"bkbase_rts": {}, "databus_configs": {}, "components_by_link": {}}
        out = r._build_v4_databus_block("foo.bar", ds, ctx)
        assert all(out[k] is None for k in ("bkbase_status", "bkbase_table_id", "databus_name", "bkbase_components"))


# ============================================================
# _build_placeholder_block + _build_runtime_error_fields
# ============================================================


def test_placeholder_block_all_null():
    out = QueryDataLinkMetadataResource()._build_placeholder_block()
    assert out == {
        "kafka_broker_num": None,
        "es_node_num": None,
        "doris_node_num": None,
        "collect_config_id": None,
    }


def test_runtime_error_fields_all_null():
    out = QueryDataLinkMetadataResource()._build_runtime_error_fields()
    assert out == {"bkbase_remote_error": None, "es_runtime_error": None}


# ============================================================
# component_name (P3 stub)
# ============================================================


class TestResolveByComponentName:
    """P3: component_name 反查."""

    def test_empty_name_returns_empty(self):
        r = QueryDataLinkMetadataResource()
        # 无 namespace 前缀, name 部分为空
        assert r._resolve_by_component_name("system", "") == []

    @mock.patch("metadata.resources.bkdata_link.models")
    def test_parse_namespace_prefix(self, m_models):
        """``bklog-xxx`` → ns=bklog, name=xxx."""
        m_models.DataLink.objects.filter.return_value.first.return_value = None
        # 让 *Config 全部未命中
        for cfg_cls_name in (
            "DataIdConfig",
            "ResultTableConfig",
            "VMStorageBindingConfig",
            "ESStorageBindingConfig",
            "DorisStorageBindingConfig",
            "DataBusConfig",
            "ConditionalSinkConfig",
        ):
            getattr(m_models, cfg_cls_name).objects.filter.return_value.first.return_value = None
        r = QueryDataLinkMetadataResource()
        out = r._resolve_by_component_name("system", "bklog-bklog_301_xxx")
        assert out == []
        # 验证至少调了 bklog namespace 的 DataLink 查询
        called = False
        for call in m_models.DataLink.objects.filter.call_args_list:
            kwargs = call.kwargs
            if kwargs.get("namespace") == "bklog" and kwargs.get("data_link_name") == "bklog_301_xxx":
                called = True
                break
        assert called, "DataLink query for bklog namespace not invoked"

    @mock.patch("metadata.resources.bkdata_link.models")
    def test_datalink_first_hit(self, m_models):
        """Step 1 直查 DataLink 命中, 不扫 *Config."""
        link = mock.MagicMock()
        link.bk_data_id = 100004
        link.table_ids = ["100_bklog.fake_table"]
        m_models.DataLink.objects.filter.return_value.first.return_value = link
        r = QueryDataLinkMetadataResource()
        out = r._resolve_by_component_name("system", "bklog-fake_bklog_link_1")
        assert out == [(100004, "100_bklog.fake_table")]

    @mock.patch("metadata.resources.bkdata_link.models")
    def test_fallback_to_config(self, m_models):
        """Step 1 未命中 → fallback 扫 *Config; 再回 DataLink 查."""
        # 先返回 None (DataLink 未命中第一轮); 然后 ConditionalSinkConfig 命中 → 拿到 data_link_name → 再查 DataLink 命中
        m_models.DataLink.objects.filter.return_value.first.side_effect = [
            None,
            mock.MagicMock(bk_data_id=200, table_ids=["foo.bar"]),
        ]
        # 让前几个 *Config 都返回 None, ConditionalSinkConfig 命中
        for cfg_cls_name in (
            "DataIdConfig",
            "ResultTableConfig",
            "VMStorageBindingConfig",
            "ESStorageBindingConfig",
            "DorisStorageBindingConfig",
            "DataBusConfig",
        ):
            getattr(m_models, cfg_cls_name).objects.filter.return_value.first.return_value = None
        cfg = mock.MagicMock()
        cfg.data_link_name = "fed_router_xxx"
        m_models.ConditionalSinkConfig.objects.filter.return_value.first.return_value = cfg

        r = QueryDataLinkMetadataResource()
        out = r._resolve_by_component_name("system", "bkmonitor-fed_router_xxx_router")
        # 命中后返回展开的 (data_id, table_id) 列表
        assert out == [(200, "foo.bar")]

    @mock.patch("metadata.resources.bkdata_link.models")
    def test_no_namespace_prefix_tries_both(self, m_models):
        """``foo`` (无 ns 前缀) → 跨 bkmonitor / bklog 都试."""
        m_models.DataLink.objects.filter.return_value.first.return_value = None
        for cfg_cls_name in (
            "DataIdConfig",
            "ResultTableConfig",
            "VMStorageBindingConfig",
            "ESStorageBindingConfig",
            "DorisStorageBindingConfig",
            "DataBusConfig",
            "ConditionalSinkConfig",
        ):
            getattr(m_models, cfg_cls_name).objects.filter.return_value.first.return_value = None
        r = QueryDataLinkMetadataResource()
        r._resolve_by_component_name("system", "no_prefix_name")
        # 应该至少调用 DataLink 2 次 (bkmonitor + bklog)
        ns_called = set()
        for call in m_models.DataLink.objects.filter.call_args_list:
            ns = call.kwargs.get("namespace")
            if ns:
                ns_called.add(ns)
        assert {"bkmonitor", "bklog"}.issubset(ns_called)


# ============================================================
# P3: bcs_federal_info 填充判定
# ============================================================


class TestBuildBcsFederalInfo:
    def _make_resource(self):
        return QueryDataLinkMetadataResource()

    def test_no_match(self):
        r = self._make_resource()
        rt = mock.MagicMock()
        rt.table_id = "regular.foo"
        ctx = {"fed_by_table_id": {}, "fed_by_sub_cluster_id": {}}
        out = r._build_bcs_federal_info(rt, "bk_standard_v2_time_series", "BCS-K8S-99", ctx)
        assert out is None

    def test_table_id_hit_fed_builtin(self):
        r = self._make_resource()
        rt = mock.MagicMock()
        rt.table_id = "1068_bkmonitor_time_series_557787.__default__"
        fed = mock.MagicMock(
            fed_cluster_id="BCS-K8S-99003",
            host_cluster_id="BCS-K8S-99004",
            sub_cluster_id="BCS-K8S-99005",
            fed_namespaces=["ns1", "ns2"],
            fed_builtin_metric_table_id="1068_bkmonitor_time_series_557787.__default__",
            fed_builtin_event_table_id="1068_bkmonitor_event_557789",
        )
        ctx = {
            "fed_by_table_id": {rt.table_id: fed},
            "fed_by_sub_cluster_id": {},
        }
        # 即使 strategy 不是联邦, 命中 fed_builtin 也填充
        out = r._build_bcs_federal_info(rt, "bk_standard_v2_time_series", None, ctx)
        assert out is not None
        assert out["fed_cluster_id"] == "BCS-K8S-99003"
        assert out["host_cluster_id"] == "BCS-K8S-99004"
        assert out["sub_cluster_id"] == "BCS-K8S-99005"
        assert out["fed_namespaces"] == ["ns1", "ns2"]

    def test_strategy_match_with_sub_cluster_hit(self):
        r = self._make_resource()
        rt = mock.MagicMock()
        rt.table_id = "subset.cpu_fed"
        fed = mock.MagicMock(
            fed_cluster_id="BCS-K8S-99003",
            host_cluster_id="BCS-K8S-99004",
            sub_cluster_id="BCS-K8S-99005",
            fed_namespaces=[],
            fed_builtin_metric_table_id=None,
            fed_builtin_event_table_id=None,
        )
        ctx = {
            "fed_by_table_id": {},
            "fed_by_sub_cluster_id": {"BCS-K8S-99005": fed},
        }
        out = r._build_bcs_federal_info(rt, "bcs_federal_subset_time_series", "BCS-K8S-99005", ctx)
        assert out is not None
        assert out["sub_cluster_id"] == "BCS-K8S-99005"

    def test_strategy_match_no_sub_cluster(self):
        """策略匹配但 bcs_cluster_id 未提供 → 不填充."""
        r = self._make_resource()
        rt = mock.MagicMock()
        rt.table_id = "subset.cpu_fed"
        ctx = {"fed_by_table_id": {}, "fed_by_sub_cluster_id": {"X": mock.MagicMock()}}
        out = r._build_bcs_federal_info(rt, "bcs_federal_subset_time_series", None, ctx)
        assert out is None

    def test_non_federal_strategy_no_sub_cluster_match(self):
        """非联邦策略, 即使 sub_cluster_id 数值相同也不填 (避免误命中)."""
        r = self._make_resource()
        rt = mock.MagicMock()
        rt.table_id = "regular.bar"
        fed = mock.MagicMock(sub_cluster_id="BCS-K8S-99005")
        ctx = {
            "fed_by_table_id": {},
            "fed_by_sub_cluster_id": {"BCS-K8S-99005": fed},
        }
        out = r._build_bcs_federal_info(rt, "bk_standard_v2_time_series", "BCS-K8S-99005", ctx)
        assert out is None


# ============================================================
# P2 Runtime: _fetch_bkbase_metadata
# ============================================================


class TestFetchBkbaseMetadata:
    def _make_resource(self):
        return QueryDataLinkMetadataResource()

    def test_no_params_returns_none(self):
        r = self._make_resource()
        assert r._fetch_bkbase_metadata(None, None) is None

    @mock.patch("metadata.resources.bkdata_link.api")
    def test_with_bk_base_data_id(self, m_api):
        m_api.bkdata.get_data_link_metadata.return_value = {"branches": [{"kafka_host": "h"}]}
        r = self._make_resource()
        result = r._fetch_bkbase_metadata(100003, None)
        assert result == {"branches": [{"kafka_host": "h"}]}
        m_api.bkdata.get_data_link_metadata.assert_called_with(bk_data_id=100003)

    @mock.patch("metadata.resources.bkdata_link.api")
    def test_with_vm_rt_name_when_no_data_id(self, m_api):
        m_api.bkdata.get_data_link_metadata.return_value = {"branches": []}
        r = self._make_resource()
        r._fetch_bkbase_metadata(None, "2_bkm_xxx")
        m_api.bkdata.get_data_link_metadata.assert_called_with(vm_result_table_id="2_bkm_xxx")

    @mock.patch("metadata.resources.bkdata_link.api")
    def test_api_failure_returns_error(self, m_api):
        m_api.bkdata.get_data_link_metadata.side_effect = RuntimeError("502 Bad Gateway")
        r = self._make_resource()
        result = r._fetch_bkbase_metadata(100, None)
        assert isinstance(result, dict)
        assert "_error" in result
        assert "502" in result["_error"]


# ============================================================
# P2 Runtime: _apply_bkbase_metadata 应用 branches[]
# ============================================================


class TestApplyBkbaseMetadata:
    def _make_resource(self):
        return QueryDataLinkMetadataResource()

    def test_empty_branches_no_op(self):
        r = self._make_resource()
        row = {"dispatch_cluster": None}
        r._apply_bkbase_metadata(row, {"branches": []})
        assert row["dispatch_cluster"] is None

    def test_full_branch_data(self):
        r = self._make_resource()
        row = {}
        result = {
            "branches": [
                {
                    "dispatch_cluster": "vmraw-10b",
                    "dispatch_cluster_count": 1,
                    "dispatch_cluster_task_name": "task_xxx",
                    "dispatch_task_count": 1,
                    "kafka_host": "127.0.1.10",
                    "kafka_topic_name": "topic_xxx",
                    "kafka_topic_partition_num": 4,
                    "vm_cluster_domain": "vm.example.com",
                    "kafka_shipper_host": "shipper.example.com",
                    "kafka_shipper_topic_name": "shipper_topic",
                    "kafka_shipper_topic_partition_num": 8,
                }
            ]
        }
        r._apply_bkbase_metadata(row, result)
        assert row["dispatch_cluster"] == "vmraw-10b"
        assert row["dispatch_cluster_count"] == 1
        assert row["dispatch_cluster_task_name"] == "task_xxx"
        assert row["databus_v4_subtask_name"] == "task_xxx"  # 双写
        assert row["databus_kafka_host"] == "127.0.1.10"
        assert row["databus_topic_name"] == "topic_xxx"
        assert row["databus_topic_partition_num"] == 4
        assert row["databus_vm_cluster_domain"] == "vm.example.com"
        assert row["kafka_shipper_host"] == "shipper.example.com"
        assert row["kafka_shipper_topic_name"] == "shipper_topic"
        assert row["kafka_shipper_topic_partition_num"] == 8

    def test_non_dict_result_no_op(self):
        r = self._make_resource()
        row = {"dispatch_cluster": None}
        r._apply_bkbase_metadata(row, "not-a-dict")
        assert row["dispatch_cluster"] is None


# ============================================================
# P2 Runtime: _fetch_es_runtime + _apply_es_runtime
# ============================================================


class TestFetchEsRuntime:
    def _make_resource(self):
        return QueryDataLinkMetadataResource()

    def test_no_storage(self):
        r = self._make_resource()
        assert r._fetch_es_runtime(None) is None

    def test_success(self):
        r = self._make_resource()
        es = mock.MagicMock()
        es.current_index_info.return_value = {
            "datetime_object": "dt",
            "index": 0,
            "index_version": "v2",
        }
        es.make_index_name.return_value = "v2_xxx_20260513_0"
        es.get_index_info.return_value = {"size": 1000, "status": "open"}
        es._should_create_index.return_value = True

        out = r._fetch_es_runtime(es)
        assert out["current_index_name"] == "v2_xxx_20260513_0"
        assert out["current_index_detail"] == {"size": 1000, "status": "open"}
        assert out["should_rotate"] is True

    def test_es_api_failure(self):
        r = self._make_resource()
        es = mock.MagicMock()
        es.current_index_info.side_effect = RuntimeError("ES timeout")
        out = r._fetch_es_runtime(es)
        assert "_error" in out


class TestApplyEsRuntime:
    def _make_resource(self):
        return QueryDataLinkMetadataResource()

    def test_full(self):
        r = self._make_resource()
        row = {}
        r._apply_es_runtime(
            row,
            {
                "current_index_name": "v2_idx_0",
                "current_index_detail": {"size": 1000},
                "should_rotate": False,
            },
        )
        assert row["es_current_index_name"] == "v2_idx_0"
        assert row["es_current_index_info"] == {"size": 1000}
        assert row["es_should_rotate_index"] is False

    def test_no_detail_fallback_to_raw(self):
        r = self._make_resource()
        row = {}
        r._apply_es_runtime(
            row,
            {"current_index_info_raw": {"index": 0}, "should_rotate": True},
        )
        assert row["es_current_index_info"] == {"index": 0}


# ============================================================
# P2 Runtime: _fetch_component_status
# ============================================================


class TestFetchComponentStatus:
    def _make_resource(self):
        return QueryDataLinkMetadataResource()

    def test_none_instance(self):
        r = self._make_resource()
        assert r._fetch_component_status(None) is None

    def test_dict_response(self):
        r = self._make_resource()
        cfg = mock.MagicMock()
        # configure property to return dict
        type(cfg).component_status = mock.PropertyMock(return_value={"phase": "Ok", "message": ""})
        out = r._fetch_component_status(cfg)
        assert out == ("Ok", "")

    def test_string_response(self):
        r = self._make_resource()
        cfg = mock.MagicMock()
        type(cfg).component_status = mock.PropertyMock(return_value="Pending")
        out = r._fetch_component_status(cfg)
        assert out == ("Pending", None)

    def test_property_failure(self):
        r = self._make_resource()
        cfg = mock.MagicMock()
        type(cfg).component_status = mock.PropertyMock(side_effect=RuntimeError("svc down"))
        out = r._fetch_component_status(cfg)
        assert isinstance(out, dict) and "_error" in out


# ============================================================
# P2 Runtime: _record_runtime_error
# ============================================================


class TestRecordRuntimeError:
    def _make_resource(self):
        return QueryDataLinkMetadataResource()

    def test_bkbase_metadata_error_writes_remote_error(self):
        r = self._make_resource()
        row = {}
        r._record_runtime_error(row, "bkbase_metadata", {}, "timeout")
        assert "bkbase_metadata" in row["bkbase_remote_error"]
        assert "timeout" in row["bkbase_remote_error"]

    def test_es_runtime_error_writes_es_error(self):
        r = self._make_resource()
        row = {}
        r._record_runtime_error(row, "es_runtime", {}, "connection refused")
        assert row["es_runtime_error"] == "connection refused"

    def test_component_status_error_writes_to_component(self):
        r = self._make_resource()
        comp = {"kind": "DataId", "status_error": None}
        row = {"bkbase_components": [comp]}
        r._record_runtime_error(row, "component_status", {"comp_idx": 0}, "svc unavailable")
        assert comp["status_error"] == "svc unavailable"


# ============================================================
# P2 集成: _enrich_with_runtime 端到端流程 (mock 全部 fetch)
# ============================================================


class TestEnrichWithRuntimeIntegration:
    def _make_resource(self):
        return QueryDataLinkMetadataResource()

    def test_empty_rows(self):
        """空 rows 无副作用."""
        r = self._make_resource()
        r._enrich_with_runtime([], {})

    @mock.patch.object(QueryDataLinkMetadataResource, "_fetch_bkbase_metadata")
    def test_v4_row_triggers_bkbase_fetch(self, m_fetch):
        """V4 行 + 有 bk_base_data_id → 触发 BKBase fetch."""
        m_fetch.return_value = {"branches": [{"dispatch_cluster": "dispatch-1"}]}
        r = self._make_resource()
        row = {
            "datalink_version": "v4",
            "bk_base_data_id": 100,
            "vm_rt_name": "2_bkm_x",
            "result_table_id": "2_bkmonitor.x",
            "es_cluster_id": None,
            "bkbase_components": [],
        }
        r._enrich_with_runtime([row], {"databus_configs": {}, "es_storages": {}})
        assert m_fetch.called
        assert row.get("dispatch_cluster") == "dispatch-1"

    @mock.patch.object(QueryDataLinkMetadataResource, "_fetch_es_runtime")
    def test_es_row_triggers_es_fetch(self, m_fetch):
        m_fetch.return_value = {"current_index_name": "v2_idx", "should_rotate": False}
        r = self._make_resource()
        row = {
            "datalink_version": "v4",
            "bk_base_data_id": None,
            "vm_rt_name": None,
            "es_cluster_id": 27,
            "result_table_id": "log.foo",
            "bkbase_components": [],
        }
        es_storage = mock.MagicMock()
        r._enrich_with_runtime([row], {"databus_configs": {}, "es_storages": {"log.foo": es_storage}})
        assert m_fetch.called
        assert row.get("es_current_index_name") == "v2_idx"

    @mock.patch.object(QueryDataLinkMetadataResource, "_fetch_bkbase_metadata")
    def test_bkbase_fetch_failure_records_error(self, m_fetch):
        m_fetch.return_value = {"_error": "boom"}
        r = self._make_resource()
        row = {
            "datalink_version": "v4",
            "bk_base_data_id": 100,
            "es_cluster_id": None,
            "result_table_id": "x.y",
            "bkbase_components": [],
        }
        r._enrich_with_runtime([row], {"databus_configs": {}, "es_storages": {}})
        assert "boom" in (row.get("bkbase_remote_error") or "")

    def test_error_row_skipped(self):
        """已经 error 的行不再 enrich."""
        r = self._make_resource()
        row = {"error": "previous failure"}
        r._enrich_with_runtime([row], {"databus_configs": {}, "es_storages": {}})
        # 应该没有 runtime 字段写入
        assert "bkbase_remote_error" not in row
