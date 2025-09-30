# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import time

import mock
import pytest
from django.test import TestCase
from elasticsearch_dsl import AttrDict

from metadata import models
from monitor_web.models import CollectorPluginMeta
from packages.monitor_web.datalink.resources import (
    CollectingTargetStatusResource,
    QueryBizByBkBase,
)

pytestmark = pytest.mark.django_db

MOCKED_COLLECT_CONFIG = {
    "id": 41,
    "bk_biz_id": 22,
    "target_node_type": "INSTANCE",
    "target": [
        {
            "bk_host_id": 6,
            "display_name": "127.0.0.1",
            "bk_cloud_id": 0,
            "bk_cloud_name": "Default Area",
            "agent_status": "normal",
            "bk_os_type": "linux",
            "bk_supplier_id": "0",
            "is_external_ip": False,
            "is_innerip": True,
            "is_outerip": False,
            "ip": "127.0.0.1",
        }
    ],
}

MOCKED_SEARCH_POINT_STR = str(int(time.time()) // 60 * 60 - 60 * 2)

MOCKED_SEARCH_POINT = int(MOCKED_SEARCH_POINT_STR) * 1000

MOCKED_DSL_SEARCH_RESPONSE = AttrDict(
    {
        "aggs": {
            "init_alert": {"targets": {"buckets": [{"key": 6, "key_as_string": "6", "doc_count": 3}]}},
            "begin_time": {
                "targets": {
                    "buckets": [
                        {
                            "key": 6,
                            "key_as_string": "6",
                            "doc_count": 1,
                            "time": {
                                "buckets": [
                                    {
                                        "key": MOCKED_SEARCH_POINT,
                                        "key_as_string": MOCKED_SEARCH_POINT_STR,
                                        "doc_count": 1,
                                    }
                                ]
                            },
                        }
                    ]
                },
            },
            "end_time": {
                "end_alert": {
                    "targets": {
                        "buckets": [
                            {
                                "key": 6,
                                "key_as_string": "6",
                                "doc_count": 1,
                                "time": {
                                    "buckets": [
                                        {
                                            "key": MOCKED_SEARCH_POINT,
                                            "key_as_string": MOCKED_SEARCH_POINT_STR,
                                            "doc_count": 3,
                                        }
                                    ]
                                },
                            }
                        ]
                    }
                }
            },
        }
    }
)

DEFAULT_DATA_ID = 10000011
DEFAULT_DATA_ID_ONE = 10000012
DEFAULT_DATA_ID_TWO = 10000013
DEFAULT_DATA_ID_THREE = 10000014

DEFAULT_DATA_ID_NAME = "vm_test"
DEFAULT_DATA_ID_NAME_ONE = "10011_vm_test"
DEFAULT_DATA_ID_NAME_TWO = "vm_test_10011"
DEFAULT_DATA_ID_NAME_THREE = "vm_test_space"

DEFAULT_RT_ID = "test.demo"
DEFAULT_RT_ID_ONE = "test.demo1"
DEFAULT_RT_ID_TWO = "test.demo2"
DEFAULT_RT_ID_THREE = "script_vm_test.group2"

DEFAULT_BIZ_ID = 10011
DEFAULT_BIZ_ID_ONE = 0
DEFAULT_BIZ_ID_TWO = 0
DEFAULT_BIZ_ID_THREE = 0

DEFAULT_VM_DATA_ID = 100011
DEFAULT_VM_DATA_ID_ONE = 100012
DEFAULT_VM_DATA_ID_TWO = 100013
DEFAULT_VM_DATA_ID_THREE = 100014

DEFAULT_VM_RT_ID = "vm_test"
DEFAULT_VM_RT_ID_ONE = "vm_test1"
DEFAULT_VM_RT_ID_TWO = "vm_test2"
DEFAULT_VM_RT_ID_THREE = "10011_script_vm_test.group2"
COLLECTOR_PLUGIN_ID = "vm_test"


class TestResource(TestCase):
    def create_collect_config_meta(self):
        from monitor_web.models.collecting import (
            CollectConfigMeta,
            CollectorPluginMeta,
            DeploymentConfigVersion,
        )

        plugin_meta = CollectorPluginMeta.objects.create(plugin_id="plugin_01", bk_biz_id=2, plugin_type="Pushgateway")
        deployment_ver = DeploymentConfigVersion.objects.create(
            target_node_type="INSTANCE",
            plugin_version_id=1,
            config_meta_id=1,
        )
        self.collect_meta = CollectConfigMeta.objects.create(
            bk_biz_id=2,
            name="demo01",
            collect_type="Pushgateway",
            target_object_type="HOST",
            last_operation="CREATE",
            operation_result="SUCCESS",
            plugin=plugin_meta,
            deployment_config=deployment_ver,
        )

    def setUp(self) -> None:
        super().setUp()
        self.create_collect_config_meta()

    def tearDown(self) -> None:
        super().tearDown()

    def test_collector_status(self):
        from core.drf_resource import resource

        resource.collecting.collect_config_detail
        with mock.patch(
            "core.drf_resource.resource.collecting.collect_config_detail"
        ) as patch_collect_config_detail, mock.patch(
            "elasticsearch_dsl.search.Search.execute"
        ) as patch_dsl_search_execute:
            patch_collect_config_detail.return_value = MOCKED_COLLECT_CONFIG
            patch_dsl_search_execute.return_value = MOCKED_DSL_SEARCH_RESPONSE
            resource = CollectingTargetStatusResource()
            result = resource.request({"collect_config_id": self.collect_meta.id})
            print(MOCKED_SEARCH_POINT)
            print(result)
            assert result["target_info"]["target_node_type"] == "INSTANCE"
            assert len(result["target_info"]["table_data"]) == 1
            assert result["alert_histogram"][-1][1] == 1


@pytest.mark.django_db(databases=['default', 'monitor_api'])
class TestQueryBizByBkBase(TestCase):
    """
    测试根据计算平台相关信息反查业务信息
    """

    databases = {'default', 'monitor_api'}

    def create_test_data(self):
        models.DataSource.objects.create(
            bk_data_id=DEFAULT_DATA_ID,
            data_name=DEFAULT_DATA_ID_NAME,
            mq_cluster_id=1,
            mq_config_id=1,
            is_custom_source=True,
        )
        models.DataSource.objects.create(
            bk_data_id=DEFAULT_DATA_ID_ONE,
            data_name=DEFAULT_DATA_ID_NAME_ONE,
            mq_cluster_id=1,
            mq_config_id=1,
            is_custom_source=True,
        )
        models.DataSource.objects.create(
            bk_data_id=DEFAULT_DATA_ID_TWO,
            data_name=DEFAULT_DATA_ID_NAME_TWO,
            mq_cluster_id=1,
            mq_config_id=1,
            is_custom_source=True,
        )
        models.DataSource.objects.create(
            bk_data_id=DEFAULT_DATA_ID_THREE,
            data_name=DEFAULT_DATA_ID_NAME_THREE,
            mq_cluster_id=1,
            mq_config_id=1,
            is_custom_source=True,
        )

        models.DataSourceResultTable.objects.create(bk_data_id=DEFAULT_DATA_ID, table_id=DEFAULT_RT_ID)
        models.DataSourceResultTable.objects.create(bk_data_id=DEFAULT_DATA_ID_ONE, table_id=DEFAULT_RT_ID_ONE)
        models.DataSourceResultTable.objects.create(bk_data_id=DEFAULT_DATA_ID_TWO, table_id=DEFAULT_RT_ID_TWO)
        models.DataSourceResultTable.objects.create(bk_data_id=DEFAULT_DATA_ID_THREE, table_id=DEFAULT_RT_ID_THREE)

        models.ResultTable.objects.create(table_id=DEFAULT_RT_ID, bk_biz_id=DEFAULT_BIZ_ID, is_custom_table=True)
        models.ResultTable.objects.create(
            table_id=DEFAULT_RT_ID_ONE, bk_biz_id=DEFAULT_BIZ_ID_ONE, is_custom_table=True
        )
        models.ResultTable.objects.create(
            table_id=DEFAULT_RT_ID_TWO, bk_biz_id=DEFAULT_BIZ_ID_TWO, is_custom_table=True
        )
        models.ResultTable.objects.create(
            table_id=DEFAULT_RT_ID_THREE, bk_biz_id=DEFAULT_BIZ_ID_THREE, is_custom_table=True
        )

        models.AccessVMRecord.objects.create(
            result_table_id=DEFAULT_RT_ID, bk_base_data_id=DEFAULT_VM_DATA_ID, vm_result_table_id=DEFAULT_VM_RT_ID
        )
        models.AccessVMRecord.objects.create(
            result_table_id=DEFAULT_RT_ID_ONE,
            bk_base_data_id=DEFAULT_VM_DATA_ID_ONE,
            vm_result_table_id=DEFAULT_VM_RT_ID_ONE,
        )
        models.AccessVMRecord.objects.create(
            result_table_id=DEFAULT_RT_ID_TWO,
            bk_base_data_id=DEFAULT_VM_DATA_ID_TWO,
            vm_result_table_id=DEFAULT_VM_RT_ID_TWO,
        )
        models.AccessVMRecord.objects.create(
            result_table_id=DEFAULT_RT_ID_THREE,
            bk_base_data_id=DEFAULT_VM_DATA_ID_THREE,
            vm_result_table_id=DEFAULT_VM_RT_ID_THREE,
        )

        models.EventGroup.objects.create(
            table_id=DEFAULT_RT_ID_TWO,
            bk_data_id=DEFAULT_DATA_ID_TWO,
            bk_biz_id=DEFAULT_BIZ_ID_TWO,
        )
        models.TimeSeriesGroup.objects.create(
            table_id=DEFAULT_RT_ID_ONE,
            bk_data_id=DEFAULT_DATA_ID_ONE,
            bk_biz_id=DEFAULT_BIZ_ID_ONE,
        )
        models.Space.objects.create(
            space_type_id="bkcc",
            space_id=DEFAULT_BIZ_ID_ONE,
            space_name="test_demo",
        )
        CollectorPluginMeta.objects.create(
            plugin_type="script",
            plugin_id=COLLECTOR_PLUGIN_ID,
            bk_biz_id=DEFAULT_BIZ_ID,
        )

    def setUp(self) -> None:
        super().setUp()
        self.create_test_data()

    def tearDown(self) -> None:
        super().tearDown()

    def test_query_biz_by_bk_base_params_error(self):
        with pytest.raises(ValueError):
            QueryBizByBkBase().request()

    def test_query_biz_by_bk_base_with_vm_table_id(self):
        params = {"bk_base_vm_table_id_list": [DEFAULT_VM_RT_ID]}
        resp = QueryBizByBkBase().request(params)
        assert resp[DEFAULT_VM_DATA_ID] == DEFAULT_BIZ_ID

        # 测试为 0 业务，并且在 ts group 中场景
        params = {"bk_base_vm_table_id_list": [DEFAULT_VM_RT_ID_ONE]}
        resp = QueryBizByBkBase().request(params)
        assert resp[DEFAULT_VM_DATA_ID_ONE] == int(DEFAULT_DATA_ID_NAME_ONE.split("_")[0])

        # 测试为 0 业务，并且在 event group 中场景
        params = {"bk_base_vm_table_id_list": [DEFAULT_VM_RT_ID_TWO]}
        resp = QueryBizByBkBase().request(params)
        assert resp[DEFAULT_VM_DATA_ID_TWO] == int(DEFAULT_DATA_ID_NAME_TWO.split("_")[-1])

        # 测试为 0 业务，并且在 CollectorPluginMeta 中场景
        params = {"bk_base_vm_table_id_list": [DEFAULT_VM_RT_ID_THREE]}
        resp = QueryBizByBkBase().request(params)
        assert resp[DEFAULT_VM_DATA_ID_THREE] == DEFAULT_BIZ_ID

        # 包含五个场景
        params = {
            "bk_base_vm_table_id_list": [
                DEFAULT_VM_RT_ID,
                DEFAULT_VM_RT_ID_ONE,
                DEFAULT_VM_RT_ID_TWO,
                DEFAULT_VM_RT_ID_THREE,
            ]
        }
        resp = QueryBizByBkBase().request(params)
        assert len(resp) == 4
        assert resp[DEFAULT_VM_DATA_ID] == DEFAULT_BIZ_ID
        assert resp[DEFAULT_VM_DATA_ID_ONE] == int(DEFAULT_DATA_ID_NAME_ONE.split("_")[0])
        assert resp[DEFAULT_VM_DATA_ID_TWO] == int(DEFAULT_DATA_ID_NAME_TWO.split("_")[-1])
        assert resp[DEFAULT_VM_DATA_ID_THREE] == DEFAULT_BIZ_ID

    def test_query_biz_by_bk_base_with_vm_data_id(self):
        params = {"bk_base_data_id_list": [DEFAULT_VM_DATA_ID]}
        resp = QueryBizByBkBase().request(params)
        assert resp[DEFAULT_VM_DATA_ID] == DEFAULT_BIZ_ID

        # 测试为 0 业务，并且在 ts group 中场景
        params = {"bk_base_data_id_list": [DEFAULT_VM_DATA_ID_ONE]}
        resp = QueryBizByBkBase().request(params)
        assert resp[DEFAULT_VM_DATA_ID_ONE] == int(DEFAULT_DATA_ID_NAME_ONE.split("_")[0])

        # 测试为 0 业务，并且在 event group 中场景
        params = {"bk_base_data_id_list": [DEFAULT_VM_DATA_ID_TWO]}
        resp = QueryBizByBkBase().request(params)
        assert resp[DEFAULT_VM_DATA_ID_TWO] == int(DEFAULT_DATA_ID_NAME_TWO.split("_")[-1])

        # 包含三个场景
        params = {"bk_base_data_id_list": [DEFAULT_VM_DATA_ID, DEFAULT_VM_DATA_ID_ONE, DEFAULT_VM_DATA_ID_TWO]}
        resp = QueryBizByBkBase().request(params)
        assert len(resp) == 3
        assert resp[DEFAULT_VM_DATA_ID] == DEFAULT_BIZ_ID
        assert resp[DEFAULT_VM_DATA_ID_ONE] == int(DEFAULT_DATA_ID_NAME_ONE.split("_")[0])
        assert resp[DEFAULT_VM_DATA_ID_TWO] == int(DEFAULT_DATA_ID_NAME_TWO.split("_")[-1])

    def test_query_biz_by_bk_base_with_error_id(self):
        params = {"bk_base_data_id_list": [123123123123]}
        resp = QueryBizByBkBase().request(params)
        assert len(resp) == 0
