"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import sys
from contextlib import nullcontext
from copy import deepcopy
from types import ModuleType, SimpleNamespace

import pytest
from django.http import QueryDict
from rest_framework.exceptions import ValidationError

from kernel_api.resource import alert


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


def test_merge_nested_dict_preserves_omitted_fields_and_replaces_arrays():
    result = alert.merge_nested_dict(
        {
            "template_detail": {
                "url": "https://old.example.com",
                "headers": [{"key": "Authorization", "value": "old"}],
                "authorize": {"auth_type": "none"},
            },
            "timeout": 600,
        },
        {
            "template_detail": {
                "url": "https://new.example.com",
                "headers": [],
            }
        },
    )

    assert result == {
        "template_detail": {
            "url": "https://new.example.com",
            "headers": [],
            "authorize": {"auth_type": "none"},
        },
        "timeout": 600,
    }


def test_normalize_strategy_metric_ids_preserves_special_id_until_query_changes():
    current_config = {
        "items": [
            {
                "query_configs": [
                    {
                        "id": 20,
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "result_table_id": "system.proc_port",
                        "metric_field": "proc_exists",
                        "metric_id": "bk_monitor.proc_port",
                    }
                ]
            }
        ]
    }
    request_data = deepcopy(current_config)

    alert.normalize_strategy_metric_ids(request_data, current_config)
    assert request_data["items"][0]["query_configs"][0]["metric_id"] == "bk_monitor.proc_port"

    query_config = request_data["items"][0]["query_configs"][0]
    query_config.update(
        {
            "data_source_label": "prometheus",
            "data_type_label": "time_series",
            "promql": "avg(cpu_usage)",
        }
    )
    alert.normalize_strategy_metric_ids(request_data, current_config)
    assert query_config["metric_id"] == "avg(cpu_usage)"


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


def test_update_alarm_strategy_requires_complete_config():
    serializer = alert.UpdateAlarmStrategyResource.RequestSerializer(
        data={
            "bk_biz_id": 2,
            "ids": [1],
            "edit_data": {"algorithms": []},
            "confirm": True,
        }
    )

    assert not serializer.is_valid()
    assert {"id", "name", "scenario", "items", "detects", "notice", "actions"} <= set(serializer.errors)


def test_update_alarm_strategy_uses_full_save(monkeypatch):
    captured = {}
    request_data = {
        "bk_biz_id": 2,
        "id": 1,
        "name": "CPU 使用率高",
        "type": "monitor",
        "source": "bkmonitorv3",
        "scenario": "os",
        "is_enabled": True,
        "is_invalid": False,
        "invalid_type": "",
        "items": [
            {
                "id": 10,
                "query_configs": [
                    {
                        "id": 20,
                        "data_source_label": "prometheus",
                        "data_type_label": "time_series",
                        "metric_id": "old_query",
                        "promql": "avg(cpu_usage)",
                    }
                ],
            }
        ],
        "detects": [{"id": 30}],
        "notice": {"user_groups": []},
        "actions": [],
        "labels": [],
        "app": "",
        "path": "",
        "priority": None,
        "priority_group_key": "",
        "metric_type": "time_series",
        "issue_config": None,
        "update_time": "2026-07-21 18:00:00+0800",
        "config_version": "version-1",
        "confirm": True,
    }
    fake_resource = SimpleNamespace(
        strategies=SimpleNamespace(
            save_strategy_v2=SimpleNamespace(request=lambda **kwargs: captured.update(kwargs) or {"id": kwargs["id"]})
        )
    )
    monkeypatch.setattr(alert, "resource", fake_resource)
    monkeypatch.setattr(alert, "ensure_strategy_relations_belong_to_biz", lambda _bk_biz_id, _data: None)
    monkeypatch.setattr(alert.transaction, "atomic", lambda: nullcontext())
    monkeypatch.setattr(alert, "get_strategy_config_version", lambda _value: "version-1")
    current_strategy_config = {
        "items": [
            {
                "query_configs": [
                    {
                        "id": 20,
                        "data_source_label": "prometheus",
                        "data_type_label": "time_series",
                        "metric_id": "old_query",
                        "promql": "old_query",
                    }
                ]
            }
        ]
    }
    current_strategy_obj = SimpleNamespace(
        restore=lambda: None,
        to_dict=lambda convert_dashboard: current_strategy_config,
    )
    monkeypatch.setattr(
        alert.Strategy,
        "from_models",
        lambda _models: [current_strategy_obj],
    )
    monkeypatch.setattr(
        alert,
        "StrategyModel",
        SimpleNamespace(
            DoesNotExist=type("DoesNotExist", (Exception,), {}),
            objects=SimpleNamespace(
                select_for_update=lambda: SimpleNamespace(get=lambda **_kwargs: SimpleNamespace(update_time=object()))
            ),
        ),
    )

    serializer = alert.UpdateAlarmStrategyResource.RequestSerializer(data=request_data)
    assert serializer.is_valid(), serializer.errors
    result = alert.UpdateAlarmStrategyResource().perform_request(serializer.validated_data)

    assert result == {"id": 1}
    assert captured["items"][0]["query_configs"][0]["promql"] == "avg(cpu_usage)"
    assert captured["items"][0]["query_configs"][0]["metric_id"] == "avg(cpu_usage)"
    assert "confirm" not in captured
    assert "edit_data" not in captured


