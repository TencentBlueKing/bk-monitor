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
from alarm_backends.cluster.define import Cluster, RoutingRule, TargetType


class TestCluster:
    def test_match(self):
        routing_rules = [
            RoutingRule(
                cluster_name="test",
                target_type="biz",
                matcher_type="true",
                matcher_config={},
            ),
        ]
        cluster = Cluster(
            name="test",
            code=1,
            tags={},
            description="",
            routing_rules=routing_rules,
        )

        assert cluster.match(TargetType.biz, "anything")

        routing_rules = [
            RoutingRule(
                cluster_name="test1",
                target_type="biz",
                matcher_type="condition",
                matcher_config=[{"method": "eq", "value": "1"}],
            ),
            RoutingRule(
                cluster_name="test2",
                target_type="biz",
                matcher_type="true",
                matcher_config={},
            ),
        ]

        cluster1 = Cluster(
            name="test1",
            code=2,
            tags={},
            description="",
            routing_rules=routing_rules,
        )
        cluster2 = Cluster(
            name="test2",
            code=3,
            tags={},
            description="",
            routing_rules=routing_rules,
        )
        assert cluster1.match(TargetType.biz, 1)
        assert not cluster1.match(TargetType.biz, 2)
        assert cluster2.match(TargetType.biz, 2)
        assert not cluster2.match(TargetType.biz, 1)

    def test_filter(self):
        cluster = Cluster(
            name="test",
            tags={},
            code=1,
            description="",
            routing_rules=[
                RoutingRule(
                    cluster_name="test",
                    target_type="biz",
                    matcher_type="true",
                    matcher_config={},
                ),
            ],
        )

        assert cluster.filter(TargetType.biz, [1, 2, 3]) == [1, 2, 3]

        cluster = Cluster(
            name="test",
            tags={},
            code=1,
            description="",
            routing_rules=[
                RoutingRule(
                    cluster_name="test",
                    target_type="biz",
                    matcher_type="condition",
                    matcher_config=[{"method": "gt", "value": "1"}],
                ),
            ],
        )

        assert cluster.filter(TargetType.biz, [1, 2, 3]) == [2, 3]

    def test_get_targets_by_cluster(self):
        cluster = Cluster(
            name="test1",
            code=1,
            tags={},
            description="",
            routing_rules=[
                RoutingRule(
                    cluster_name="test1",
                    target_type="biz",
                    matcher_type="condition",
                    matcher_config=[{"method": "gt", "value": "10"}],
                ),
                RoutingRule(
                    cluster_name="test2",
                    target_type="biz",
                    matcher_type="condition",
                    matcher_config=[{"method": "lt", "value": "3"}],
                ),
                RoutingRule(
                    cluster_name="test3",
                    target_type="biz",
                    matcher_type="true",
                    matcher_config={},
                ),
            ],
        )

        assert cluster.get_targets_by_cluster(TargetType.biz, [1, 2, 3, 11, 12, 13]) == {
            "test1": [11, 12, 13],
            "test2": [1, 2],
            "test3": [3],
        }
