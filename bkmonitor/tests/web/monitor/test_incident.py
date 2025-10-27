"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from monitor_web.incident.metrics.resources import IncidentMetricsSearchResource
from monitor_web.incident.events.resources import IncidentEventsSearchResource
from django.test import TestCase


class TestIncidentMetric(TestCase):
    """
    测试故障的指标相关接口
    """

    def test_incident_metric_search_by_node(self):
        """
        测试指标搜索接口(IncidentMetricsSearchResource)
        """
        data = {
            "bk_biz_id": 1,
            "bk_data_id": 1,
            "metric_type": "node",
            "index_info": {
                "index_type": "entity",
                "entity_type": "BcsPod",
                "entity_name": "test",
                "is_anomaly": True,
            },
            "start_time": 1718035200,
            "end_time": 1718038800,
        }
        print(data)
        inst = IncidentMetricsSearchResource().request(data)
        # # 断言返回的数据是一个列表
        # self.assertIsNotNone(inst)
        print("Metric Search Result:\n\n", inst)

    def test_incident_metric_search_by_edge(self):
        """
        测试指标搜索接口(IncidentMetricsSearchResource)
        """
        data = {
            "bk_biz_id": 1,
            "metric_type": "ebpf_call",
            "index_info": {
                "index_type": "edge",  # 节点类型，需要带节点类型和节点name
                "source_type": "BcsPod",
                "source_name": "test",
                "target_type": "APMService",
                "target_name": "test",
                "is_anomaly": False,
            },
            "start_time": 1749124917,
            "end_time": 1749128517,
        }

        print(data)
        inst = IncidentMetricsSearchResource().request(data)
        # # 断言返回的数据是一个列表
        # self.assertIsNotNone(inst)
        print("Metric Search Result:\n\n", inst)


class TestIncidentEvent(TestCase):
    """
    测试故障的事件相关接口
    """

    def test_incident_event_search_by_node(self):
        """
        测试事件搜索接口(IncidentEventsSearchResource)
        """
        data = {
            "bk_biz_id": 1,
            "metric_name": "apm.error_count",
            "index_info": {
                "index_type": "entity",
                "entity_type": "BcsPod",
                "entity_name": "test",
                "is_anomaly": True,
            },
            "start_time": 1749124917,
            "end_time": 1749128517,
        }

        inst = IncidentEventsSearchResource().request(data)
        # 添加一个基本的断言，确保返回的实例不是None
        self.assertIsNotNone(inst)
        print("Event Search Result:\n\n", inst)

    def test_incident_event_search_by_edge(self):
        data = {
            "bk_biz_id": 1,
            "metric_name": "ebpf_call",
            "index_info": {
                "index_type": "edge",
                "source_type": "BcsPod",
                "source_name": "test",
                "target_type": "APMService",
                "target_name": "test",
                "is_anomaly": False,
            },
            "start_time": 1749124917,
            "end_time": 1749128517,
        }
        inst = IncidentEventsSearchResource().request(data)
        self.assertIsNotNone(inst)
        print("Event Search Result:\n\n", inst)
