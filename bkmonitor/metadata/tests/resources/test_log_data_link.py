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

import pytest

from metadata import models
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.resources import CreateOrUpdateLogRouter

non_exist_doris_table_id = "2_bklog.test_doris_non_exists"
exist_doris_table_id = "2_bklog.test_doris_exists"

non_exist_es_table_id = "2_bklog.test_es_non_exists"
exist_es_table_id = "2_bklog.test_es_exists"


@pytest.fixture
def create_or_delete_records(mocker):
    # ResultTable
    models.ResultTable.objects.create(
        table_id=exist_doris_table_id,
        bk_biz_id=1001,
        is_custom_table=False,
    )
    models.ResultTable.objects.create(
        table_id=exist_es_table_id,
        bk_biz_id=1001,
        is_custom_table=False,
    )

    # Space
    models.Space.objects.update_or_create(
        space_type_id="bkcc",
        space_id=2,
        defaults={
            "space_code": "2_space",
            "space_name": "2_space",
        },
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

    # 平台公共默认Doris集群
    models.ClusterInfo.objects.create(
        domain_name="test.es.db",
        cluster_name="default_es",
        cluster_type=models.ClusterInfo.TYPE_ES,
        port=9200,
        is_default_cluster=True,
        cluster_id=10036,
    )

    # 用户Doris独立集群
    models.ClusterInfo.objects.create(
        domain_name="custom.es.db",
        cluster_name="custom_es",
        cluster_type=models.ClusterInfo.TYPE_ES,
        port=9200,
        is_default_cluster=False,
        cluster_id=10037,
    )
    yield
    models.ResultTable.objects.filter(
        table_id__in=[non_exist_doris_table_id, exist_doris_table_id, non_exist_es_table_id, exist_es_table_id]
    ).delete()
    models.ResultTableField.objects.filter(
        table_id__in=[non_exist_doris_table_id, exist_doris_table_id, non_exist_es_table_id, exist_es_table_id]
    ).delete()
    models.DorisStorage.objects.filter(table_id__in=[non_exist_doris_table_id, exist_doris_table_id]).delete()
    models.ESStorage.objects.filter(table_id__in=[non_exist_es_table_id, exist_es_table_id]).delete()
    models.ClusterInfo.objects.all().delete()
    models.Space.objects.all().delete()


@pytest.mark.django_db(databases="__all__")
def test_create_or_update_log_doris_router_resource_for_bkcc(create_or_delete_records):
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

    # 空间路由推送 后台任务方式
    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            space_client = SpaceTableIDRedis()
            space_client.push_space_table_ids("bkcc", "2", is_publish=True)
            expected_space_router = {"bkcc__2": '{"2_bklog.test_doris_non_exists":{"filters":[]}}'}

            mock_hmset_to_redis.assert_has_calls(
                [
                    call("bkmonitorv3:spaces:space_to_result_table", expected_space_router),
                ]
            )

            mock_publish.assert_has_calls(
                [
                    call("bkmonitorv3:spaces:space_to_result_table:channel", ["bkcc__2"]),
                ]
            )

    # 结果表详情路由推送 后台任务方式
    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            space_client = SpaceTableIDRedis()
            space_client.push_doris_table_id_detail(
                bk_tenant_id="system", table_id_list=[non_exist_doris_table_id], is_publish=True
            )
            expected_rt_detail_router = {
                non_exist_doris_table_id: '{"db":"2_bklog_pure_doris,2_bklog_doris_log","measurement":"doris",'
                '"storage_type":"bk_sql","data_label":"bkdata_index_set_7839"}'
            }

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


@pytest.mark.django_db(databases="__all__")
def test_create_or_update_log_es_router_resource_for_bkcc(create_or_delete_records):
    # 创建ES链路,不指定存储集群即使用默认集群
    create_params = dict(
        space_type="bkcc",
        space_id="2",
        table_id=non_exist_es_table_id,
        data_label="bkdata_index_set_6788",
        index_set="2_bklog_pure_es,2_bklog_es_log",
        source_type="bkdata",
        bkbase_table_id="2_bklog_pure_es,2_bklog_es_log",
        storage_type="elasticsearch",
        origin_table_id=non_exist_es_table_id,
    )

    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            CreateOrUpdateLogRouter().request(**create_params)

            storage_record_enable_timestamp = int(
                models.StorageClusterRecord.objects.get(table_id=non_exist_es_table_id).enable_time.timestamp()
            )
            expected_space_router = {"bkcc__2": '{"2_bklog.test_es_non_exists":{"filters":[]}}'}

            detail_string = (
                '{"storage_id":3,"db":"2_bklog_pure_es,2_bklog_es_log",'
                '"measurement":"__default__","source_type":"bkdata","options":{},'
                '"storage_type":"elasticsearch","storage_cluster_records":[{'
                '"storage_id":3,"enable_time":1747130440}],'
                '"data_label":"bkdata_index_set_6788","field_alias":{}}'
            )

            detail_string = detail_string.replace(
                '"enable_time":1747130440', f'"enable_time":{storage_record_enable_timestamp}'
            )

            expected_rt_detail_router = {non_exist_es_table_id: detail_string}

            # 创建流程,先推送RT详情路由,再推送空间路由

            mock_hmset_to_redis.assert_has_calls(
                [
                    call("bkmonitorv3:spaces:result_table_detail", expected_rt_detail_router),
                    call("bkmonitorv3:spaces:space_to_result_table", expected_space_router),
                    call(
                        "bkmonitorv3:spaces:data_label_to_result_table",
                        {"bkdata_index_set_6788": '["2_bklog.test_es_non_exists"]'},
                    ),
                ]
            )

            mock_publish.assert_has_calls(
                [
                    call("bkmonitorv3:spaces:result_table_detail:channel", [non_exist_es_table_id]),
                    call("bkmonitorv3:spaces:space_to_result_table:channel", ["bkcc__2"]),
                    call("bkmonitorv3:spaces:data_label_to_result_table:channel", ["bkdata_index_set_6788"]),
                ]
            )

            es_storage_ins = models.ESStorage.objects.get(table_id=non_exist_es_table_id)
            assert es_storage_ins.index_set == "2_bklog_pure_es,2_bklog_es_log"
            assert es_storage_ins.storage_cluster_id == 3
            assert es_storage_ins.source_type == "bkdata"
            assert es_storage_ins.origin_table_id == non_exist_es_table_id

            result_table_ins = models.ResultTable.objects.get(table_id=non_exist_es_table_id)
            assert result_table_ins.data_label == "bkdata_index_set_6788"
            assert result_table_ins.default_storage == "elasticsearch"
            assert result_table_ins.bk_biz_id == 2

    # 空间路由推送 后台任务方式
    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            space_client = SpaceTableIDRedis()
            space_client.push_space_table_ids("bkcc", "2", is_publish=True)
            expected_space_router = {"bkcc__2": '{"2_bklog.test_es_non_exists":{"filters":[]}}'}

            mock_hmset_to_redis.assert_has_calls(
                [
                    call("bkmonitorv3:spaces:space_to_result_table", expected_space_router),
                ]
            )

            mock_publish.assert_has_calls(
                [
                    call("bkmonitorv3:spaces:space_to_result_table:channel", ["bkcc__2"]),
                ]
            )

    # 结果表详情路由推送 后台任务方式
    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            space_client = SpaceTableIDRedis()
            space_client.push_es_table_id_detail(table_id_list=[non_exist_es_table_id], is_publish=True)

            mock_hmset_to_redis.assert_has_calls(
                [
                    call("bkmonitorv3:spaces:result_table_detail", expected_rt_detail_router),
                ]
            )

            mock_publish.assert_has_calls(
                [
                    call("bkmonitorv3:spaces:result_table_detail:channel", [non_exist_es_table_id]),
                ]
            )

    modify_params = dict(
        space_type="bkcc",
        space_id="2",
        table_id=non_exist_es_table_id,
        data_label="bkdata_index_set_6788",
        index_set="2_bklog_pure_es",
        source_type="bkdata",
        storage_type="elasticsearch",
    )

    with patch("metadata.utils.redis_tools.RedisTools.hmset_to_redis") as mock_hmset_to_redis:
        with patch("metadata.utils.redis_tools.RedisTools.publish") as mock_publish:
            CreateOrUpdateLogRouter().request(**modify_params)

            detail_string = (
                '{"source_type":"bkdata","storage_id":3,"db":"2_bklog_pure_es",'
                '"measurement":"__default__","storage_type":"elasticsearch","options":{},'
                '"storage_cluster_records":[{"storage_id":3,"enable_time":1747130440}]}'
            )

            detail_string = detail_string.replace(
                '"enable_time":1747130440', f'"enable_time":{storage_record_enable_timestamp}'
            )

            expected_rt_detail_router = {non_exist_es_table_id: detail_string}

            # 创建流程,先推送RT详情路由,再推送空间路由
            mock_hmset_to_redis.assert_has_calls(
                [
                    call("bkmonitorv3:spaces:result_table_detail", expected_rt_detail_router),
                ]
            )

            mock_publish.assert_has_calls(
                [
                    call("bkmonitorv3:spaces:result_table_detail:channel", [non_exist_es_table_id]),
                ]
            )

            es_storage_ins = models.ESStorage.objects.get(table_id=non_exist_es_table_id)
            assert es_storage_ins.index_set == "2_bklog_pure_es"
            assert es_storage_ins.storage_cluster_id == 3
            assert es_storage_ins.source_type == "bkdata"

            result_table_ins = models.ResultTable.objects.get(table_id=non_exist_es_table_id)
            assert result_table_ins.data_label == "bkdata_index_set_6788"
            assert result_table_ins.default_storage == "elasticsearch"
            assert result_table_ins.bk_biz_id == 2
