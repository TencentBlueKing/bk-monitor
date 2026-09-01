"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from monitor_web.shield.resources.backend_resources import AddShieldResource
from weixin.event.resources import QuickShield

pytestmark = pytest.mark.django_db

STRATEGY_ID = 100
CLUSTER_ID = "BCS-K8S-00000"
NAMESPACE = "ns-live"
POD_A = "pod-a"


class _FakeDimension:
    def __init__(self, key, value):
        self._data = {"key": key, "value": value, "display_key": key, "display_value": value}

    def to_dict(self):
        return self._data


def _fake_alert(dimensions=None):
    alert = MagicMock()
    alert.id = "12345"
    alert.strategy_id = STRATEGY_ID
    alert.severity = 1
    alert.event.description = "demo"
    if dimensions is None:
        dimensions = [
            _FakeDimension("tags.bcs_cluster_id", CLUSTER_ID),
            _FakeDimension("tags.namespace", NAMESPACE),
            _FakeDimension("tags.pod", POD_A),
            _FakeDimension("ip", "10.0.0.1"),
        ]
    alert.dimensions = dimensions
    return alert


def _event_params(**overrides):
    params = {
        "type": "event",
        "event_id": 12345,
        "bk_biz_id": 2,
        "end_time": datetime.now(),
        "description": "",
        "dimension_keys": None,
        "dimension_conditions": None,
    }
    params.update(overrides)
    return params


class TestHandleAlertWritePath:
    def test_conditions_do_not_copy_raw_dimensions(self):
        conditions = [
            {"key": "tags.namespace", "value": [NAMESPACE], "method": "eq"},
        ]
        with patch("monitor_web.shield.resources.backend_resources.AlertDocument") as alert_document:
            alert_document.get.return_value = _fake_alert()
            result = AddShieldResource.handle_alert(
                {
                    "dimension_config": {
                        "alert_id": "12345",
                        "dimension_conditions": conditions,
                    }
                }
            )
        assert result["dimension_conditions"] == conditions
        assert result["strategy_id"] == STRATEGY_ID
        assert "tags.pod" not in result
        assert "ip" not in result
        assert POD_A not in result["_dimensions"]
        assert NAMESPACE in result["_dimensions"]

    def test_dimension_keys_still_filter_raw_equals(self):
        with patch("monitor_web.shield.resources.backend_resources.AlertDocument") as alert_document:
            alert_document.get.return_value = _fake_alert()
            result = AddShieldResource.handle_alert(
                {
                    "dimension_keys": ["tags.namespace"],
                    "dimension_config": {"alert_id": "12345"},
                }
            )
        assert result["tags.namespace"] == NAMESPACE
        assert "tags.pod" not in result
        assert "dimension_conditions" not in result

    def test_without_keys_or_conditions_copies_all_dimensions(self):
        with patch("monitor_web.shield.resources.backend_resources.AlertDocument") as alert_document:
            alert_document.get.return_value = _fake_alert()
            result = AddShieldResource.handle_alert({"dimension_config": {"alert_id": "12345"}})
        assert result["tags.pod"] == POD_A
        assert result["ip"] == "10.0.0.1"
        assert "dimension_conditions" not in result


    def test_empty_keys_keep_strategy_id_only(self):
        with patch("monitor_web.shield.resources.backend_resources.AlertDocument") as alert_document:
            alert_document.get.return_value = _fake_alert()
            result = AddShieldResource.handle_alert(
                {
                    "dimension_keys": [],
                    "dimension_config": {"alert_id": "12345"},
                }
            )
        assert result["strategy_id"] == STRATEGY_ID
        assert "tags.pod" not in result
        assert "tags.namespace" not in result
        assert "ip" not in result
        assert "dimension_conditions" not in result
        assert [k for k in result if not str(k).startswith("_")] == ["strategy_id"]


def _assert_empty_event_stays_alert(params, alert):
    with (
        patch("weixin.event.resources.AlertDocument") as alert_document,
        patch("weixin.event.resources.resource.shield.add_shield") as add_shield,
    ):
        alert_document.get.return_value = alert
        add_shield.return_value = {"id": 1}
        QuickShield().perform_request(params)
    add_shield.assert_called_once()
    payload = add_shield.call_args[0][0]
    assert payload["category"] == "alert"
    assert payload["dimension_keys"] == []
    assert payload["dimension_config"]["alert_id"] == "12345"


class TestWeixinQuickShield:
    def test_event_empty_selection_with_dimensions_stays_alert(self):
        _assert_empty_event_stays_alert(_event_params(), _fake_alert())

    def test_event_empty_lists_with_dimensions_stays_alert(self):
        _assert_empty_event_stays_alert(_event_params(dimension_keys=[], dimension_conditions=[]), _fake_alert())

    def test_event_empty_alert_dimensions_none_keys_stays_alert(self):
        _assert_empty_event_stays_alert(_event_params(), _fake_alert(dimensions=[]))

    def test_event_empty_alert_dimensions_empty_lists_stays_alert(self):
        _assert_empty_event_stays_alert(
            _event_params(dimension_keys=[], dimension_conditions=[]), _fake_alert(dimensions=[])
        )

    def test_event_with_keys_stays_alert_category(self):
        with (
            patch("weixin.event.resources.AlertDocument") as alert_document,
            patch("weixin.event.resources.resource.shield.add_shield") as add_shield,
        ):
            alert_document.get.return_value = _fake_alert()
            add_shield.return_value = {"id": 1}
            QuickShield().perform_request(_event_params(dimension_keys=["tags.namespace"]))
        payload = add_shield.call_args[0][0]
        assert payload["category"] == "alert"
        assert payload["dimension_keys"] == ["tags.namespace"]
        assert payload["dimension_config"]["alert_id"] == "12345"

    def test_event_with_conditions_only_stays_alert_category(self):
        conditions = [{"key": "tags.namespace", "value": [NAMESPACE], "method": "eq"}]
        with (
            patch("weixin.event.resources.AlertDocument") as alert_document,
            patch("weixin.event.resources.resource.shield.add_shield") as add_shield,
        ):
            alert_document.get.return_value = _fake_alert()
            add_shield.return_value = {"id": 1}
            QuickShield().perform_request(_event_params(dimension_conditions=conditions))
        payload = add_shield.call_args[0][0]
        assert payload["category"] == "alert"
        assert payload["dimension_config"]["dimension_conditions"] == conditions
        assert payload["dimension_config"]["alert_id"] == "12345"
