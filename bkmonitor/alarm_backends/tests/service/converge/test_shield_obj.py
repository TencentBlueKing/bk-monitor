"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from datetime import datetime, timedelta

import pytest

from alarm_backends.service.converge.shield.shield_obj import ShieldObj
from bkmonitor.utils.shield import BaseShieldDisplayManager, format_dimension_conditions_display

pytestmark = pytest.mark.django_db

STRATEGY_ID = 100
CLUSTER_ID = "BCS-K8S-00000"
NAMESPACE = "ns-live"
OTHER_NAMESPACE = "ns-other"
POD_A = "pod-a"
POD_B = "pod-b"


def _quick_alert_config(dimension_config, is_quick=True):
    return {
        "id": 1,
        "category": "alert",
        "is_quick": is_quick,
        "scope_type": "",
        "cycle_config": {},
        "begin_time": datetime.now(),
        "end_time": datetime.now() + timedelta(days=1),
        "dimension_config": dimension_config,
    }


def _stock_dimension_config(conditions):
    """存量快捷屏蔽：conditions + 被误写入的实例维。"""
    return {
        "strategy_id": STRATEGY_ID,
        "tags.bcs_cluster_id": CLUSTER_ID,
        "tags.namespace": NAMESPACE,
        "tags.pod": POD_A,
        "tags.workload_kind": "Deployment",
        "ip": "10.0.0.1",
        "bk_host_id": 1,
        "dimension_conditions": conditions,
        "_dimensions": "pod({}) - ip(10.0.0.1)".format(POD_A),
        "_alert_id": "1",
        "_severity": 1,
    }


def _alert_data(namespace=NAMESPACE, pod=POD_B, strategy_id=STRATEGY_ID):
    return {
        "strategy_id": strategy_id,
        "tags.bcs_cluster_id": CLUSTER_ID,
        "tags.namespace": namespace,
        "tags.pod": pod,
        "ip": "10.0.0.2",
    }


class _DummyDisplayManager(BaseShieldDisplayManager):
    def get_service_name_list(self, bk_biz_id, service_instance_id_list):
        return []

    def get_node_path_list(self, bk_biz_id, bk_topo_node_list):
        return []

    def get_dynamic_group_name_list(self, bk_biz_id, dynamic_group_list):
        return []

    def get_business_name(self, bk_biz_id):
        return str(bk_biz_id)


class TestQuickAlertShieldMatch:
    def test_stock_conditions_same_namespace_different_pod_hits(self):
        config = _quick_alert_config(
            _stock_dimension_config(
                [
                    {"key": "tags.bcs_cluster_id", "value": [CLUSTER_ID], "method": "eq"},
                    {"key": "tags.namespace", "value": [NAMESPACE], "method": "eq"},
                ]
            )
        )
        shield_obj = ShieldObj(config)
        assert shield_obj.dimension_check.is_match(_alert_data(pod=POD_B)) is True

    def test_stock_conditions_mismatched_namespace_misses(self):
        config = _quick_alert_config(
            _stock_dimension_config(
                [
                    {"key": "tags.bcs_cluster_id", "value": [CLUSTER_ID], "method": "eq"},
                    {"key": "tags.namespace", "value": [NAMESPACE], "method": "eq"},
                ]
            )
        )
        shield_obj = ShieldObj(config)
        assert shield_obj.dimension_check.is_match(_alert_data(namespace=OTHER_NAMESPACE)) is False

    def test_reg_expands_match_range(self):
        config = _quick_alert_config(
            {
                "strategy_id": STRATEGY_ID,
                "dimension_conditions": [
                    {"key": "tags.namespace", "value": ["ns-.*"], "method": "reg"},
                ],
            }
        )
        shield_obj = ShieldObj(config)
        assert shield_obj.dimension_check.is_match(_alert_data(namespace="ns-live")) is True
        assert shield_obj.dimension_check.is_match(_alert_data(namespace="ns-other")) is True
        assert shield_obj.dimension_check.is_match(_alert_data(namespace="prod")) is False

    def test_pc_quick_without_conditions_keeps_raw_keys(self):
        config = _quick_alert_config(
            {
                "strategy_id": STRATEGY_ID,
                "tags.pod": POD_A,
                "_dimensions": "pod({})".format(POD_A),
            }
        )
        shield_obj = ShieldObj(config)
        assert shield_obj.dimension_check.is_match(_alert_data(pod=POD_A)) is True
        assert shield_obj.dimension_check.is_match(_alert_data(pod=POD_B)) is False


class TestShieldDisplay:
    def test_format_dimension_conditions_display(self):
        content = format_dimension_conditions_display(
            [
                {"key": "tags.namespace", "name": "namespace", "value": [NAMESPACE], "method": "eq"},
                {"key": "tags.pod", "name": "pod", "value": [POD_A], "method": "reg", "condition": "and"},
            ]
        )
        assert "namespace = {}".format(NAMESPACE) in content
        assert "pod reg {}".format(POD_A) in content
        assert "and" in content

    def test_alert_content_uses_conditions_not_raw_dimensions(self):
        manager = _DummyDisplayManager()
        content = manager.get_shield_content(
            {
                "bk_biz_id": 2,
                "category": "alert",
                "scope_type": "",
                "dimension_config": _stock_dimension_config(
                    [
                        {"key": "tags.namespace", "name": "namespace", "value": [NAMESPACE], "method": "eq"},
                    ]
                ),
            },
            strategy_id_to_name={STRATEGY_ID: "demo-strategy"},
        )
        assert NAMESPACE in content
        assert POD_A not in content
        assert "10.0.0.1" not in content
        assert "demo-strategy" in content

