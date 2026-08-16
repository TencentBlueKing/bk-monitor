"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from django.conf import settings
from django.utils import timezone

from metadata import models
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.tests.common_utils import consul_client

base_time = datetime(2020, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def create_or_delete_records(mocker):
    """
    创建或删除测试数据
    """
    delete_consul_config = mocker.patch(
        "metadata.models.data_source.DataSource.delete_consul_config", return_value=True
    )
    delete_consul_config.start()

    models.Space.objects.all().delete()
    models.SpaceDataSource.objects.all().delete()
    models.SpaceResource.objects.all().delete()
    models.DataSource.objects.all().delete()
    models.ResultTable.objects.all().delete()
    models.AccessVMRecord.objects.all().delete()
    models.ESStorage.objects.all().delete()

    # ---------------------空间数据--------------------- #
    models.Space.objects.create(
        space_type_id="bkcc",
        space_id="1",
        space_name="test",
        space_code="1111test",
    )
    models.SpaceDataSource.objects.create(bk_data_id=50010, space_type_id="bkcc", space_id="1")
    models.SpaceDataSource.objects.create(bk_data_id=50011, space_type_id="bkcc", space_id="1")

    models.Space.objects.create(
        space_type_id="bkci",
        space_id="bkmonitor",
        space_name="bkmonitor",
        space_code="1111bkm",
        bk_tenant_id="system",
        id=10000,
    )
    models.SpaceResource.objects.create(
        space_type_id="bkci", space_id="bkmonitor", resource_type="bkcc", resource_id="1"
    )

    models.Space.objects.create(
        space_type_id="bksaas",
        space_id="monitor_saas",
        space_name="monitor_saas",
        space_code="1111bksaas",
        id=10008,
    )
    # ---------------------空间数据--------------------- #

    # ---------------------指标数据--------------------- #
    models.DataSource.objects.create(
        bk_data_id=50010,
        data_name="metric_tst",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
    )
    models.ResultTable.objects.create(
        table_id="1001_bkmonitor_time_series_50010.__default__",
        bk_biz_id=1001,
        is_custom_table=False,
    )
    models.AccessVMRecord.objects.create(
        result_table_id="1001_bkmonitor_time_series_50010.__default__",
        vm_cluster_id=111,
        storage_cluster_id=111,
        vm_result_table_id="1001_vm_test_50010",
        bk_base_data_id=50010,
    )
    models.ResultTableField.objects.create(
        table_id="1001_bkmonitor_time_series_50010.__default__",
        field_name="metric_a",
        field_type="float",
        tag="metric",
        is_config_by_user=False,
    )
    models.DataSourceResultTable.objects.create(
        bk_data_id=50010, table_id="1001_bkmonitor_time_series_50010.__default__"
    )
    # ---------------------指标数据--------------------- #

    # ---------------------预计算数据--------------------- #
    models.RecordRule.objects.create(space_type="bkcc", space_id="1", table_id="bkm_1_record_rule.__default__")

    # ---------------------日志数据--------------------- #
    models.ESStorage.objects.create(
        table_id="1001_bklog.stdout",
        storage_cluster_id=11,
    )
    models.ResultTable.objects.create(
        table_id="1001_bklog.stdout",
        table_name_zh="stdout",
        data_label="bklog_index_set_1001",
        is_custom_table=False,
    )
    models.ResultTable.objects.create(
        table_id="apm_global.precalculate_storage_1",
        table_name_zh="apm_global.precalculate_storage_1_rt",
        bk_biz_id_alias="biz_id",
        is_custom_table=True,
    )
    models.ResultTable.objects.create(
        table_id="apm_global.precalculate_storage_2",
        table_name_zh="apm_global.precalculate_storage_2_rt",
        bk_biz_id_alias="biz_id",
        is_custom_table=True,
    )
    models.ResultTable.objects.create(
        table_id="apm_global.precalculate_storage_3",
        table_name_zh="apm_global.precalculate_storage_3_rt",
        bk_biz_id_alias="biz_id",
        is_custom_table=True,
    )
    models.ClusterInfo.objects.create(
        cluster_id=11,
        cluster_name="test_es_1",
        cluster_type=models.ClusterInfo.TYPE_ES,
        domain_name="es_test.1",
        port=9090,
        description="",
        is_default_cluster=True,
        version="5.x",
    )
    models.StorageClusterRecord.objects.create(
        table_id="1001_bklog.stdout", cluster_id=11, is_current=True, enable_time=base_time - timedelta(days=30)
    )
    models.StorageClusterRecord.objects.create(
        table_id="1001_bklog.stdout",
        cluster_id=12,
        is_current=False,
        enable_time=base_time - timedelta(days=60),
        disable_time=base_time - timedelta(days=30),
    )
    models.StorageClusterRecord.objects.create(
        table_id="1001_bklog.stdout", cluster_id=13, is_current=True, enable_time=None
    )
    models.DataSourceResultTable.objects.create(bk_data_id=50011, table_id="1001_bklog.stdout")

    # ---------------------日志数据--------------------- #

    # ---------------------全局事件--------------------- #
    models.DataSource.objects.create(
        bk_data_id=60010,
        data_name="test_event",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="test",
        is_custom_source=False,
        is_platform_data_id=True,
        space_type_id="bkci",
    )
    models.ResultTable.objects.create(
        table_id="bkmonitor_event_60010",
        table_name_zh="test_devops_event",
        bk_biz_id_alias="dimensions.project_id",
        is_custom_table=True,
    )
    models.ESStorage.objects.create(
        table_id="bkmonitor_event_60010",
        storage_cluster_id=11,
    )
    models.DataSourceResultTable.objects.create(table_id="bkmonitor_event_60010", bk_data_id=60010)

    # ---------------------全局事件--------------------- #

    # ---------------------APM 全局 ES 数据--------------------- #
    models.DataSource.objects.create(
        bk_data_id=60011,
        data_name="bkapm_shared_trace_0001",
        mq_cluster_id=1,
        mq_config_id=1,
        etl_config="bk_flat_batch",
        is_custom_source=True,
        is_platform_data_id=True,
        space_type_id="bkcc",
        space_uid="bkcc__2",
    )
    models.ResultTable.objects.create(
        table_id="apm_global.shared_trace_0001",
        table_name_zh="apm_shared_trace_0001",
        bk_biz_id=0,
        bk_biz_id_alias="bk_biz_id",
        is_custom_table=True,
        schema_type=models.ResultTable.SCHEMA_TYPE_FREE,
        default_storage=models.ClusterInfo.TYPE_ES,
    )
    models.ESStorage.objects.create(
        table_id="apm_global.shared_trace_0001",
        storage_cluster_id=11,
    )
    models.DataSourceResultTable.objects.create(
        table_id="apm_global.shared_trace_0001",
        bk_data_id=60011,
    )
    # ---------------------APM 全局 ES 数据--------------------- #

    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    models.DataSource.objects.all().delete()
    models.ResultTable.objects.all().delete()
    models.AccessVMRecord.objects.all().delete()
    models.ESStorage.objects.all().delete()
    models.ClusterInfo.objects.all().delete()
    models.StorageClusterRecord.objects.all().delete()
    models.Space.objects.all().delete()
    models.SpaceDataSource.objects.all().delete()
    models.SpaceResource.objects.all().delete()
    delete_consul_config.stop()


@pytest.mark.django_db(databases="__all__")
def test_push_space_to_rt_router_for_bkcc(create_or_delete_records):
    """测试SPACE_TO_RESULT_TABLE路由推送- BKCC类型"""
    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            settings.ENABLE_MULTI_TENANT_MODE = True
            client = SpaceTableIDRedis()
            client.push_space_table_ids(space_type="bkcc", space_id="1", is_publish=True)

            expected = '{"bkmonitor_event_60010.__default__":{"filters":[{"dimensions.project_id":"1"}]},"apm_global.shared_trace_0001":{"filters":[{"bk_biz_id":"1"}]},"1001_bklog.stdout":{"filters":[{"bk_biz_id":"1"}]},"1001_bkmonitor_time_series_50010.__default__":{"filters":[{"bk_biz_id":"1"}]},"bkm_1_record_rule.__default__":{"filters":[]}}'

            # 验证 RedisTools.hmset_to_redis 是否被正确调用
            # 获取实际的调用参数
            args, kwargs = mock_hmset_to_redis.call_args
            actual_redis_key = args[0]
            actual_mapping = args[1]

            assert actual_redis_key == "bkmonitorv3:spaces:space_to_result_table"
            actual_json = actual_mapping["bkcc__1|system"]
            assert json.loads(actual_json) == json.loads(expected)

            mock_publish.assert_called_once_with(
                "bkmonitorv3:spaces:space_to_result_table:channel",
                ["bkcc__1|system"],
            )

    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            settings.ENABLE_MULTI_TENANT_MODE = False
            client = SpaceTableIDRedis()
            client.push_space_table_ids(space_type="bkcc", space_id="1", is_publish=True)

            expected = (
                '{"bkmonitor_event_60010.__default__":{"filters":[{"dimensions.project_id":"1"}]},'
                '"apm_global.shared_trace_0001":{"filters":[{"bk_biz_id":"1"}]},'
                '"1001_bklog.stdout":{"filters":[{"bk_biz_id":"1"}]},'
                '"1001_bkmonitor_time_series_50010.__default__":{"filters":[{"bk_biz_id":"1"}]},'
                '"bkm_1_record_rule.__default__":{"filters":[]}}'
            )
            args, kwargs = mock_hmset_to_redis.call_args
            actual_redis_key = args[0]
            actual_mapping = args[1]

            assert actual_redis_key == "bkmonitorv3:spaces:space_to_result_table"
            actual_json = actual_mapping["bkcc__1"]
            assert json.loads(actual_json) == json.loads(expected)

            mock_publish.assert_called_once_with(
                "bkmonitorv3:spaces:space_to_result_table:channel",
                ["bkcc__1"],
            )


@pytest.mark.django_db(databases="__all__")
def test_push_space_to_rt_router_for_bkci(create_or_delete_records):
    """测试SPACE_TO_RESULT_TABLE路由推送- BKCI类型"""
    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            settings.ENABLE_MULTI_TENANT_MODE = True
            client = SpaceTableIDRedis()
            client.push_space_table_ids(space_type="bkci", space_id="bkmonitor", is_publish=True)

            expected = '{"bkmonitor_event_60010.__default__":{"filters":[{"projectId":"bkmonitor"}]},"custom_report_aggate.base":{"filters":[{"bk_biz_id":"-10000"}]},"bkm_statistics.base":{"filters":[{"bk_biz_id":"-10000"}]},"apm_global.precalculate_storage_1":{"filters":[{"biz_id":"-10000"}]},"apm_global.precalculate_storage_2":{"filters":[{"biz_id":"-10000"}]},"apm_global.precalculate_storage_3":{"filters":[{"biz_id":"-10000"}]},"apm_global.shared_trace_0001":{"filters":[{"bk_biz_id":"-10000"}]}}'

            # 验证 RedisTools.hmset_to_redis 是否被正确调用
            args, kwargs = mock_hmset_to_redis.call_args
            actual_redis_key = args[0]
            actual_mapping = args[1]
            assert actual_redis_key == "bkmonitorv3:spaces:space_to_result_table"
            actual_json = actual_mapping["bkci__bkmonitor|system"]
            assert json.loads(actual_json) == json.loads(expected)

            # 验证 RedisTools.publish 是否被正确调用
            mock_publish.assert_called_once_with(
                "bkmonitorv3:spaces:space_to_result_table:channel",
                ["bkci__bkmonitor|system"],
            )


@pytest.mark.django_db(databases="__all__")
def test_push_space_to_rt_router_for_bksaas(create_or_delete_records):
    """测试SPACE_TO_RESULT_TABLE路由推送- BKSAAS类型"""
    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            settings.ENABLE_MULTI_TENANT_MODE = True
            client = SpaceTableIDRedis()
            client.push_space_table_ids(space_type="bksaas", space_id="monitor_saas", is_publish=True)

            expected = '{"custom_report_aggate.base":{"filters":[{"bk_biz_id":"-10008"}]},"bkm_statistics.base":{"filters":[{"bk_biz_id":"-10008"}]},"apm_global.precalculate_storage_1":{"filters":[{"biz_id":"-10008"}]},"apm_global.precalculate_storage_2":{"filters":[{"biz_id":"-10008"}]},"apm_global.precalculate_storage_3":{"filters":[{"biz_id":"-10008"}]},"apm_global.shared_trace_0001":{"filters":[{"bk_biz_id":"-10008"}]}}'

            # 验证 RedisTools.hmset_to_redis 是否被正确调用
            args, kwargs = mock_hmset_to_redis.call_args
            actual_redis_key = args[0]
            actual_mapping = args[1]
            assert actual_redis_key == "bkmonitorv3:spaces:space_to_result_table"
            actual_json = actual_mapping["bksaas__monitor_saas|system"]
            assert json.loads(actual_json) == json.loads(expected)

            # 验证 RedisTools.publish 是否被正确调用
            mock_publish.assert_called_once_with(
                "bkmonitorv3:spaces:space_to_result_table:channel",
                ["bksaas__monitor_saas|system"],
            )


@pytest.mark.django_db(databases="__all__")
def test_compose_apm_all_type_table_ids(create_or_delete_records):
    client = SpaceTableIDRedis()

    bkci_data = client._compose_apm_all_type_table_ids(space_type="bkci", space_id="bkmonitor")
    assert bkci_data == {
        "apm_global.precalculate_storage_1": {"filters": [{"biz_id": "-10000"}]},
        "apm_global.precalculate_storage_2": {"filters": [{"biz_id": "-10000"}]},
        "apm_global.precalculate_storage_3": {"filters": [{"biz_id": "-10000"}]},
        "apm_global.shared_trace_0001": {"filters": [{"bk_biz_id": "-10000"}]},
    }

    bksaas_data = client._compose_apm_all_type_table_ids(space_type="bksaas", space_id="monitor_saas")
    assert bksaas_data == {
        "apm_global.precalculate_storage_1": {"filters": [{"biz_id": "-10008"}]},
        "apm_global.precalculate_storage_2": {"filters": [{"biz_id": "-10008"}]},
        "apm_global.precalculate_storage_3": {"filters": [{"biz_id": "-10008"}]},
        "apm_global.shared_trace_0001": {"filters": [{"bk_biz_id": "-10008"}]},
    }


def create_log_global_table(
    *,
    table_id: str,
    query_router_config: dict,
    storage_type: str = models.ClusterInfo.TYPE_ES,
    bk_biz_id: int = 999,
    bk_tenant_id: str = "system",
    is_enable: bool = True,
    is_deleted: bool = False,
    value_type: str = models.ResultTableOption.TYPE_DICT,
    raw_value: str | None = None,
) -> None:
    models.ResultTable.objects.create(
        table_id=table_id,
        table_name_zh=table_id,
        bk_biz_id=bk_biz_id,
        bk_tenant_id=bk_tenant_id,
        default_storage=storage_type,
        is_custom_table=False,
        is_enable=is_enable,
        is_deleted=is_deleted,
    )
    models.ResultTableOption.objects.create(
        table_id=table_id,
        name=models.ResultTableOption.OPTION_QUERY_ROUTER_CONFIG,
        value=raw_value if raw_value is not None else json.dumps(query_router_config),
        value_type=value_type,
        creator="system",
        bk_tenant_id=bk_tenant_id,
    )


@pytest.mark.django_db(databases="__all__")
def test_compose_log_global_table_ids_match_specific_space_type_and_all(create_or_delete_records):
    spaces = {
        space.space_type_id: space
        for space in models.Space.objects.filter(space_type_id__in=["bkcc", "bkci", "bksaas"])
    }
    for space_type in spaces:
        create_log_global_table(
            table_id=f"global_{space_type}.log",
            query_router_config={
                "space_type": space_type,
                "filter_key": "space_id",
                "filter_value": "space_id",
            },
        )
    create_log_global_table(
        table_id="global_all.log",
        storage_type=models.ClusterInfo.TYPE_DORIS,
        query_router_config={
            "space_type": "all",
            "filter_key": "bk_biz_id",
            "filter_value": "bk_biz_id",
        },
    )

    client = SpaceTableIDRedis()
    compose_methods = {
        "bkcc": client._compose_bkcc_space_table_ids,
        "bkci": client._compose_bkci_space_table_ids,
        "bksaas": client._compose_bksaas_space_table_ids,
    }
    for space_type, space in spaces.items():
        values = client._compose_log_global_table_ids(space)
        space_values = compose_methods[space_type](space)

        assert values[f"global_{space_type}.log"] == {"filters": [{"space_id": space.space_id}]}
        assert values["global_all.log"] == {"filters": [{"bk_biz_id": space.get_bk_biz_id()}]}
        assert set(values) == {f"global_{space_type}.log", "global_all.log"}
        assert space_values[f"global_{space_type}.log"] == values[f"global_{space_type}.log"]
        assert space_values["global_all.log"] == values["global_all.log"]


@pytest.mark.django_db(databases="__all__")
def test_compose_log_global_table_ids_keep_owner_route_unfiltered(create_or_delete_records):
    create_log_global_table(
        table_id="owner_global.log",
        bk_biz_id=1,
        query_router_config={
            "space_type": "all",
            "filter_key": "bk_biz_id",
            "filter_value": "bk_biz_id",
        },
    )
    client = SpaceTableIDRedis()
    bkcc_space = models.Space.objects.get(space_type_id="bkcc", space_id="1")
    bksaas_space = models.Space.objects.get(space_type_id="bksaas", space_id="monitor_saas")

    assert "owner_global.log" not in client._compose_log_global_table_ids(bkcc_space)
    assert client._compose_bkcc_space_table_ids(bkcc_space)["owner_global.log"] == {"filters": []}
    assert client._compose_log_global_table_ids(bksaas_space)["owner_global.log"] == {
        "filters": [{"bk_biz_id": bksaas_space.get_bk_biz_id()}]
    }


@pytest.mark.django_db(databases="__all__")
def test_compose_log_global_table_ids_ignore_invalid_or_ineligible_options(create_or_delete_records):
    create_log_global_table(table_id="valid_default.log", query_router_config={})
    create_log_global_table(table_id="invalid_json.log", query_router_config={}, raw_value="{")
    create_log_global_table(
        table_id="invalid_type.log",
        query_router_config={"space_type": "all"},
        value_type=models.ResultTableOption.TYPE_STRING,
    )
    create_log_global_table(
        table_id="empty_filter_key.log",
        query_router_config={"space_type": "all", "filter_key": "", "filter_value": "space_id"},
    )
    create_log_global_table(
        table_id="unknown_space_type.log",
        query_router_config={"space_type": "bcs", "filter_key": "bk_biz_id", "filter_value": "bk_biz_id"},
    )
    create_log_global_table(
        table_id="unknown_filter_value.log",
        query_router_config={"space_type": "all", "filter_key": "bk_biz_id", "filter_value": "space_uid"},
    )
    create_log_global_table(table_id="disabled.log", query_router_config={}, is_enable=False)
    create_log_global_table(table_id="deleted.log", query_router_config={}, is_deleted=True)
    create_log_global_table(
        table_id="vm_storage.log",
        query_router_config={},
        storage_type=models.ClusterInfo.TYPE_VM,
    )
    create_log_global_table(
        table_id="other_tenant.log",
        query_router_config={},
        bk_tenant_id="other-tenant",
    )

    space = models.Space.objects.get(space_type_id="bksaas", space_id="monitor_saas")
    values = SpaceTableIDRedis()._compose_log_global_table_ids(space)

    assert values == {"valid_default.log": {"filters": [{"bk_biz_id": space.get_bk_biz_id()}]}}
    assert models.ResultTableOption.OPTION_QUERY_ROUTER_CONFIG not in models.ResultTableOption.QUERY_OPTION_NAME_LIST


@pytest.mark.django_db(databases="__all__")
def test_compose_bkci_level_table_ids(create_or_delete_records):
    """
    测试特殊路由 -- BKCI下也使用RT中的bk_biz_id_alias
    """
    client = SpaceTableIDRedis()
    settings.SPECIAL_RT_ROUTE_ALIAS_RESULT_TABLE_LIST = ["bkmonitor_event_60010"]
    data = client._compose_bkci_level_table_ids(space_type="bkci", space_id="bkmonitor", bk_tenant_id="system")
    expected = {"bkmonitor_event_60010": {"filters": [{"dimensions.project_id": "bkmonitor"}]}}
    assert data == expected