def test_update_alarm_strategy_rejects_stale_snapshot(monkeypatch):
    monkeypatch.setattr(alert.transaction, "atomic", lambda: nullcontext())
    monkeypatch.setattr(alert, "get_strategy_config_version", lambda _value: "new-version")
    monkeypatch.setattr(
        alert,
        "StrategyModel",
        SimpleNamespace(
            DoesNotExist=type("DoesNotExist", (Exception,), {}),
            objects=SimpleNamespace(
                select_for_update=lambda: SimpleNamespace(get=lambda **_kwargs: SimpleNamespace(update_time=object()))
            ),
        ),
    )

    with pytest.raises(ValidationError, match="重新调用 get_alarm_strategy"):
        alert.UpdateAlarmStrategyResource().perform_request(
            {
                "bk_biz_id": 2,
                "id": 1,
                "items": [
                    {
                        "query_configs": [
                            {
                                "data_source_label": "prometheus",
                                "data_type_label": "time_series",
                                "promql": "avg(cpu_usage)",
                            }
                        ]
                    }
                ],
                "update_time": "old-update-time",
                "config_version": "old-version",
                "confirm": True,
            }
        )


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


def test_ensure_duty_rules_belong_to_current_or_public_biz(monkeypatch):
    class FakeQuerySet:
        def values_list(self, *_args, **_kwargs):
            return [1, 2]

    class FakeManager:
        def filter(self, **kwargs):
            assert kwargs["bk_biz_id__in"] == [0, 2]
            return FakeQuerySet()

    monkeypatch.setattr(alert, "DutyRule", SimpleNamespace(objects=FakeManager()))

    alert.ensure_duty_rules_belong_to_biz(2, [1, 2])
    with pytest.raises(ValidationError):
        alert.ensure_duty_rules_belong_to_biz(2, [1, 3])


def test_get_alarm_strategy_honors_convert_dashboard(monkeypatch):
    class FakeQuerySet:
        def filter(self, **_kwargs):
            return self

        def count(self):
            return 1

        def first(self):
            return SimpleNamespace(id=1)

    fake_strategy = SimpleNamespace(
        update_time=object(),
        restore=lambda: None,
        to_dict=lambda convert_dashboard: {
            "convert_dashboard": convert_dashboard,
            "actions": [],
            "notice": {},
        },
    )
    monkeypatch.setattr(alert, "StrategyModel", SimpleNamespace(objects=FakeQuerySet()))
    monkeypatch.setattr(alert.Strategy, "from_models", lambda _models: [fake_strategy])
    monkeypatch.setattr(alert, "get_strategy_config_version", lambda _value: "version-1")

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
    assert result["config_version"] == "version-1"


