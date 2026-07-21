"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace

import pytest
from django.http import QueryDict
from rest_framework.exceptions import ValidationError

from kernel_api.resource import alert
from monitor_web.shield.resources.backend_resources import ShieldListSerializer
from monitor_web.shield.serializers import StrategySerializer as StrategyShieldSerializer
from monitor_web.strategies.resources.v2 import UpdatePartialStrategyV2Resource


def test_business_scoped_serializer_preserves_backend_fields():
    serializer = alert.BusinessScopedSerializer(
        data={"bk_biz_id": "2", "conditions": [{"key": "strategy_status", "value": ["ON"]}]}
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data == {
        "bk_biz_id": 2,
        "conditions": [{"key": "strategy_status", "value": ["ON"]}],
    }


def test_confirmed_serializer_requires_true():
    serializer = alert.ConfirmedBusinessScopedSerializer(data={"bk_biz_id": 2, "confirm": False})

    assert not serializer.is_valid()
    assert "confirm" in serializer.errors


def test_get_alarm_strategy_condition_requires_value_list():
    serializer = alert.GetAlarmStrategyResource.RequestSerializer(
        data={
            "bk_biz_id": 2,
            "conditions": [{"key": "strategy_id", "value": 1}],
        }
    )

    assert not serializer.is_valid()
    assert "conditions" in serializer.errors


def test_pass_through_serializer_flattens_get_query_params():
    serializer = alert.BusinessScopedSerializer(data=QueryDict("bk_biz_id=2&page=3&order=-id"))

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data == {"bk_biz_id": 2, "page": "3", "order": "-id"}


def test_build_strategy_from_simplified_request():
    result = alert.build_strategy_from_simplified_request(
        {
            "bk_biz_id": 2,
            "name": "CPU 使用率高",
            "scenario": "os",
            "metric": {
                "name": "CPU 使用率",
                "data_source_label": "bk_monitor",
                "data_type_label": "time_series",
                "result_table_id": "system.cpu_summary",
                "metric_field": "usage",
                "unit": "percent",
            },
            "detect": {
                "level": 2,
                "algorithm_type": "Threshold",
                "method": "gt",
                "threshold": 80,
                "trigger_count": 5,
                "check_window": 5,
            },
            "notice_group_ids": [1],
            "action_config_ids": [3],
        }
    )

    assert result["items"][0]["query_configs"][0]["alias"] == "a"
    assert result["items"][0]["algorithms"][0]["config"] == [[{"method": "gt", "threshold": 80}]]
    assert result["detects"][0]["trigger_config"] == {"count": 5, "check_window": 5}
    assert result["notice"]["user_groups"] == [1]
    assert result["actions"][0]["config_id"] == 3
    assert "metric" not in result
    assert "detect" not in result


def test_get_alarm_strategy_returns_candidates_when_not_unique(monkeypatch):
    class FakeQuerySet(list):
        def filter(self, **kwargs):
            strategies = self
            for key, value in kwargs.items():
                if key == "id__in":
                    strategies = [strategy for strategy in strategies if strategy.id in value]
                elif key == "name__in":
                    strategies = [strategy for strategy in strategies if strategy.name in value]
                else:
                    strategies = [strategy for strategy in strategies if getattr(strategy, key) == value]
            return FakeQuerySet(strategies)

        def count(self):
            return len(self)

        def order_by(self, *_args):
            return self

    strategies = FakeQuerySet(
        [
            SimpleNamespace(
                id=1,
                name="CPU",
                bk_biz_id=2,
                scenario="os",
                is_enabled=True,
                update_time=None,
            ),
            SimpleNamespace(
                id=2,
                name="CPU-2",
                bk_biz_id=2,
                scenario="os",
                is_enabled=False,
                update_time=None,
            ),
        ]
    )
    monkeypatch.setattr(alert, "StrategyModel", SimpleNamespace(objects=strategies))

    result = alert.GetAlarmStrategyResource().perform_request(
        {"bk_biz_id": 2, "conditions": [{"key": "strategy_name", "value": ["CPU", "CPU-2"]}]}
    )

    assert result["total"] == 2
    assert result["candidates"] == [
        {
            "id": 1,
            "name": "CPU",
            "bk_biz_id": 2,
            "scenario": "os",
            "is_enabled": True,
            "update_time": None,
        },
        {
            "id": 2,
            "name": "CPU-2",
            "bk_biz_id": 2,
            "scenario": "os",
            "is_enabled": False,
            "update_time": None,
        },
    ]


def test_ensure_shield_belongs_to_biz_rejects_cross_biz(monkeypatch):
    fake_resource = SimpleNamespace(
        shield=SimpleNamespace(
            shield_detail=SimpleNamespace(request=lambda **kwargs: {"id": kwargs["id"], "bk_biz_id": 3}),
        )
    )
    monkeypatch.setattr(alert, "resource", fake_resource)

    with pytest.raises(ValidationError):
        alert.ensure_shield_belongs_to_biz(2, 10)


def test_strategy_snapshot_rejects_cross_biz(monkeypatch):
    monkeypatch.setattr(
        alert.AlertDocument,
        "get",
        lambda _id: SimpleNamespace(event=SimpleNamespace(bk_biz_id=3)),
    )

    with pytest.raises(ValidationError):
        alert.ListStrategySnapshotResource().perform_request({"bk_biz_id": 2, "id": 10})


def test_alert_related_resource_checks_biz_and_strips_auth_param(monkeypatch):
    captured = {}

    class FakeBackendResource:
        def request(self, **kwargs):
            captured.update(kwargs)
            return {"ok": True}

    monkeypatch.setattr(
        alert.AlertDocument,
        "get",
        lambda _id: SimpleNamespace(event=SimpleNamespace(bk_biz_id=2)),
    )
    resource_instance = alert.ListAlertEventsResource()
    resource_instance.backend_resource_class = FakeBackendResource

    result = resource_instance.perform_request({"bk_biz_id": 2, "alert_id": "alert-1", "limit": 5})

    assert result == {"ok": True}
    assert captured == {"alert_id": "alert-1", "limit": 5}


def test_create_alarm_shield_defaults_one_time_cycle():
    serializer = alert.CreateAlarmShieldResource.RequestSerializer(
        data={
            "bk_biz_id": 2,
            "category": "strategy",
            "begin_time": "2026-07-20 20:00:00",
            "end_time": "2026-07-20 21:00:00",
            "shield_notice": False,
            "dimension_config": {"id": [1]},
            "confirm": True,
        }
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["cycle_config"]["type"] == 1


@pytest.mark.parametrize(
    "category,dimension_config",
    [
        ("scope", {"scope_type": "unknown", "target": [1]}),
        ("scope", {"scope_type": "ip", "target": []}),
        ("scope", {"scope_type": "ip", "target": [{"ip": "127.0.0.1"}]}),
        ("scope", {"scope_type": "dynamic_group", "target": [{}]}),
        ("scope", {"scope_type": "instance", "target": [0]}),
        ("dimension", {"dimension_conditions": []}),
    ],
)
def test_create_alarm_shield_rejects_unsafe_targets(category, dimension_config):
    serializer = alert.CreateAlarmShieldResource.RequestSerializer(
        data={
            "bk_biz_id": 2,
            "category": category,
            "begin_time": "2026-07-20 20:00:00",
            "end_time": "2026-07-20 21:00:00",
            "shield_notice": False,
            "dimension_config": dimension_config,
            "confirm": True,
        }
    )

    assert not serializer.is_valid()
    assert any(field.startswith("dimension_config") for field in serializer.errors)


def test_create_alarm_shield_requires_complete_notice_config():
    serializer = alert.CreateAlarmShieldResource.RequestSerializer(
        data={
            "bk_biz_id": 2,
            "category": "strategy",
            "begin_time": "2026-07-20 20:00:00",
            "end_time": "2026-07-20 21:00:00",
            "shield_notice": True,
            "notice_config": {"notice_time": 5},
            "dimension_config": {"id": [1]},
            "confirm": True,
        }
    )

    assert not serializer.is_valid()
    assert "notice_config" in serializer.errors


def test_create_alert_shield_rejects_cross_biz(monkeypatch):
    monkeypatch.setattr(
        alert.AlertDocument,
        "get",
        lambda _id: SimpleNamespace(event=SimpleNamespace(bk_biz_id=3)),
    )

    with pytest.raises(ValidationError):
        alert.CreateAlarmShieldResource().perform_request(
            {
                "bk_biz_id": 2,
                "category": "alert",
                "dimension_config": {"alert_ids": ["alert-1"]},
                "confirm": True,
            }
        )


def test_create_alert_shield_rejects_two_id_forms():
    with pytest.raises(ValidationError):
        alert.CreateAlarmShieldResource().perform_request(
            {
                "bk_biz_id": 2,
                "category": "alert",
                "dimension_config": {"alert_id": "alert-1", "alert_ids": ["alert-2"]},
                "confirm": True,
            }
        )


def test_normalize_shield_notice_config_converts_stored_receivers():
    result = alert.normalize_shield_notice_config(
        {
            "notice_time": 5,
            "notice_way": ["weixin"],
            "notice_receiver": ["user#alice", {"type": "group", "id": "bk_biz_maintainer"}],
        }
    )

    assert result["notice_receiver"] == [
        {"type": "user", "id": "alice"},
        {"type": "group", "id": "bk_biz_maintainer"},
    ]


def test_strategy_relation_validation_rejects_non_list_actions():
    with pytest.raises(ValidationError):
        alert.ensure_strategy_relations_belong_to_biz(2, {"actions": True})


@pytest.mark.parametrize("action_count", [0, 2])
def test_update_notice_group_list_updates_all_relations(action_count):
    actions = [SimpleNamespace(user_groups=[], instance=SimpleNamespace(id=index + 1)) for index in range(action_count)]
    notice = SimpleNamespace(user_groups=[], instance=SimpleNamespace(id=100))
    strategy = SimpleNamespace(actions=actions, notice=notice)

    _, fields, relations = UpdatePartialStrategyV2Resource.update_notice_group_list(strategy, [7, 8])

    assert fields == ["user_groups"]
    assert [relation.id for relation in relations] == [*range(1, action_count + 1), 100]
    assert all(action.user_groups == [7, 8] for action in actions)
    assert notice.user_groups == [7, 8]


def test_get_alarm_strategy_honors_convert_dashboard(monkeypatch):
    class FakeQuerySet:
        def filter(self, **_kwargs):
            return self

        def count(self):
            return 1

        def first(self):
            return SimpleNamespace(id=1)

    fake_strategy = SimpleNamespace(
        restore=lambda: None,
        to_dict=lambda convert_dashboard: {
            "convert_dashboard": convert_dashboard,
            "actions": [],
            "notice": {},
        },
    )
    monkeypatch.setattr(alert, "StrategyModel", SimpleNamespace(objects=FakeQuerySet()))
    monkeypatch.setattr(alert.Strategy, "from_models", lambda _models: [fake_strategy])

    result = alert.GetAlarmStrategyResource().perform_request(
        {
            "bk_biz_id": 2,
            "conditions": [{"key": "strategy_id", "value": ["1"]}],
            "with_user_group": False,
            "with_user_group_detail": False,
            "convert_dashboard": False,
        }
    )

    assert result["convert_dashboard"] is False


def test_shield_serializers_preserve_source():
    list_serializer = ShieldListSerializer(data={"bk_biz_id": 2, "source": "mcp"})
    create_serializer = StrategyShieldSerializer(
        data={
            "bk_biz_id": 2,
            "category": "strategy",
            "begin_time": "2026-07-20 20:00:00",
            "end_time": "2026-07-20 21:00:00",
            "dimension_config": {"id": [1]},
            "shield_notice": False,
            "source": "mcp",
        }
    )

    assert list_serializer.is_valid(), list_serializer.errors
    assert create_serializer.is_valid(), create_serializer.errors
    assert list_serializer.validated_data["source"] == "mcp"
    assert create_serializer.validated_data["source"] == "mcp"
