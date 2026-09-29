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
from kernel_api.rpc.functions.bkm_cli.platform_catalog import cmdb
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
    authorize = Mock()
    normalize = Mock(wraps=alert.normalize_strategy_metric_ids)
    relations = Mock()
    preflight = Mock(wraps=alert._validate_strategy_before_write)
    monkeypatch.setattr(
        alert, "StrategyModel", SimpleNamespace(objects=SimpleNamespace(get=load), DoesNotExist=LookupError)
    )
    monkeypatch.setattr(alert.Strategy, "from_models", read)
    monkeypatch.setattr(
        alert, "resource", SimpleNamespace(strategies=SimpleNamespace(save_strategy_v2=SimpleNamespace(request=save)))
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


@pytest.mark.parametrize(
    "update",
    [
        {"confirmed": False},
        {"confirmed": 1},
        {"operator": ""},
        {"operator": "<operator>"},
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
        {"items": [{"id": 10, "algorithms": [{"id": 30, "config": [[{"method": "gt", "threshold": True}]]}]}]},
        {
            "items": [
                {"id": 10, "algorithms": [{"id": 30, "config": [[{"method": "gt", "threshold": 1, "extra": None}]]}]}
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
    with pytest.raises(CustomException, match="不支持修改 query_string"):
        management.manage_strategy_config(request_data)
    api.save.assert_not_called()


def test_non_threshold_algorithm_rejected(config, request_data, api):
    config["items"][0]["algorithms"][0]["type"] = "NewSeries"
    request_data["config_version"] = get_strategy_config_version(config)
    request_data["items"] = [{"id": 10, "algorithms": [{"id": 30, "config": [[{"method": "gt", "threshold": 1}]]}]}]
    with pytest.raises(CustomException, match="已有 Threshold"):
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
    monkeypatch.setattr(cmdb, "get_request", lambda **_kwargs: request)
    monkeypatch.setattr(cmdb, "bk_biz_id_to_bk_tenant_id", lambda _value: "system")
    monkeypatch.setattr(cmdb, "is_match_api_token", lambda *_args: True)
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

        monkeypatch.setattr(cmdb, "is_match_api_token", deny_target)
    elif kind in ("token", "expired"):
        request.META["HTTP_AUTHORIZATION"] = "Bearer synthetic-token"
        record = SimpleNamespace(is_expired=lambda: kind == "expired", is_allowed_namespace=lambda _: False)
        monkeypatch.setattr(cmdb.ApiAuthToken.objects, "filter", lambda **_: SimpleNamespace(first=lambda: record))
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
    request.update(name="full API edit", confirm=True)
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
