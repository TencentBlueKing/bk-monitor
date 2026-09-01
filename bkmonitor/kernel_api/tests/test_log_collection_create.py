"""日志采集 Fast Create MCP 资源测试。"""

from types import SimpleNamespace

import pytest
from rest_framework.exceptions import PermissionDenied, ValidationError

from api.log_search.default import FastCreateLogCollectorResource as FastCreateLogCollectorAPIResource
from bkmonitor.iam import ActionEnum
from core.drf_resource.contrib import api as api_module
from kernel_api.resource import log_collection_create as create_module
from kernel_api.resource.log_collection_create import FastCreateLogCollectorResource
from kernel_api.views.v4.log_collection_create import (
    CanonicalBusinessActionPermission,
    LogCollectionCreateViewSet,
)


def linux_payload(**overrides):
    payload = {
        "bk_biz_id": 2,
        "environment": "linux",
        "collector_config_name": "linux app",
        "collector_config_name_en": "linux_app",
        "collector_scenario_id": "row",
        "target_object_type": "HOST",
        "target_node_type": "INSTANCE",
        "target_nodes": [{"bk_host_id": 101}],
        "params": {"paths": ["/var/log/app.log"]},
        "confirm": True,
    }
    payload.update(overrides)
    return payload


def windows_payload(**overrides):
    payload = {
        "bk_biz_id": 2,
        "environment": "windows",
        "collector_config_name": "windows events",
        "collector_config_name_en": "windows_events",
        "collector_scenario_id": "wineventlog",
        "target_object_type": "HOST",
        "target_node_type": "INSTANCE",
        "target_nodes": [{"bk_host_id": 102}],
        "params": {"winlog_name": ["Application"], "winlog_level": ["error"]},
        "confirm": True,
    }
    payload.update(overrides)
    return payload


def container_payload(**overrides):
    payload = {
        "bk_biz_id": 2,
        "environment": "container",
        "collector_config_name": "container app",
        "collector_config_name_en": "container_app",
        "collector_scenario_id": "row",
        "bcs_cluster_id": "BCS-K8S-00000",
        "configs": [
            {
                "namespaces": ["default"],
                "params": {"paths": ["/var/log/app.log"]},
                "collector_type": "container_log_config",
            }
        ],
        "confirm": True,
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("payload", [linux_payload(), windows_payload(), container_payload()])
def test_serializer_accepts_three_environments(payload):
    serializer = FastCreateLogCollectorResource.RequestSerializer(data=payload)

    assert serializer.is_valid(), serializer.errors


@pytest.mark.parametrize("confirm", [None, False])
def test_serializer_requires_explicit_confirmation(confirm):
    payload = linux_payload()
    if confirm is None:
        payload.pop("confirm")
    else:
        payload["confirm"] = confirm

    serializer = FastCreateLogCollectorResource.RequestSerializer(data=payload)

    assert not serializer.is_valid()
    assert "confirm" in serializer.errors


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        (linux_payload(configs=container_payload()["configs"]), "configs"),
        (container_payload(target_nodes=[]), "target_nodes"),
        (windows_payload(bcs_cluster_id="BCS-K8S-00000"), "bcs_cluster_id"),
    ],
)
def test_serializer_rejects_fields_from_another_environment(payload, field):
    serializer = FastCreateLogCollectorResource.RequestSerializer(data=payload)

    assert not serializer.is_valid()
    assert field in serializer.errors


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        (linux_payload(collector_scenario_id="wineventlog"), "collector_scenario_id"),
        (windows_payload(collector_scenario_id="row"), "collector_scenario_id"),
        (container_payload(collector_scenario_id="wineventlog"), "collector_scenario_id"),
    ],
)
def test_serializer_rejects_scenario_environment_mismatch(payload, field):
    serializer = FastCreateLogCollectorResource.RequestSerializer(data=payload)

    assert not serializer.is_valid()
    assert field in serializer.errors


@pytest.mark.parametrize(
    "field",
    [
        "storage_cluster_id",
        "data_link_id",
        "retention",
        "es_shards",
        "parent_index_set_ids",
        "platform_username",
        "bk_username",
    ],
)
def test_serializer_rejects_infrastructure_and_identity_overrides(field):
    serializer = FastCreateLogCollectorResource.RequestSerializer(data=linux_payload(**{field: 1}))

    assert not serializer.is_valid()
    assert field in serializer.errors


@pytest.mark.parametrize(
    ("payload", "error_field"),
    [
        (linux_payload(params={"paths": ["/tmp/a"], "unknown": True}), "params.unknown"),
        (
            linux_payload(target_nodes=[{"bk_host_id": 101, "unknown": True}]),
            "target_nodes[0].unknown",
        ),
        (
            container_payload(
                configs=[
                    {
                        "params": {"paths": ["/tmp/a"]},
                        "collector_type": "container_log_config",
                        "unknown": True,
                    }
                ]
            ),
            "configs[0].unknown",
        ),
        (
            container_payload(
                configs=[
                    {
                        "params": {"paths": ["/tmp/a"], "winlog_name": ["Application"]},
                        "collector_type": "container_log_config",
                    }
                ]
            ),
            "configs[0].params.winlog_name",
        ),
    ],
)
def test_serializer_rejects_unknown_or_mixed_nested_fields(payload, error_field):
    serializer = FastCreateLogCollectorResource.RequestSerializer(data=payload)

    assert not serializer.is_valid()
    assert error_field in serializer.errors


