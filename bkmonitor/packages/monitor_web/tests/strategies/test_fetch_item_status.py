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
from collections import defaultdict

from monitor_web.strategies.resources.public import FetchItemStatus

from core.drf_resource import resource


class TestFetchItemStatus:
    def test_transform_target_to_dsl(self):
        actual = FetchItemStatus.transform_target_to_dsl({})
        assert actual is None

        target = {
            "bcs_cluster_id": "BCS-K8S-00000",
            "namespace": "thanos",
            "pod_name": "prometheus-po-kube-prometheus-stack-prometheus-0",
        }
        dsl = FetchItemStatus.transform_target_to_dsl(target)
        actual = dsl.to_dict()
        expect = {
            'bool': {
                'must': [
                    {
                        'nested': {
                            'path': 'event.tags',
                            'query': {
                                'bool': {
                                    'must': [
                                        {'term': {'event.tags.key': {'value': 'bcs_cluster_id'}}},
                                        {'match_phrase': {'event.tags.value': {'query': 'BCS-K8S-00000'}}},
                                    ]
                                }
                            },
                        }
                    },
                    {
                        'nested': {
                            'path': 'event.tags',
                            'query': {
                                'bool': {
                                    'must': [
                                        {'term': {'event.tags.key': {'value': 'namespace'}}},
                                        {'match_phrase': {'event.tags.value': {'query': 'thanos'}}},
                                    ]
                                }
                            },
                        }
                    },
                    {
                        'nested': {
                            'path': 'event.tags',
                            'query': {
                                'bool': {
                                    'must': [
                                        {'term': {'event.tags.key': {'value': 'pod_name'}}},
                                        {
                                            'match_phrase': {
                                                'event.tags.value': {
                                                    'query': 'prometheus-po-kube-prometheus-stack-prometheus-0'
                                                }
                                            }
                                        },
                                    ]
                                }
                            },
                        }
                    },
                ]
            }
        }
        assert actual == expect

    def test_perform_request(self, monkeypatch):
        def mock_return(_, validated_request_data):
            if not validated_request_data.get("target"):
                return {40449: 22, 40454: 3, 40552: 2, 55686: 1, 55691: 1, 56469: 1}
            else:
                target = validated_request_data.get("target")
                if target["bcs_cluster_id"] == "BCS-K8S-00000":
                    return {55691: 1}
                else:
                    return {}

        monkeypatch.setattr(FetchItemStatus, "get_alarm_event_num", mock_return)

        monkeypatch.setattr(
            FetchItemStatus,
            "get_strategy_numbers",
            lambda _, bk_biz_id, metric_ids: defaultdict(
                list, {'bk_monitor..container_cpu_usage_seconds_total': [55686, 55691]}
            ),
        )

        # 无target
        params = {"metric_ids": ["bk_monitor..container_cpu_usage_seconds_total"], "bk_biz_id": 2}
        actual = resource.strategies.fetch_item_status(params)
        expect = {
            'bk_monitor..container_cpu_usage_seconds_total': {'alert_number': 2, 'status': 2, 'strategy_number': 2}
        }
        assert actual == expect

        # BCS资源匹配
        params = {
            "metric_ids": ["bk_monitor..container_cpu_usage_seconds_total"],
            "target": {
                "bcs_cluster_id": "BCS-K8S-00000",
                "namespace": "thanos",
                "pod_name": "prometheus-po-kube-prometheus-stack-prometheus-0",
            },
            "bk_biz_id": 2,
        }
        actual = resource.strategies.fetch_item_status(params)
        expect = {
            'bk_monitor..container_cpu_usage_seconds_total': {'alert_number': 1, 'status': 2, 'strategy_number': 2}
        }
        assert actual == expect

        # BCS资源不匹配
        params = {
            "metric_ids": ["bk_monitor..container_cpu_usage_seconds_total"],
            "target": {
                "bcs_cluster_id": "BCS-K8S-00001",
                "namespace": "thanos",
                "pod_name": "prometheus-po-kube-prometheus-stack-prometheus-0",
            },
            "bk_biz_id": 2,
        }
        actual = resource.strategies.fetch_item_status(params)
        expect = {
            'bk_monitor..container_cpu_usage_seconds_total': {'alert_number': 0, 'status': 1, 'strategy_number': 2}
        }
        assert actual == expect