def test_update_action_config_merges_nested_config_and_preserves_plugin(monkeypatch):
    captured = {}
    current_config = {
        "id": 9,
        "bk_biz_id": 2,
        "name": "HTTP callback",
        "desc": "",
        "plugin_id": 2,
        "is_enabled": True,
        "execute_config": {
            "template_detail": {
                "method": "POST",
                "url": "https://old.example.com",
                "headers": [{"key": "Authorization", "value": "token"}],
                "authorize": {"auth_type": "none"},
            },
            "timeout": 600,
        },
    }

    class FakeGetActionConfigResource:
        def request(self, **_kwargs):
            return current_config

    class FakeEditActionConfigResource:
        def request(self, **kwargs):
            captured.update(kwargs)
            return kwargs

    fake_module = ModuleType("kernel_api.views.v4.action_config")
    fake_module.GetActionConfigResource = FakeGetActionConfigResource
    fake_module.EditActionConfigResource = FakeEditActionConfigResource
    monkeypatch.setitem(sys.modules, "kernel_api.views.v4.action_config", fake_module)

    request_data = {
        "bk_biz_id": 2,
        "id": 9,
        "name": "HTTP callback",
        "desc": "updated",
        "execute_config": {
            "template_detail": {"url": "https://new.example.com"},
            "timeout": 600,
        },
        "is_enabled": False,
        "confirm": True,
    }
    serializer = alert.UpdateMCPActionConfigResource.RequestSerializer(data=request_data)
    assert serializer.is_valid(), serializer.errors

    alert.UpdateMCPActionConfigResource().perform_request(serializer.validated_data)

    assert captured["plugin_id"] == 2
    assert captured["is_enabled"] is False
    assert captured["execute_config"]["template_detail"] == {
        "method": "POST",
        "url": "https://new.example.com",
        "headers": [{"key": "Authorization", "value": "token"}],
        "authorize": {"auth_type": "none"},
    }


def test_update_action_config_rejects_plugin_change(monkeypatch):
    class FakeGetActionConfigResource:
        def request(self, **_kwargs):
            return {
                "id": 9,
                "bk_biz_id": 2,
                "plugin_id": 2,
                "execute_config": {"template_detail": {}, "timeout": 600},
            }

    fake_module = ModuleType("kernel_api.views.v4.action_config")
    fake_module.GetActionConfigResource = FakeGetActionConfigResource
    fake_module.EditActionConfigResource = SimpleNamespace
    monkeypatch.setitem(sys.modules, "kernel_api.views.v4.action_config", fake_module)

    with pytest.raises(ValidationError):
        alert.UpdateMCPActionConfigResource().perform_request(
            {
                "bk_biz_id": 2,
                "id": 9,
                "name": "HTTP callback",
                "desc": "",
                "plugin_id": 3,
                "execute_config": {"template_detail": {}, "timeout": 600},
                "is_enabled": True,
                "confirm": True,
            }
        )


def test_search_alarm_shields_filters_source_without_changing_backend_serializer(monkeypatch):
    captured = {}

    class FakeQuerySet:
        def filter(self, **_kwargs):
            return self

        def values_list(self, *_args, **_kwargs):
            return [11, 12]

    fake_resource = SimpleNamespace(
        shield=SimpleNamespace(
            shield_list=SimpleNamespace(
                request=lambda **kwargs: captured.update(kwargs)
                or {"count": 2, "shield_list": [{"id": 11}, {"id": 12}]}
            )
        )
    )
    monkeypatch.setattr(alert, "resource", fake_resource)
    monkeypatch.setattr(alert, "Shield", SimpleNamespace(objects=FakeQuerySet()))

    result = alert.SearchAlarmShieldsResource().perform_request({"bk_biz_id": 2, "source": "mcp"})

    assert result["count"] == 2
    assert "source" not in captured
    assert {"key": "id", "value": [11, 12]} in captured["conditions"]
