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
from unittest.mock import MagicMock, patch

from elasticsearch_dsl import Search

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
            "bool": {
                "must": [
                    {
                        "nested": {
                            "path": "event.tags",
                            "query": {
                                "bool": {
                                    "must": [
                                        {"term": {"event.tags.key": {"value": "bcs_cluster_id"}}},
                                        {"match_phrase": {"event.tags.value": {"query": "BCS-K8S-00000"}}},
                                    ]
                                }
                            },
                        }
                    },
                    {
                        "nested": {
                            "path": "event.tags",
                            "query": {
                                "bool": {
                                    "must": [
                                        {"term": {"event.tags.key": {"value": "namespace"}}},
                                        {"match_phrase": {"event.tags.value": {"query": "thanos"}}},
                                    ]
                                }
                            },
                        }
                    },
                    {
                        "nested": {
                            "path": "event.tags",
                            "query": {
                                "bool": {
                                    "must": [
                                        {"term": {"event.tags.key": {"value": "pod_name"}}},
                                        {
                                            "match_phrase": {
                                                "event.tags.value": {
                                                    "query": "prometheus-po-kube-prometheus-stack-prometheus-0"
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
        def mock_return(cls, validated_request_data):
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
            lambda cls, bk_biz_id, metric_ids, labels: defaultdict(
                list, {"bk_monitor..container_cpu_usage_seconds_total": [55686, 55691]}
            ),
        )

        # 无target
        params = {"metric_ids": ["bk_monitor..container_cpu_usage_seconds_total"], "bk_biz_id": 2}
        actual = resource.strategies.fetch_item_status(params)
        expect = {
            "bk_monitor..container_cpu_usage_seconds_total": {"alert_number": 2, "status": 2, "strategy_number": 2}
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
            "bk_monitor..container_cpu_usage_seconds_total": {"alert_number": 1, "status": 2, "strategy_number": 2}
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
            "bk_monitor..container_cpu_usage_seconds_total": {"alert_number": 0, "status": 1, "strategy_number": 2}
        }
        assert actual == expect

    def test_add_labels_query(self):
        """测试基于策略标签过滤告警的功能"""

        search_object = Search()
        labels = ["APM-APP(trpc_demo)", "APM-SERVICE(example.greeter)"]
        result = FetchItemStatus.add_labels_query(search_object, labels)

        actual = result.to_dict()
        expect = {"query": {"bool": {"filter": [{"terms": {"labels": labels}}]}}}
        assert actual == expect

    def test_filter_strategy_ids_by_labels(self):
        """测试按标签过滤策略 ID 的 AND 语义"""

        # 空标签直接返回空集合
        assert FetchItemStatus._filter_strategy_ids_by_labels(bk_biz_id=2, labels=[]) == set()

        # 多标签 AND 语义：策略 100 同时关联两个标签，策略 200 只关联第一个
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.values_list.return_value = [
            (100, "/APM-APP(demo)/"),
            (200, "/APM-APP(demo)/"),
            (100, "/APM-SERVICE(svc)/"),
        ]

        with patch("monitor_web.strategies.resources.public.StrategyLabel.objects") as mock_objects:
            mock_objects.filter.return_value = mock_qs
            result = FetchItemStatus._filter_strategy_ids_by_labels(
                bk_biz_id=2, labels=["APM-APP(demo)", "APM-SERVICE(svc)"]
            )

        assert result == {100}

    def test_get_strategy_numbers_routing(self):
        """测试 get_strategy_numbers 的路由分发逻辑"""

        # metric_ids 为空时走标签路径
        with patch.object(FetchItemStatus, "_filter_strategy_ids_by_labels", return_value={100}):
            result = FetchItemStatus.get_strategy_numbers(bk_biz_id=2, metric_ids=[], labels=["APM-APP(demo)"])
        assert result == {FetchItemStatus.LABEL_ASSOCIATE_KEY: [100]}

        # metric_ids 和 labels 都为空时返回空字典
        result = FetchItemStatus.get_strategy_numbers(bk_biz_id=2, metric_ids=[], labels=[])
        assert result == {}

    def test_build_labels_response(self):
        """测试按标签关联的汇总响应构建"""

        strategy_numbers = {FetchItemStatus.LABEL_ASSOCIATE_KEY: [100, 200, 300]}
        strategy_alert_num = {100: 5, 200: 0, 300: 3}
        result = FetchItemStatus._build_labels_response(strategy_numbers, strategy_alert_num)
        assert result == {"strategy_count": 3, "alert_count": 8}

        # 空策略映射
        assert FetchItemStatus._build_labels_response({}, {}) == {"strategy_count": 0, "alert_count": 0}

    def test_build_metrics_response(self):
        """测试按指标关联的响应构建"""

        strategy_numbers = {"metric_a": [100, 200]}
        strategy_alert_num = {100: 3, 200: 0}

        result = FetchItemStatus._build_metrics_response(strategy_numbers, strategy_alert_num, ["metric_a", "metric_b"])
        # 有告警 -> status=2
        assert result["metric_a"] == {"status": 2, "alert_number": 3, "strategy_number": 2}
        # 未配置策略 -> status=0
        assert result["metric_b"] == {"status": 0, "alert_number": 0, "strategy_number": 0}

    def test_perform_request_with_labels(self, monkeypatch):
        """测试 metric_ids 为空、labels 非空时的汇总响应路径"""

        monkeypatch.setattr(FetchItemStatus, "get_alarm_event_num", lambda cls, data: {100: 5, 200: 0, 300: 3})
        monkeypatch.setattr(
            FetchItemStatus,
            "get_strategy_numbers",
            lambda cls, bk_biz_id, metric_ids, labels: {FetchItemStatus.LABEL_ASSOCIATE_KEY: [100, 200, 300]},
        )

        params = {"bk_biz_id": 2, "metric_ids": [], "labels": ["APM-APP(demo)", "APM-SERVICE(svc)"]}
        actual = resource.strategies.fetch_item_status(params)
        assert actual == {"strategy_count": 3, "alert_count": 8}
