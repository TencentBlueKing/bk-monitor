"""Synthetic contracts for confirmed, business-scoped strategy edits."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from rest_framework.exceptions import PermissionDenied, ValidationError

from bkmonitor.iam import ActionEnum
from bkmonitor.strategy.new_strategy import AbstractConfig, BaseActionRelation, Item, QueryConfig, Strategy
from core.drf_resource.exceptions import CustomException
from kernel_api.resource import alert
from kernel_api.resource.alert import get_strategy_config_version
from kernel_api.resource.bkm_cli import BkmCliOpCallResource
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry
from kernel_api.rpc.functions.bkm_cli import strategy_management as management
from kernel_api.rpc.functions.bkm_cli.platform_catalog import _authorization
from kernel_api.rpc.functions.bkm_cli.platform_catalog._catalog import ParamsGuardRejected


@pytest.fixture
def config():
    query = {
        "id": 20,
        "alias": "a",
        "data_source_label": "bk_log_search",
        "data_type_label": "log",
        "metric_id": "demo_metric",
        "query_string": "original",
        "index_set_id": 1,
        "result_table_id": "demo_index",
        "agg_interval": 60,
        "agg_dimension": ["service", "Stack"],
        "agg_condition": [],
        "time_field": "timestamp",
        "functions": [],
    }
    item = {
        "id": 10,
        "name": "demo",
        "expression": "a",
        "query_configs": [query],
        "algorithms": [
            {
                "id": 30,
                "type": "Threshold",
                "level": 2,
                "unit_prefix": "",
                "config": [[{"method": "gte", "threshold": 5}]],
            }
        ],
        "no_data_config": {"is_enabled": True, "continuous": 5},
        "target": [[]],
        "functions": [],
        "origin_sql": "",
        "metric_type": "log",
        "time_delay": 30,
        "access_lookback_periods": 12,
    }
    result = {
        "id": 1,
        "bk_biz_id": 2,
        "name": "demo strategy",
        "type": "monitor",
        "source": "bkmonitorv3",
        "scenario": "os",
        "items": [item],
        "detects": [{"id": 40, "level": 2}],
        "notice": {"id": 50, "user_groups": [1], "config": {"alarm_interval": 120}},
        "actions": [{"id": 60, "config_id": 1}],
        "is_enabled": False,
        "is_invalid": False,
        "invalid_type": "",
        "labels": ["demo"],
        "app": "",
        "path": "",
        "priority": 1,
        "priority_group_key": "PGK:demo",
        "metric_type": "log",
        "issue_config": None,
        "update_time": "2026-01-01 00:00:00+0000",
    }
    result["config_version"] = get_strategy_config_version(result)
    return result


@pytest.fixture
def request_data(config):
    return {
        "operation": "update",
        "confirmed": True,
        "operator": "alice",
        "bk_biz_id": 2,
        "strategy_id": 1,
        "config_version": config["config_version"],
        "items": [{"id": 10, "expression": "0<a<30"}],
    }


@pytest.fixture
def api(monkeypatch, config):
    model = SimpleNamespace(id=config["id"], bk_biz_id=config["bk_biz_id"])

    def load_target(**lookup):
        if lookup != {"id": config["id"], "bk_biz_id": config["bk_biz_id"]}:
            raise LookupError
        return model

    load = Mock(side_effect=load_target)
    snapshot = Mock(side_effect=lambda *, convert_dashboard: deepcopy(config))
    current = SimpleNamespace(restore=Mock(), to_dict=snapshot)
    read = Mock(return_value=[current])
    save = Mock(return_value={"id": 1})
    validate_save = Mock(side_effect=deepcopy)
    save_with_audit = Mock(side_effect=lambda params, **_kwargs: save(**params))
    authorize = Mock()
    normalize = Mock(wraps=alert.normalize_strategy_metric_ids)
    relations = Mock()
    preflight = Mock(wraps=alert._validate_strategy_before_write)
    monkeypatch.setattr(
        alert, "StrategyModel", SimpleNamespace(objects=SimpleNamespace(get=load), DoesNotExist=LookupError)
    )
    monkeypatch.setattr(alert.Strategy, "from_models", read)
    monkeypatch.setattr(
        alert,
        "resource",
        SimpleNamespace(
            strategies=SimpleNamespace(
                save_strategy_v2=SimpleNamespace(
                    request=save, validate_request_data=validate_save, perform_request=save_with_audit
                )
            )
        ),
    )
    monkeypatch.setattr(alert, "normalize_strategy_metric_ids", normalize)
    monkeypatch.setattr(alert, "ensure_strategy_relations_belong_to_biz", relations)
    monkeypatch.setattr(alert, "_validate_strategy_before_write", preflight)
    monkeypatch.setattr(management, "authorize_strategy_business", authorize)
    return SimpleNamespace(
        load=load,
        model=model,
        read=read,
        snapshot=snapshot,
        current=current,
        save=save,
        validate_save=validate_save,
        save_with_audit=save_with_audit,
        authorize=authorize,
        normalize=normalize,
        relations=relations,
        preflight=preflight,
    )


def test_registry_and_successful_bridge_audit(monkeypatch, request_data, api):
    op = BkmCliOpRegistry.resolve("manage-strategy-config")
    assert (op.capability_level, op.risk_level, op.requires_confirmation) == ("admin", "mutation", True)
    monkeypatch.setattr("kernel_api.resource.bkm_cli.inject_bk_tenant_id", lambda params: params)
    monkeypatch.setattr("kernel_api.resource.bkm_cli.request_context.get_request_username", lambda: "gateway-user")
    request_data["operator"] = " alice "
    result = BkmCliOpCallResource().perform_request({"op_id": op.op_id, "params": request_data})
    assert result["audit"]["declared_operator"] == "alice"
    assert result["audit"]["request_caller"] == "gateway-user"
    assert result["result"]["requested_operator"] == "alice"
    assert api.save_with_audit.call_args.kwargs == {"audit_operator": "alice"}
    api.validate_save.assert_called_once()
    api.load.assert_called_once_with(bk_biz_id=2, id=1)
    api.read.assert_called_once_with([api.model])
    api.current.restore.assert_called_once_with()
    api.snapshot.assert_called_once_with(convert_dashboard=False)


def test_three_supported_changes_preserve_every_other_field(config, request_data, api):
    original = deepcopy(config)
    patches = [
        {
            "id": 10,
            "expression": "0<a<30",
            "query_configs": [
                {
                    "id": 20,
                    "query_string": "error",
                    "agg_dimension": ["service"],
                    "agg_condition": [{"key": "service", "method": "eq", "value": ["demo"], "condition": "and"}],
                }
            ],
            "algorithms": [{"id": 30, "config": [[{"method": "gte", "threshold": 1}]]}],
        }
    ]
    request_data["items"] = patches
    management.manage_strategy_config(request_data)
    expected = deepcopy(original)
    item = expected["items"][0]
    item["expression"] = patches[0]["expression"]
    item["query_configs"][0].update(patches[0]["query_configs"][0])
    item["algorithms"][0]["config"] = patches[0]["algorithms"][0]["config"]
    api.save.assert_called_once_with(**expected)
    api.normalize.assert_called_once_with(expected, original)
    api.relations.assert_called_once_with(2, expected)
    api.preflight.assert_called_once_with(expected)
    assert config == original


@pytest.fixture
def create_request():
    return {
        "operation": "create",
        "bk_biz_id": 2,
        "confirmed": True,
        "operator": "alice",
        "config": {
            "name": "demo log strategy",
            "scenario": "os",
            "is_enabled": True,
            "items": [
                {
                    "name": "errors",
                    "expression": "a",
                    "functions": [],
                    "target": [],
                    "no_data_config": {"is_enabled": False},
                    "query_configs": [
                        {
                            "data_source_label": "bk_log_search",
                            "data_type_label": "log",
                            "alias": "a",
                            "index_set_id": 1,
                            "result_table_id": "",
                            "query_string": "example error",
                            "agg_interval": 60,
                            "agg_dimension": ["pod"],
                            "agg_condition": [],
                        }
                    ],
                    "algorithms": [{"type": "Threshold", "level": 2, "config": [[{"method": "gte", "threshold": 10}]]}],
                }
            ],
            "detects": [
                {"level": 2, "trigger_config": {"count": 2, "check_window": 3}, "recovery_config": {"check_window": 3}}
            ],
            "notice": {
                "user_groups": [1],
                "signal": ["abnormal", "recovered"],
                "options": {"converge_config": {"need_biz_converge": True}},
                "config": {
                    "need_poll": True,
                    "notify_interval": 600,
                    "interval_notify_mode": "standard",
                    "template": [
                        {"signal": "abnormal", "message_tmpl": "", "title_tmpl": ""},
                        {"signal": "recovered", "message_tmpl": "", "title_tmpl": ""},
                    ],
                },
            },
        },
    }


def test_create_reuses_platform_validation_relations_and_audit(create_request, api):
    original = deepcopy(create_request)
    api.save.return_value = {"id": 42, "name": create_request["config"]["name"]}
    result = management.manage_strategy_config(create_request)
    assert result["strategy_id"] == 42
    assert result["requested_operator"] == "alice"
    api.authorize.assert_called_once_with(create_request)
    api.relations.assert_called_once()
    api.validate_save.assert_called_once()
    api.save_with_audit.assert_called_once()
    assert api.save_with_audit.call_args.kwargs == {"audit_operator": "alice"}
    assert api.save_with_audit.call_args.args[0]["actions"] == []
    assert "confirm" not in api.save_with_audit.call_args.args[0]
    assert create_request == original


def test_create_accepts_function_identifiers_without_accepting_existing_record_ids(create_request, api):
    create_request["config"]["items"][0]["functions"] = [{"id": "abs", "params": []}]
    api.save.return_value = {"id": 42, "name": create_request["config"]["name"]}
    management.manage_strategy_config(create_request)
    assert api.save.call_args.kwargs["items"][0]["functions"] == [{"id": "abs", "params": []}]


@pytest.mark.parametrize(
    "path,value",
    [
        (("strategy_id",), 1),
        (("config", "id"), 0),
        (("config", "actions"), []),
        (("config", "bk_biz_id"), 3),
        (("config", "is_enabled"), None),
        (("config", "items", 0, "id"), 0),
        (("config", "items", 0, "query_configs", 0, "id"), 0),
        (("config", "items", 0, "query_configs", 0, "data_source_label"), "custom"),
        (("config", "items", 0, "query_configs", 0, "agg_interval"), -1),
        (("config", "items", 0, "algorithms", 0, "id"), 0),
        (("config", "items", 0, "algorithms", 0, "type"), "IntelligentDetect"),
        (("config", "detects", 0, "id"), 0),
        (("config", "detects", 0, "trigger_config", "typo"), None),
        (("config", "notice", "config_id"), 1),
        (("config", "notice", "user_groups"), []),
        (("config", "notice", "config", "typo"), None),
    ],
)
def test_invalid_creates_do_not_reach_save(create_request, api, path, value):
    target = create_request
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    with pytest.raises((CustomException, ValidationError)):
        management.manage_strategy_config(create_request)
    api.save.assert_not_called()


def test_create_checks_real_platform_serializer(create_request):
    config = {**create_request["config"], "bk_biz_id": 2, "actions": []}
    serializer = Strategy.Serializer(data=config)
    serializer.is_valid(raise_exception=True)
    assert serializer.validated_data["detects"][0]["trigger_config"] == {"count": 2, "check_window": 3}
    assert serializer.validated_data["notice"]["config"]["notify_interval"] == 600


def test_create_does_not_save_without_business_permission(monkeypatch, create_request, api):
    monkeypatch.setattr(management, "authorize_strategy_business", Mock(side_effect=PermissionDenied))
    with pytest.raises(PermissionDenied):
        management.manage_strategy_config(create_request)
    api.save.assert_not_called()


def test_create_audit_path_validates_before_persistence(create_request, api):
    api.validate_save.side_effect = ValidationError("invalid strategy")
    with pytest.raises(ValidationError, match="invalid strategy"):
        management.manage_strategy_config(create_request)
    api.save_with_audit.assert_not_called()
    api.save.assert_not_called()


def test_existing_create_resource_keeps_its_default_save_path(create_request, api):
    creator = alert.CreateAlarmStrategyResource()
    config = creator.validate_request_data({**create_request["config"], "bk_biz_id": 2, "confirm": True})
    creator.perform_request(config)
    api.save.assert_called_once()
    api.validate_save.assert_not_called()
    api.save_with_audit.assert_not_called()


@pytest.mark.parametrize(
    "update",
    [
        {"confirmed": False},
        {"confirmed": 1},
        {"operator": ""},
        {"operator": "<operator>"},
        {"operator": "a" * 33},
        {"operator": "a" * 129},
        {"unknown": None},
        {"is_enabled": True},
        {"operation": "create"},
        {"bk_biz_id": True},
        {"strategy_id": -1},
        {"config_version": "old"},
        {"items": []},
        {"items": [{"id": 10}]},
        {"items": [{"id": 10, "notice": None}]},
        {"items": [{"id": 10, "expression": "a"}, {"id": 10, "expression": "b"}]},
        {"items": [{"id": 10, "query_configs": [{"id": 20, "index_set_id": 2}]}]},
        {"items": [{"id": 10, "query_configs": [{"id": 20, "query_string": " "}]}]},
        {"items": [{"id": 10, "query_configs": [{"id": 20, "agg_dimension": ["x", "x"]}]}]},
        {
            "items": [
                {
                    "id": 10,
                    "query_configs": [{"id": 20, "agg_condition": [{"key": "x", "method": "eq", "value": [None]}]}],
                }
            ]
        },
    ],
)
def test_invalid_patch_rejected_before_permission_or_api(request_data, api, update):
    request_data.update(update)
    with pytest.raises(CustomException):
        management.manage_strategy_config(request_data)
    api.authorize.assert_not_called()
    api.load.assert_not_called()
    api.read.assert_not_called()
    api.save.assert_not_called()


def test_audit_operator_accepts_storage_length_boundary(request_data, api):
    request_data["operator"] = "a" * 32
    result = management.manage_strategy_config(request_data)
    assert result["requested_operator"] == request_data["operator"]
    assert api.save_with_audit.call_args.kwargs == {"audit_operator": request_data["operator"]}


def test_creation_scope_update_preserves_ids_and_unedited_configuration(config, request_data, api):
    request_data.pop("items")
    request_data["config"] = {
        "name": "log backlog",
        "is_enabled": True,
        "items": [
            {"id": 10, "query_configs": [{"id": 20, "agg_interval": 600}], "algorithms": [{"id": 30, "level": 1}]}
        ],
        "detects": [
            {
                "id": 40,
                "level": 1,
                "trigger_config": {"count": 3, "check_window": 3},
                "recovery_config": {"check_window": 2},
            }
        ],
        "notice": {"config": {"notify_interval": 7200}},
    }
    original = deepcopy(config)
    management.manage_strategy_config(request_data)
    saved = api.save.call_args.kwargs
    assert saved["is_enabled"] is True
    assert saved["name"] == "log backlog"
    assert saved["items"][0]["query_configs"][0]["agg_interval"] == 600
    assert saved["items"][0]["algorithms"][0]["level"] == saved["detects"][0]["level"] == 1
    assert saved["detects"][0]["trigger_config"] == {"count": 3, "check_window": 3}
    assert saved["detects"][0]["recovery_config"]["check_window"] == 2
    assert saved["notice"]["config"]["notify_interval"] == 7200
    for field in ("actions", "labels", "priority_group_key"):
        assert saved[field] == original[field]
    for field in ("id", "time_delay", "access_lookback_periods", "no_data_config"):
        assert saved["items"][0][field] == original["items"][0][field]
    assert saved["notice"]["id"] == original["notice"]["id"]
    assert saved["notice"]["user_groups"] == original["notice"]["user_groups"]
    assert config == original
    api.save.assert_called_once()


def test_disable_only_preserves_every_other_field(config, request_data, api):
    request_data.pop("items")
    config["is_enabled"] = True
    request_data["config_version"] = get_strategy_config_version(config)
    request_data["config"] = {"is_enabled": False}
    management.manage_strategy_config(request_data)
    saved = api.save.call_args.kwargs
    assert saved["is_enabled"] is False
    for field in ("items", "detects", "notice", "actions"):
        assert saved[field] == config[field]


@pytest.mark.parametrize(
    "patch",
    [
        {},
        {"is_enabled": "false"},
        {"actions": []},
        {"items": [{"id": 10, "query_configs": [{"agg_interval": 600}]}]},
        {"detects": [{"id": 40, "trigger_config": {"unexpected": 3}}]},
        {"detects": [{"id": 40, "level": 1}, {"id": 40, "level": 2}]},
        {"notice": {"config_id": 60}},
    ],
)
def test_invalid_config_patch_fails_before_authorization(request_data, api, patch):
    request_data.pop("items")
    request_data["config"] = patch
    with pytest.raises(CustomException):
        management.manage_strategy_config(request_data)
    api.authorize.assert_not_called()
    api.save.assert_not_called()


@pytest.mark.parametrize(
    "patch",
    [
        {"items": [{"id": 999, "name": "foreign"}]},
        {"items": [{"id": 10, "query_configs": [{"id": 999, "agg_interval": 600}]}]},
        {"items": [{"id": 10, "algorithms": [{"id": 999, "level": 1}]}]},
        {"detects": [{"id": 999, "level": 1}]},
    ],
)
def test_config_patch_rejects_foreign_nested_records(request_data, api, patch):
    request_data.pop("items")
    request_data["config"] = patch
    with pytest.raises(CustomException, match="ID 不属于"):
        management.manage_strategy_config(request_data)
    api.save.assert_not_called()


def test_creation_scope_update_keeps_version_check_and_single_write(request_data, api):
    request_data.pop("items")
    request_data["config"] = {"is_enabled": False}
    version = request_data["config_version"]
    request_data["config_version"] = "f" * 64
    with pytest.raises(ValidationError):
        management.manage_strategy_config(request_data)
    api.save.assert_not_called()
    request_data["config_version"] = version
    api.save.side_effect = TimeoutError("unknown write outcome")
    with pytest.raises(TimeoutError):
        management.manage_strategy_config(request_data)
    api.save.assert_called_once()


def test_audit_save_still_validates_before_persistence(request_data, api):
    api.validate_save.side_effect = ValidationError("invalid strategy")
    with pytest.raises(ValidationError, match="invalid strategy"):
        management.manage_strategy_config(request_data)
    api.save_with_audit.assert_not_called()
    api.save.assert_not_called()


@pytest.mark.parametrize(
    "items",
    [
        [{"id": 999, "expression": "b"}],
        [{"id": 10, "query_configs": [{"id": 999, "query_string": "b"}]}],
        [{"id": 10, "algorithms": [{"id": 999, "config": [[{"method": "gt", "threshold": 1}]]}]}],
    ],
)
def test_foreign_objects_rejected(request_data, api, items):
    request_data["items"] = items
    with pytest.raises(CustomException, match="ID 不属于"):
        management.manage_strategy_config(request_data)
    api.save.assert_not_called()


def test_stale_version_and_wrong_business_rejected(request_data, config, api):
    request_data["config_version"] = "f" * 64
    with pytest.raises(ValidationError, match="重新调用 get_alarm_strategy"):
        management.manage_strategy_config(request_data)
    request_data["config_version"] = config["config_version"]
    config["bk_biz_id"] = 3
    with pytest.raises(ValidationError, match="不存在"):
        management.manage_strategy_config(request_data)
    api.save.assert_not_called()


def test_query_field_not_supported_by_current_source_is_rejected(config, request_data, api):
    query = config["items"][0]["query_configs"][0]
    query.update(data_source_label="prometheus", data_type_label="time_series")
    request_data["config_version"] = get_strategy_config_version(config)
    request_data["items"] = [{"id": 10, "query_configs": [{"id": 20, "query_string": "error"}]}]
    with pytest.raises(CustomException, match="不支持的参数.*query_string"):
        management.manage_strategy_config(request_data)
    api.save.assert_not_called()


def test_legacy_patch_validates_the_existing_non_threshold_algorithm(config, request_data, api):
    config["items"][0]["algorithms"][0]["type"] = "NewSeries"
    config["items"][0]["algorithms"][0]["config"] = {"detect_range": 600}
    request_data["config_version"] = get_strategy_config_version(config)
    request_data["items"] = [{"id": 10, "algorithms": [{"id": 30, "config": {"detect_range": 900}}]}]
    management.manage_strategy_config(request_data)
    algorithm = api.save.call_args.kwargs["items"][0]["algorithms"][0]
    assert algorithm["type"] == "NewSeries"
    assert algorithm["config"]["detect_range"] == algorithm["config"]["effective_delay"] == 900


def test_legacy_algorithm_unknown_config_fields_are_rejected(config, request_data, api):
    request_data["items"] = [
        {"id": 10, "algorithms": [{"id": 30, "config": [[{"method": "gt", "threshold": 1, "extra": None}]]}]}
    ]
    with pytest.raises(CustomException, match="extra"):
        management.manage_strategy_config(request_data)
    api.save.assert_not_called()


def test_non_editable_strategy_rejected(config, request_data, api):
    config["edit_allowed"] = False
    request_data["config_version"] = get_strategy_config_version(config)
    with pytest.raises(CustomException, match="不允许编辑"):
        management.manage_strategy_config(request_data)
    api.save.assert_not_called()


def test_save_timeout_is_not_retried(request_data, api):
    api.save.side_effect = TimeoutError("unknown write outcome")
    with pytest.raises(TimeoutError):
        management.manage_strategy_config(request_data)
    assert api.save.call_count == 1


@pytest.fixture
def principal(monkeypatch):
    request = SimpleNamespace(
        user=SimpleNamespace(is_authenticated=True, username="gateway-user", tenant_id="system"),
        META={},
        jwt=SimpleNamespace(app=SimpleNamespace(app_code="demo-app")),
    )
    monkeypatch.setattr(management, "get_request", lambda **_kwargs: request)
    monkeypatch.setattr(_authorization, "get_request", lambda **_kwargs: request)
    monkeypatch.setattr(_authorization, "bk_biz_id_to_bk_tenant_id", lambda _value: "system")
    monkeypatch.setattr(_authorization, "is_match_api_token", lambda *_args: True)
    permission = Mock(skip_check=True)
    permission.is_allowed.return_value = True
    factory = Mock(return_value=permission)
    monkeypatch.setattr(management, "Permission", factory)
    return request, factory, permission


def test_authorization_uses_principal_and_target_business(principal):
    request, factory, permission = principal
    management.authorize_strategy_business({"bk_biz_id": 2, "operator": "alice"})
    factory.assert_called_once_with(username="gateway-user", bk_tenant_id="system")
    assert permission.skip_check is False
    action, resources = permission.is_allowed.call_args.args
    assert action == ActionEnum.MANAGE_RULE
    assert resources[0].id == "2"
    assert not hasattr(request, "biz_id")


@pytest.mark.parametrize("kind", ["iam", "tenant", "application", "token", "expired", "missing"])
def test_business_authorization_fail_closed(monkeypatch, principal, kind):
    request, factory, permission = principal
    params = {"bk_biz_id": 2}
    if kind == "iam":
        permission.is_allowed.return_value = False
    elif kind == "tenant":
        params["bk_tenant_id"] = "another"
    elif kind == "application":

        def deny_target(scoped_request, tenant, app_code):
            assert (scoped_request.biz_id, tenant, app_code) == (2, "system", "demo-app")
            return False

        monkeypatch.setattr(_authorization, "is_match_api_token", deny_target)
    elif kind in ("token", "expired"):
        request.META["HTTP_AUTHORIZATION"] = "Bearer synthetic-token"
        record = SimpleNamespace(is_expired=lambda: kind == "expired", is_allowed_namespace=lambda _: False)
        monkeypatch.setattr(
            _authorization.ApiAuthToken.objects, "filter", lambda **_: SimpleNamespace(first=lambda: record)
        )
    else:
        request.user.is_authenticated = False
    with pytest.raises((PermissionDenied, ParamsGuardRejected)):
        management.authorize_strategy_business(params)
    if kind not in ("iam",):
        permission.is_allowed.assert_not_called()


@pytest.mark.parametrize(
    "config_ids,expected,deleted",
    [
        ([2, 1], [2, 1], []),
        ([0, 0], [1, 2], []),
        ([0, 2], [1, 2], []),
        ([2], [2], [1]),
        ([0, 0, 0], [1, 2, 0], []),
        ([99, 1], [2, 1], []),
    ],
)
def test_full_save_reuses_explicit_identity_and_legacy_positions(config_ids, expected, deleted):
    configs = [SimpleNamespace(id=object_id) for object_id in config_ids]
    model = Mock()
    config_class = Mock()
    AbstractConfig.reuse_exists_records(
        model,
        [SimpleNamespace(id=1), SimpleNamespace(id=2)],
        configs,
        config_class,
    )
    assert [config.id for config in configs] == expected
    if deleted:
        model.objects.filter.assert_called_once_with(id__in=deleted)
        config_class.delete_useless.assert_called_once_with(deleted)
    else:
        model.objects.filter.assert_not_called()


def test_item_and_query_serializer_round_trip(config):
    original = config["items"][0]
    patches = [
        {
            "id": 10,
            "expression": "0<a<30",
            "query_configs": [{"id": 20, "query_string": "error", "agg_dimension": ["service"], "agg_condition": []}],
        }
    ]
    management._merge_items(config, patches)
    validated = Item.Serializer().run_validation(original)
    restored = Item(strategy_id=1, **validated).to_dict()
    assert restored["id"] == original["id"]
    assert restored["expression"] == "0<a<30"
    assert restored["no_data_config"] == original["no_data_config"]
    query = restored["query_configs"][0]
    assert query == QueryConfig(strategy_id=1, item_id=10, **original["query_configs"][0]).to_dict()
    assert query["agg_dimension"] == ["service"]
    assert query["query_string"] == "error"
    assert restored["algorithms"] == original["algorithms"]


@pytest.mark.parametrize("relation_id", [None, 60])
def test_relation_serializer_preserves_identity_and_recipient_role(relation_id):
    relation = {
        "id": relation_id,
        "config_id": 1,
        "user_type": "follower",
        "user_groups": [1],
        "signal": [],
        "options": {"converge_config": {}},
    }
    validated = BaseActionRelation.Serializer().run_validation(relation)
    restored = BaseActionRelation(strategy_id=1, **validated).to_dict()
    for key in ("id", "config_id", "user_type", "user_groups", "signal"):
        assert restored[key] == relation[key]


def test_detail_version_is_canonical_before_diagnostic_enrichment(monkeypatch, config):
    from kernel_api.rpc.functions.bkm_cli import strategy

    canonical = deepcopy(config)
    canonical.pop("config_version")
    version = get_strategy_config_version(canonical)
    strategy_obj = SimpleNamespace(restore=lambda: None, to_dict=lambda *, convert_dashboard: deepcopy(canonical))
    monkeypatch.setattr(strategy.Strategy, "from_models", lambda _: [strategy_obj])
    monkeypatch.setattr(
        strategy,
        "_inject_strategy_group_key",
        lambda _biz, value: value["items"][0].update(strategy_group_key="diagnostic"),
    )
    monkeypatch.setattr(
        strategy.Strategy, "fill_user_groups", lambda values: values[0]["notice"].update(user_group_list=[{"id": 1}])
    )
    enriched = strategy._build_strategy_config(SimpleNamespace(id=1, bk_biz_id=2), include_user_groups=True)
    assert enriched["config_version"] == version
    assert get_strategy_config_version(enriched) != version
    assert enriched["items"][0]["query_configs"][0]["id"] == 20
    assert enriched["items"][0]["algorithms"][0] == canonical["items"][0]["algorithms"][0]


@pytest.mark.parametrize("stale", [False, True])
def test_original_full_update_uses_one_snapshot_and_keeps_complete_request(config, api, stale):
    request = deepcopy(config)
    request.update(name="full API edit", confirm=True, audit_operator="untrusted-user")
    if stale:
        config["name"] = "concurrent edit"
    serializer = alert.UpdateAlarmStrategyResource.RequestSerializer(data=request)
    serializer.is_valid(raise_exception=True)
    if stale:
        with pytest.raises(ValidationError, match="重新调用 get_alarm_strategy"):
            alert.UpdateAlarmStrategyResource().perform_request(serializer.validated_data)
        api.save.assert_not_called()
    else:
        result = alert.UpdateAlarmStrategyResource().perform_request(serializer.validated_data)
        assert result == {"id": 1}
        request.pop("confirm")
        api.save.assert_called_once_with(**request)
        api.save_with_audit.assert_not_called()
        api.normalize.assert_called_once_with(request, config)
        api.relations.assert_called_once_with(2, request)
        api.preflight.assert_called_once_with(request)
    api.load.assert_called_once_with(bk_biz_id=2, id=1)
    api.read.assert_called_once_with([api.model])
    api.snapshot.assert_called_once_with(convert_dashboard=False)


def test_management_version_conflict_does_not_prepare_or_save(monkeypatch, request_data, api):
    prepare = Mock()
    monkeypatch.setattr(management, "_merge_items", prepare)
    request_data["config_version"] = "f" * 64
    with pytest.raises(ValidationError, match="config_version"):
        management.manage_strategy_config(request_data)
    prepare.assert_not_called()
    api.read.assert_called_once_with([api.model])
    api.save.assert_not_called()


def test_management_authorization_failure_does_not_load_or_save(request_data, api):
    api.authorize.side_effect = PermissionDenied("denied")
    with pytest.raises(PermissionDenied):
        management.manage_strategy_config(request_data)
    api.load.assert_not_called()
    api.read.assert_not_called()
    api.save.assert_not_called()


def test_management_prepared_configuration_uses_complete_request_serializer(config, request_data, api):
    config.pop("notice")
    request_data["config_version"] = get_strategy_config_version(config)
    with pytest.raises(ValidationError, match="notice"):
        management.manage_strategy_config(request_data)
    api.read.assert_called_once_with([api.model])
    api.normalize.assert_not_called()
    api.save.assert_not_called()


def test_internal_prepare_cannot_replace_identity_or_version(config, api):
    def prepare(current):
        current.update(id=999, bk_biz_id=999, config_version="replacement", confirm=False)

    alert.UpdateAlarmStrategyResource()._update_config(
        {"bk_biz_id": 2, "id": 1, "config_version": config["config_version"]},
        prepare_config=prepare,
    )
    api.save.assert_called_once_with(**config)
    api.normalize.assert_called_once_with(config, config)


def test_blank_expression_uses_existing_default_readback_semantics(config):
    config["items"][0]["expression"] = ""
    config["detects"][0].update(trigger_config={"count": 1, "check_window": 1}, recovery_config={"check_window": 1})
    restored = Strategy(**config).to_dict(convert_dashboard=False)
    assert restored["items"][0]["expression"] == "a"


@pytest.fixture
def standard_item(config):
    item = config["items"][0]
    item["metric_type"] = "time_series"
    item["expression"] = "a+b"
    item["query_configs"] = [
        {
            "id": 20 + index,
            "alias": alias,
            "data_source_label": "bk_monitor",
            "data_type_label": "time_series",
            "metric_id": f"bk_monitor.system.cpu_{alias}",
            "result_table_id": "system.cpu",
            "metric_field": f"cpu_{alias}",
            "agg_method": "AVG",
            "agg_interval": 60,
            "agg_dimension": ["bk_target_ip"],
            "agg_condition": [],
            "unit": "%",
            "functions": [],
            "origin_config": {"metric": alias},
        }
        for index, alias in enumerate("abc")
    ]
    return item


@pytest.fixture
def promql_patch(standard_item):
    return {
        "id": standard_item["id"],
        "expression": "a+b",
        "query_configs": [
            {
                "id": query["id"],
                "data_source_label": "prometheus",
                "data_type_label": "time_series",
                "promql": f"vector({value})",
                "expression_mode": "promql",
            }
            for query, value in zip(standard_item["query_configs"], (1, 2, 9))
        ],
        "query_output_config": {
            "response_contract": "named_outputs/v1",
            "legacy_output_ref": "RESULT",
            "output_list": [
                {"reference_name": "A", "expression": "a"},
                {"reference_name": "B", "expression": "b"},
                {"reference_name": "C", "expression": "c"},
                {"reference_name": "RESULT", "expression": "a+b"},
            ],
        },
    }


def test_standard_source_switch_uses_target_serializer_and_restores_ids(config, standard_item, promql_patch):
    original = deepcopy(standard_item)
    management._validate_config_patch({"items": [promql_patch]})
    management._merge_config_patch(config, {"items": [promql_patch]})
    validated = Item.Serializer().run_validation(standard_item)
    restored = Item(strategy_id=config["id"], **validated).to_dict()
    assert restored["query_output_config"] == promql_patch["query_output_config"]
    for original_query, query in zip(original["query_configs"], restored["query_configs"]):
        assert query["id"] == original_query["id"]
        assert query["alias"] == original_query["alias"]
        assert query["agg_interval"] == 60
        assert set(query) == {
            "id",
            "alias",
            "metric_id",
            "data_source_label",
            "data_type_label",
            "functions",
            "promql",
            "agg_interval",
            "expression_mode",
        }
    back = {
        "id": original["id"],
        "query_configs": [{k: v for k, v in q.items() if k != "metric_id"} for q in original["query_configs"]],
        "query_output_config": None,
    }
    management._merge_config_patch(config, {"items": [back]})
    alert.normalize_strategy_metric_ids(config, {"items": [restored]})
    for query in standard_item["query_configs"]:
        assert "promql" not in query
        assert "expression_mode" not in query
        assert query["data_source_label"] == "bk_monitor"
    assert [q["id"] for q in standard_item["query_configs"]] == [20, 21, 22]
    assert standard_item["algorithms"] == original["algorithms"]
    assert standard_item["no_data_config"] == original["no_data_config"]


@pytest.mark.parametrize("field,value", [("query_string", "typo"), ("agg_method", "AVG"), ("origin_config", {})])
def test_source_switch_rejects_inapplicable_submitted_fields(config, promql_patch, field, value):
    promql_patch["query_configs"][0][field] = value
    with pytest.raises(CustomException, match=field):
        management._merge_config_patch(config, {"items": [promql_patch]})


@pytest.mark.parametrize(
    "kind", ["mixed_mode", "mixed_source", "duplicate_alias", "different_period", "output_mismatch"]
)
def test_standard_promql_patch_reuses_item_validation(config, standard_item, promql_patch, kind):
    if kind == "mixed_mode":
        promql_patch["query_configs"][1].pop("expression_mode")
    elif kind == "mixed_source":
        promql_patch["query_configs"][1] = {"id": 21, "metric_field": "cpu_b"}
    elif kind == "duplicate_alias":
        promql_patch["query_configs"][1]["alias"] = "a"
    elif kind == "different_period":
        promql_patch["query_configs"][1]["agg_interval"] = 120
    else:
        promql_patch["query_output_config"]["output_list"][-1]["expression"] = "a+b+c"
    management._merge_config_patch(config, {"items": [promql_patch]})
    with pytest.raises(ValidationError):
        validated = Item.Serializer().run_validation(standard_item)
        Item(strategy_id=config["id"], **validated)


def test_query_output_patch_replaces_clears_and_preserves(config, standard_item, promql_patch):
    management._merge_config_patch(config, {"items": [promql_patch]})
    current = deepcopy(standard_item["query_output_config"])
    management._merge_config_patch(config, {"items": [{"id": 10, "name": "renamed"}]})
    assert standard_item["query_output_config"] == current
    replacement = {**current, "output_list": current["output_list"][-1:]}
    management._merge_config_patch(config, {"items": [{"id": 10, "query_output_config": replacement}]})
    assert standard_item["query_output_config"] == replacement
    management._merge_config_patch(config, {"items": [{"id": 10, "query_output_config": None}]})
    assert standard_item["query_output_config"] is None


def test_standard_create_accepts_promql_and_non_threshold_algorithm(create_request, api):
    item = create_request["config"]["items"][0]
    item["query_configs"] = [
        {
            "data_source_label": "prometheus",
            "data_type_label": "time_series",
            "alias": "a",
            "promql": "up",
            "agg_interval": 60,
        }
    ]
    item["algorithms"] = [{"type": "NewSeries", "level": 2, "config": {"detect_range": 600}}]
    api.save.return_value = {"id": 42, "name": create_request["config"]["name"]}
    management.manage_strategy_config(create_request)
    assert api.save.call_args.kwargs["items"][0]["algorithms"][0]["type"] == "NewSeries"


def test_standard_algorithm_patch_uses_selected_type(config, request_data, api):
    request_data.pop("items")
    request_data["config"] = {
        "items": [{"id": 10, "algorithms": [{"id": 30, "type": "NewSeries", "config": {"detect_range": 600}}]}]
    }
    management.manage_strategy_config(request_data)
    algorithm = api.save.call_args.kwargs["items"][0]["algorithms"][0]
    assert algorithm["type"] == "NewSeries"
    assert algorithm["config"]["effective_delay"] == 600
    assert algorithm["id"] == 30


def test_editable_query_fields_cover_every_current_platform_serializer():
    union = {field for serializer in QueryConfig.QueryConfigSerializerMapping.values() for field in serializer().fields}
    assert union | management.QUERY_IDENTITY_FIELDS == set(management.EDITABLE_FIELDS["query_configs"])


@pytest.mark.parametrize("field", ["origin_config", "intelligent_detect"])
def test_same_source_query_dictionary_patch_preserves_unedited_keys(standard_item, field):
    query = standard_item["query_configs"][0]
    query[field] = {"keep": {"first": 1, "second": 2}, "untouched": "preserved"}
    management._merge_query_config(query, {"id": query["id"], field: {"keep": {"first": 3}}})
    assert query[field] == {"keep": {"first": 3, "second": 2}, "untouched": "preserved"}


def test_grafana_variables_patch_preserves_other_variables():
    query = {
        "id": 20,
        "alias": "a",
        "data_source_label": "dashboard",
        "data_type_label": "time_series",
        "dashboard_uid": "synthetic",
        "panel_id": 1,
        "ref_id": "A",
        "variables": {"pod": ["first"], "cluster": ["synthetic"]},
    }
    management._merge_query_config(query, {"id": 20, "variables": {"pod": ["second"]}})
    assert query["variables"] == {"pod": ["second"], "cluster": ["synthetic"]}


@pytest.mark.parametrize("algorithm_type", [[], {}])
def test_standard_algorithm_invalid_type_uses_serializer_error(algorithm_type, config, request_data, api):
    request_data.pop("items")
    request_data["config"] = {"items": [{"id": 10, "algorithms": [{"id": 30, "type": algorithm_type, "config": {}}]}]}
    with pytest.raises(ValidationError):
        management.manage_strategy_config(request_data)
    api.save.assert_not_called()


def test_standard_create_accepts_the_platform_empty_algorithm_array(create_request, api):
    assert Item.Serializer().fields["algorithms"].run_validation([]) == []
    create_request["config"]["items"][0]["algorithms"] = []
    api.save.return_value = {"id": 42, "name": create_request["config"]["name"]}
    management.manage_strategy_config(create_request)
    assert api.save.call_args.kwargs["items"][0]["algorithms"] == []
