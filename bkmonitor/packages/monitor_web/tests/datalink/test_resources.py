# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import time

import mock
from attrdict import AttrDict
from django.test import TestCase

from packages.monitor_web.datalink.resources import CollectingTargetStatusResource

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
