"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest.mock import call, patch

from django.conf import settings
import pytest

from metadata import models
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.tests.common_utils import consul_client


@pytest.fixture
def create_or_delete_records(mocker):
    models.Space.objects.all().delete()
    models.BkBaseResultTable.objects.all().delete()
    models.ClusterInfo.objects.all().delete()
    models.DorisStorage.objects.all().delete()
    models.ResultTable.objects.all().delete()
    models.ResultTableField.objects.all().delete()
    models.AccessVMRecord.objects.all().delete()

    # Space
    models.Space.objects.create(
        bk_tenant_id="riot",
        space_type_id="bkcc",
        space_id=2,
        space_code="2_space",
        space_name="2_space",
    )

    # Doris结果表
    # ResultTable
    models.ResultTable.objects.create(
        bk_tenant_id="riot",
        table_id="2_bklog.test_doris_non_exists",
        bk_biz_id=2,
        is_custom_table=False,
        default_storage=models.ClusterInfo.TYPE_DORIS,
        data_label="bkdata_index_set_7839",
    )

    # DorisStorage
    models.DorisStorage.objects.create(
        bk_tenant_id="riot",
        bkbase_table_id="2_bklog_pure_doris,2_bklog_doris_log",
        storage_cluster_id=10034,
        index_set="2_bklog_pure_doris,2_bklog_doris_log",
        source_type="bkdata",
        table_id="2_bklog.test_doris_non_exists",
    )

    # 计算平台结果表
    models.ResultTable.objects.create(
        bk_tenant_id="riot",
        table_id="2_bkbase_metric_agg.__default__",
        bk_biz_id=2,
        is_custom_table=False,
        default_storage=models.ClusterInfo.TYPE_BKDATA,
        data_label="bkbase_rt_meta_metric",
    )

    models.ResultTableField.objects.create(
        bk_tenant_id="riot",
        table_id="2_bkbase_metric_agg.__default__",
        field_name="metric_a",
        field_type="long",
        tag="metric",
        unit="",
        is_config_by_user=False,
        creator="system",
    )
    models.ResultTableField.objects.create(
        bk_tenant_id="riot",
        table_id="2_bkbase_metric_agg.__default__",
        field_name="metric_b",
        field_type="long",
        tag="metric",
        unit="",
        is_config_by_user=False,
        creator="system",
    )
    models.ResultTableField.objects.create(
        bk_tenant_id="riot",
        table_id="2_bkbase_metric_agg.__default__",
        field_name="dimension_c",
        field_type="long",
        tag="dimension",
        unit="",
        is_config_by_user=False,
        creator="system",
    )

    # Doris字段别名
    models.ESFieldQueryAliasOption.objects.create(
        table_id="2_bklog.test_doris_non_exists",
        bk_tenant_id="riot",
        field_path="__ext.pod_name",
        path_type="keyword",
        query_alias="pod_name",
        is_deleted=False,
    )

    models.ESFieldQueryAliasOption.objects.create(
        table_id="2_bklog.test_doris_non_exists",
        bk_tenant_id="riot",
        field_path="__ext.pod_ip",
        path_type="keyword",
        query_alias="pod_ip",
        is_deleted=False,
    )

    # VM结果表
    models.BkBaseResultTable.objects.create(
        monitor_table_id="1001_bkmonitor_time_series_50010.__default__",
        bkbase_data_name="bkm_data_link_test",
        bkbase_table_id="bkm_1001_bkmonitor_time_series_50010",
        storage_type=models.ClusterInfo.TYPE_VM,
        data_link_name="bkm_data_link_test",
        storage_cluster_id=100111,
    )
    models.AccessVMRecord.objects.create(
        bk_tenant_id="riot",
        result_table_id="1001_bkmonitor_time_series_50010.__default__",
        vm_cluster_id=100111,
        vm_result_table_id="bkm_1001_bkmonitor_time_series_50010",
        bk_base_data_id=50010,
    )
    models.ResultTableOption.objects.create(
        bk_tenant_id="riot",
        table_id="1001_bkmonitor_time_series_50010.__default__",
        name="cmdb_level_vm_rt",
        value="bkm_1001_bkmonitor_time_series_50010_cmdb",
        value_type="string",
        creator="system",
    )

    models.ClusterInfo.objects.create(
        cluster_name="vm-plat",
        cluster_type=models.ClusterInfo.TYPE_VM,
        domain_name="test.domain.vm",
        port=9090,
        description="",
        cluster_id=100111,
        is_default_cluster=False,
        version="5.x",
    )

    yield
    mocker.patch("bkmonitor.utils.consul.BKConsul", side_effect=consul_client)
    models.Space.objects.all().delete()
    models.BkBaseResultTable.objects.all().delete()
    models.ClusterInfo.objects.all().delete()
    models.DorisStorage.objects.all().delete()
    models.ResultTable.objects.all().delete()
    models.ResultTableField.objects.all().delete()
    models.AccessVMRecord.objects.all().delete()
    models.ESFieldQueryAliasOption.objects.all().delete()


@pytest.mark.django_db(databases="__all__")
def test_push_doris_table_id_detail(create_or_delete_records):
    settings.ENABLE_MULTI_TENANT_MODE = True

    # 结果表详情路由推送 后台任务方式
    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            space_client = SpaceTableIDRedis()
            space_client.push_doris_table_id_detail(
                bk_tenant_id="riot", table_id_list=["2_bklog.test_doris_non_exists"], is_publish=True
            )
            expected_rt_detail_router = {
                "2_bklog.test_doris_non_exists|riot": '{"db":"2_bklog_pure_doris,2_bklog_doris_log",'
                '"measurement":"doris","storage_type":"bk_sql",'
                '"data_label":"bkdata_index_set_7839","field_alias":{'
                '"pod_name":"__ext.pod_name","pod_ip":"__ext.pod_ip"}}'
            }

            mock_hmset_to_redis.assert_has_calls(
                [
                    call("bkmonitorv3:spaces:result_table_detail", expected_rt_detail_router),
                ]
            )

            mock_publish.assert_has_calls(
                [
                    call("bkmonitorv3:spaces:result_table_detail:channel", ["2_bklog.test_doris_non_exists|riot"]),
                ]
            )

    settings.ENABLE_MULTI_TENANT_MODE = False


@pytest.mark.django_db(databases="__all__")
def test_push_bkbase_table_id_detail(create_or_delete_records):
    settings.ENABLE_MULTI_TENANT_MODE = True

    # 结果表详情路由推送 后台任务方式
    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            space_client = SpaceTableIDRedis()
            space_client.push_bkbase_table_id_detail(
                bk_tenant_id="riot", table_id_list=["2_bkbase_metric_agg.__default__"], is_publish=True
            )
            expected_rt_detail_router = {
                "2_bkbase_metric_agg.__default__|riot": '{"db":"2_bkbase_metric_agg",'
                '"measurement":"",'
                '"storage_type":"bk_sql",'
                '"data_label":"bkbase_rt_meta_metric",'
                '"fields":["metric_a","metric_b"]}'
            }

            mock_hmset_to_redis.assert_has_calls(
                [
                    call("bkmonitorv3:spaces:result_table_detail", expected_rt_detail_router),
                ]
            )

            mock_publish.assert_has_calls(
                [
                    call("bkmonitorv3:spaces:result_table_detail:channel", ["2_bkbase_metric_agg.__default__|riot"]),
                ]
            )

    settings.ENABLE_MULTI_TENANT_MODE = False
