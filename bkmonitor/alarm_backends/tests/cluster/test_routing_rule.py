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

from alarm_backends.cluster.define import ConditionMatcher, RoutingRule, TrueMatcher


class TestRoutingRule:
    def test_true_matcher(self):
        m = TrueMatcher()
        assert m.match("anything")

    def test_condition_matcher(self):
        m = ConditionMatcher([{"method": "eq", "value": "1"}])
        assert m.match(1)
        assert not m.match("2")

        m = ConditionMatcher([{"method": "eq", "value": ["1", 2]}])
        assert m.match(1)
        assert m.match("2")
        assert not m.match("3")

        m = ConditionMatcher([{"method": "gt", "value": ["1"]}, {"method": "lte", "value": ["3"]}])
        assert not m.match(1)
        assert m.match(2)
        assert m.match(2.5)
        assert m.match(3)
        assert not m.match(4)

        m = ConditionMatcher([{"method": "gt", "value": ["10"]}, {"condition": "or", "method": "lt", "value": [0]}])
        assert not m.match(1)
        assert m.match(11)
        assert m.match(-1)

    def test_match(self):
        routing_rule = RoutingRule(
            cluster_name="test",
            target_type="biz",
            matcher_type="true",
            matcher_config={},
        )
        assert routing_rule.match("anything")

        routing_rule = RoutingRule(
            cluster_name="test",
            target_type="biz",
            matcher_type="condition",
            matcher_config=[{"method": "eq", "value": "1"}],
        )
        assert routing_rule.match(1)
        assert not routing_rule.match(2)