def test_windows_requires_winlog_name_and_rejects_linux_paths():
    missing_name = FastCreateLogCollectorResource.RequestSerializer(data=windows_payload(params={}))
    mixed_paths = FastCreateLogCollectorResource.RequestSerializer(
        data=windows_payload(params={"winlog_name": ["Application"], "paths": ["C:\\logs\\app.log"]})
    )

    assert not missing_name.is_valid()
    assert "params.winlog_name" in missing_name.errors
    assert not mixed_paths.is_valid()
    assert "params.paths" in mixed_paths.errors


def test_create_view_requires_manage_collection_permission():
    permissions = LogCollectionCreateViewSet().get_permissions()

    assert len(permissions) == 1
    assert permissions[0].actions == [ActionEnum.MANAGE_COLLECTION]


def test_create_permission_rejects_conflicting_business_alias():
    permission = CanonicalBusinessActionPermission([ActionEnum.MANAGE_COLLECTION])
    request = SimpleNamespace(
        data={"bk_biz_id": "2", "biz_id": "3"},
        biz_id="3",
    )

    assert permission.has_permission(request, None) is False


@pytest.mark.parametrize(
    ("payload", "created_id"),
    [
        (linux_payload(), 11),
        (windows_payload(), 12),
        (container_payload(), 13),
    ],
)
def test_fast_create_dispatches_environment_and_returns_stable_contract(monkeypatch, payload, created_id):
    calls = {}

    def fast_create(**kwargs):
        calls["create"] = kwargs
        return {
            "collector_config_id": created_id,
            "bk_data_id": 1000 + created_id,
            "subscription_id": 2000 + created_id,
            "task_id_list": [3000 + created_id],
            "index_set_id": 4000 + created_id,
            "ignored": "not exposed",
        }

    monkeypatch.setattr(
        create_module,
        "api",
        SimpleNamespace(
            log_search=SimpleNamespace(
                fast_create_log_collector=fast_create,
                data_bus_collectors=lambda **kwargs: pytest.fail("complete responses must not trigger readback"),
            )
        ),
    )
    serializer = FastCreateLogCollectorResource.RequestSerializer(data=payload)
    assert serializer.is_valid(), serializer.errors

    result = FastCreateLogCollectorResource().perform_request(serializer.validated_data)

    assert calls["create"]["environment"] == payload["environment"]
    assert calls["create"]["enforce_permission"] is True
    assert "confirm" not in calls["create"]
    assert "storage_cluster_id" not in calls["create"]
    assert "data_link_id" not in calls["create"]
    assert result == {
        "collector_config_id": created_id,
        "bk_data_id": 1000 + created_id,
        "subscription_id": 2000 + created_id,
        "task_id_list": [str(3000 + created_id)],
        "index_set_id": 4000 + created_id,
    }


def test_fast_create_fills_legacy_response_from_detail(monkeypatch):
    monkeypatch.setattr(
        create_module,
        "api",
        SimpleNamespace(
            log_search=SimpleNamespace(
                fast_create_log_collector=lambda **kwargs: {"collector_config_id": 21},
                data_bus_collectors=lambda **kwargs: {
                    "collector_config_id": 21,
                    "bk_biz_id": 2,
                    "bk_data_id": 1021,
                    "subscription_id": 2021,
                    "task_id_list": "3021,3022",
                    "index_set_id": 4021,
                },
            )
        ),
    )

    result = FastCreateLogCollectorResource().perform_request(linux_payload())

    assert result == {
        "collector_config_id": 21,
        "bk_data_id": 1021,
        "subscription_id": 2021,
        "task_id_list": ["3021", "3022"],
        "index_set_id": 4021,
    }


def test_fast_create_rejects_cross_business_readback(monkeypatch):
    monkeypatch.setattr(
        create_module,
        "api",
        SimpleNamespace(
            log_search=SimpleNamespace(
                fast_create_log_collector=lambda **kwargs: {"collector_config_id": 22},
                data_bus_collectors=lambda **kwargs: {"collector_config_id": 22, "bk_biz_id": 3},
            )
        ),
    )

    with pytest.raises(PermissionDenied):
        FastCreateLogCollectorResource().perform_request(linux_payload())


def test_fast_create_requires_collector_id_in_backend_response(monkeypatch):
    monkeypatch.setattr(
        create_module,
        "api",
        SimpleNamespace(
            log_search=SimpleNamespace(
                fast_create_log_collector=lambda **kwargs: {},
                data_bus_collectors=lambda **kwargs: pytest.fail("detail should not be requested"),
            )
        ),
    )

    with pytest.raises(ValidationError, match="collector_config_id"):
        FastCreateLogCollectorResource().perform_request(linux_payload())


def test_fast_create_api_resource_injects_current_username(monkeypatch):
    monkeypatch.setattr(api_module, "make_userinfo", lambda **kwargs: {"bk_username": "alice"})
    resource = FastCreateLogCollectorAPIResource()
    resource.bk_tenant_id = "default"

    request_data = resource.full_request_data({"bk_biz_id": 2})

    assert request_data["bk_username"] == "alice"


def test_fast_create_forwards_parent_index_set_ids(monkeypatch):
    calls = {}

    def fast_create(**kwargs):
        calls.update(kwargs)
        return {"collector_config_id": 31, "index_set_id": 41}

    monkeypatch.setattr(
        create_module,
        "api",
        SimpleNamespace(log_search=SimpleNamespace(fast_create_log_collector=fast_create)),
    )
    payload = linux_payload(parent_index_set_ids=[901, 902])
    serializer = FastCreateLogCollectorResource.RequestSerializer(data=payload)
    assert serializer.is_valid(), serializer.errors

    result = FastCreateLogCollectorResource().perform_request(serializer.validated_data)

    assert calls["parent_index_set_ids"] == [901, 902]
    assert "parent_index_set_id" not in calls
    assert result["index_set_id"] == 41
