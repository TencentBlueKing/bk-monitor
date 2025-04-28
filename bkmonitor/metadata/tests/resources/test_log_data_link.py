"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest

from metadata import models
from unittest.mock import patch, call

from metadata.resources import CreateOrUpdateLogRouter

non_exist_doris_table_id = "2_bklog.test_doris_non_exists"
exist_doris_table_id = "2_bklog.test_doris_exists"


@pytest.fixture
def create_or_delete_records(mocker):
    # ResultTable
    models.ResultTable.objects.create(
        table_id=exist_doris_table_id,
        bk_biz_id=1001,
        is_custom_table=False,
    )

    # Space
    models.Space.objects.create(
        space_type_id="bkcc",
        space_id=2,
        space_code="2_space",
        space_name="2_space",
    )

    # 平台公共默认Doris集群
    models.ClusterInfo.objects.create(
        domain_name="test.doris.db",
        cluster_name="default_doris",
        cluster_type=models.ClusterInfo.TYPE_DORIS,
        port=9200,
        is_default_cluster=True,
        cluster_id=10034,
    )

    # 用户Doris独立集群
    models.ClusterInfo.objects.create(
        domain_name="custom.doris.db",
        cluster_name="custom_doris",
        cluster_type=models.ClusterInfo.TYPE_DORIS,
        port=9200,
        is_default_cluster=False,
        cluster_id=10035,
    )
    yield
    models.ResultTable.objects.filter(table_id__in=[non_exist_doris_table_id, exist_doris_table_id]).delete()
    models.ResultTableField.objects.filter(table_id__in=[non_exist_doris_table_id, exist_doris_table_id]).delete()
    models.DorisStorage.objects.filter(table_id__in=[non_exist_doris_table_id, exist_doris_table_id]).delete()
    models.ClusterInfo.objects.all().delete()
    models.Space.objects.all().delete()


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_create_or_update_log_router_resource_for_bkcc(create_or_delete_records):
    # 创建Doris链路,不指定存储集群即使用默认集群
    create_params = dict(
        space_type="bkcc",
        space_id="2",
        table_id=non_exist_doris_table_id,
        data_label="bkdata_index_set_7839",
        index_set="2_bklog_pure_doris,2_bklog_doris_log",
        source_type="bkdata",
        bkbase_table_id="2_bklog_pure_doris,2_bklog_doris_log",
        storage_type="doris",
    )

    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            CreateOrUpdateLogRouter().request(**create_params)
            expected_space_router = {"bkcc__2": '{"2_bklog.test_doris_non_exists":{"filters":[]}}'}
            expected_rt_detail_router = {
                non_exist_doris_table_id: '{"db":"2_bklog_pure_doris,2_bklog_doris_log","measurement":"doris",'
                '"storage_type":"bk_sql","data_label":"bkdata_index_set_7839"}'
            }

            # 创建流程,先推送RT详情路由,再推送空间路由
            mock_hmset_to_redis.assert_has_calls(
                [
                    call("bkmonitorv3:spaces:result_table_detail", expected_rt_detail_router),
                    call("bkmonitorv3:spaces:space_to_result_table", expected_space_router),
                ]
            )

            mock_publish.assert_has_calls(
                [
                    call("bkmonitorv3:spaces:result_table_detail:channel", [non_exist_doris_table_id]),
                    call("bkmonitorv3:spaces:space_to_result_table:channel", ["bkcc__2"]),
                ]
            )

            doris_storage_ins = models.DorisStorage.objects.get(table_id=non_exist_doris_table_id)
            assert doris_storage_ins.bkbase_table_id == "2_bklog_pure_doris,2_bklog_doris_log"
            assert doris_storage_ins.storage_cluster_id == 10034
            assert doris_storage_ins.index_set == "2_bklog_pure_doris,2_bklog_doris_log"
            assert doris_storage_ins.source_type == "bkdata"

            result_table_ins = models.ResultTable.objects.get(table_id=non_exist_doris_table_id)
            assert result_table_ins.data_label == "bkdata_index_set_7839"
            assert result_table_ins.default_storage == "doris"
            assert result_table_ins.bk_biz_id == 2

    modify_params = dict(
        space_type="bkcc",
        space_id="2",
        table_id=non_exist_doris_table_id,
        data_label="bkdata_index_set_7839",
        index_set="2_bklog_pure_doris",
        source_type="bkdata",
        bkbase_table_id="2_bklog_pure_doris",
        storage_type="doris",
        cluster_id=10035,
    )

    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            CreateOrUpdateLogRouter().request(**modify_params)
            expected_rt_detail_router = {
                non_exist_doris_table_id: '{"db":"2_bklog_pure_doris","measurement":"doris",'
                '"storage_type":"bk_sql","data_label":"bkdata_index_set_7839"}'
            }

            # 创建流程,先推送RT详情路由,再推送空间路由
            mock_hmset_to_redis.assert_has_calls(
                [
                    call("bkmonitorv3:spaces:result_table_detail", expected_rt_detail_router),
                ]
            )

            mock_publish.assert_has_calls(
                [
                    call("bkmonitorv3:spaces:result_table_detail:channel", [non_exist_doris_table_id]),
                ]
            )

            doris_storage_ins = models.DorisStorage.objects.get(table_id=non_exist_doris_table_id)
            assert doris_storage_ins.bkbase_table_id == "2_bklog_pure_doris"
            assert doris_storage_ins.storage_cluster_id == 10035
            assert doris_storage_ins.index_set == "2_bklog_pure_doris"
            assert doris_storage_ins.source_type == "bkdata"

            result_table_ins = models.ResultTable.objects.get(table_id=non_exist_doris_table_id)
            assert result_table_ins.data_label == "bkdata_index_set_7839"
            assert result_table_ins.default_storage == "doris"
            assert result_table_ins.bk_biz_id == 2
