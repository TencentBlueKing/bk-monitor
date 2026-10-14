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
        (container_payload(data_encoding="GBK"), "data_encoding"),
    ],
)
def test_serializer_rejects_fields_from_another_environment(payload, field):
    serializer = FastCreateLogCollectorResource.RequestSerializer(data=payload)

    assert not serializer.is_valid()
    assert field in serializer.errors


def test_container_serializer_accepts_filters_under_container_object():
    serializer = FastCreateLogCollectorResource.RequestSerializer(
        data=container_payload(
            configs=[
                {
                    "namespaces": ["default"],
                    "container": {
                        "workload_type": "Deployment",
                        "workload_name": "api-.*",
                        "container_name": "api,sidecar",
                    },
                    "data_encoding": "GBK",
                    "params": {"paths": ["/var/log/app.log"]},
                    "collector_type": "container_log_config",
                }
            ]
        )
    )

    assert serializer.is_valid(), serializer.errors


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
        "data_link_id",
        "allocation_min_days",
        "platform_username",
        "bk_username",
    ],
)
def test_serializer_rejects_infrastructure_and_identity_overrides(field):
    serializer = FastCreateLogCollectorResource.RequestSerializer(data=linux_payload(**{field: 1}))

    assert not serializer.is_valid()
    assert field in serializer.errors


@pytest.mark.parametrize("payload_factory", [linux_payload, windows_payload, container_payload])
@pytest.mark.parametrize(
    "storage_options",
    [
        {},
        {"storage_cluster_id": 12},
        {"retention": 30},
        {"es_shards": 3},
        {"storage_replies": 0},
        {"storage_cluster_id": 12, "retention": 30, "es_shards": 3, "storage_replies": 1},
        {"storage_cluster_id": 12, "retention": 30, "es_shards": 3, "storage_replies": 0},
    ],
)
def test_fast_create_forwards_optional_storage_settings(monkeypatch, payload_factory, storage_options):
    calls = {}
    cluster_queries = []
    api_resource = FastCreateLogCollectorAPIResource()

    def fast_create(**kwargs):
        calls["mcp"] = kwargs
        calls["bklog"] = api_resource.validate_request_data(kwargs)
        return {
            "collector_config_id": 31,
            "bk_data_id": 51,
            "subscription_id": 61,
            "task_id_list": [71],
            "index_set_id": 41,
        }

    def cluster_groups(**kwargs):
        cluster_queries.append(kwargs)
        return [{"storage_cluster_id": 12}]

    monkeypatch.setattr(
        create_module,
        "api",
        SimpleNamespace(
            log_search=SimpleNamespace(
                fast_create_log_collector=fast_create,
                bk_log_search_cluster_groups=cluster_groups,
            )
        ),
    )
    serializer = FastCreateLogCollectorResource.RequestSerializer(data=payload_factory(**storage_options))
    assert serializer.is_valid(), serializer.errors

    result = FastCreateLogCollectorResource().perform_request(serializer.validated_data)

    for params in calls.values():
        assert {
            key: params[key]
            for key in ("storage_cluster_id", "retention", "es_shards", "storage_replies")
            if key in params
        } == storage_options
    assert calls["bklog"]["enforce_permission"] is True
    assert "confirm" not in calls["bklog"]
    if "storage_cluster_id" in storage_options:
        # 显式传集群时按 ES + Doris 查询可见集群
        assert [(query["bk_biz_id"], query.get("cluster_type")) for query in cluster_queries] == [(2, "all")]
    elif any(key in storage_options for key in ("retention", "es_shards", "storage_replies")):
        # 只传存储参数时按 BKLOG 默认口径查询公共 ES 集群，用于取上限
        assert [(query["bk_biz_id"], query.get("cluster_type")) for query in cluster_queries] == [(2, None)]
    else:
        assert cluster_queries == []
    assert result["collector_config_id"] == 31


@pytest.mark.parametrize("payload_factory", [linux_payload, windows_payload, container_payload])
def test_fast_create_rejects_storage_cluster_outside_business_visible_range(monkeypatch, payload_factory):
    created = []

    def fast_create(**kwargs):
        created.append(kwargs)
        return {"collector_config_id": 31}

    monkeypatch.setattr(
        create_module,
        "api",
        SimpleNamespace(
            log_search=SimpleNamespace(
                fast_create_log_collector=fast_create,
                bk_log_search_cluster_groups=lambda **kwargs: [
                    {"storage_cluster_id": 12},
                    {"storage_cluster_id": 13},
                ],
            )
        ),
    )
    serializer = FastCreateLogCollectorResource.RequestSerializer(data=payload_factory(storage_cluster_id=99))
    assert serializer.is_valid(), serializer.errors

    with pytest.raises(ValidationError, match="storage_cluster_id"):
        FastCreateLogCollectorResource().perform_request(serializer.validated_data)

    assert created == []


def test_fast_create_skips_storage_cluster_lookup_without_storage_params(monkeypatch):
    monkeypatch.setattr(
        create_module,
        "api",
        SimpleNamespace(
            log_search=SimpleNamespace(
                fast_create_log_collector=lambda **kwargs: {
                    "collector_config_id": 31,
                    "bk_data_id": 51,
                    "subscription_id": None,
                    "task_id_list": None,
                    "index_set_id": 41,
                },
                bk_log_search_cluster_groups=lambda **kwargs: pytest.fail(
                    "storage cluster visibility must not be queried when storage_cluster_id is absent"
                ),
            )
        ),
    )
    serializer = FastCreateLogCollectorResource.RequestSerializer(data=linux_payload())
    assert serializer.is_valid(), serializer.errors

    result = FastCreateLogCollectorResource().perform_request(serializer.validated_data)

    assert result["collector_config_id"] == 31


STORAGE_CAPS_CLUSTER = {
    "storage_cluster_id": 12,
    "cluster_type": "elasticsearch",
    "cluster_config": {
        "cluster_id": 12,
        "custom_option": {
            "setup_config": {
                "retention_days_max": 7,
                "es_shards_max": 512,
                "number_of_replicas_max": 1,
            }
        },
    },
}


def patch_api_with_clusters(monkeypatch, clusters, created, queries=None):
    """把集群列表与创建接口替换为桩，并记录实际创建参数与集群查询参数。"""

    def fast_create(**kwargs):
        created.append(kwargs)
        return {
            "collector_config_id": 31,
            "bk_data_id": 51,
            "subscription_id": 61,
            "task_id_list": [71],
            "index_set_id": 41,
        }

    def cluster_groups(**kwargs):
        if queries is not None:
            queries.append(kwargs)
        return clusters

    monkeypatch.setattr(
        create_module,
        "api",
        SimpleNamespace(
            log_search=SimpleNamespace(
                fast_create_log_collector=fast_create,
                bk_log_search_cluster_groups=cluster_groups,
            )
        ),
    )


@pytest.mark.parametrize("payload_factory", [linux_payload, windows_payload, container_payload])
@pytest.mark.parametrize(("field", "value"), [("retention", 8), ("es_shards", 513), ("storage_replies", 2)])
def test_fast_create_rejects_storage_settings_above_cluster_limits(monkeypatch, payload_factory, field, value):
    created = []
    patch_api_with_clusters(monkeypatch, [STORAGE_CAPS_CLUSTER], created)
    serializer = FastCreateLogCollectorResource.RequestSerializer(
        data=payload_factory(storage_cluster_id=12, **{field: value})
    )
    assert serializer.is_valid(), serializer.errors

    with pytest.raises(ValidationError, match=field):
        FastCreateLogCollectorResource().perform_request(serializer.validated_data)

    assert created == []


@pytest.mark.parametrize("payload_factory", [linux_payload, windows_payload, container_payload])
def test_fast_create_allows_storage_settings_at_cluster_limits(monkeypatch, payload_factory):
    created = []
    patch_api_with_clusters(monkeypatch, [STORAGE_CAPS_CLUSTER], created)
    serializer = FastCreateLogCollectorResource.RequestSerializer(
        data=payload_factory(storage_cluster_id=12, retention=7, es_shards=512, storage_replies=1)
    )
    assert serializer.is_valid(), serializer.errors

    result = FastCreateLogCollectorResource().perform_request(serializer.validated_data)

    assert result["collector_config_id"] == 31
    assert created[0]["es_shards"] == 512


def test_fast_create_checks_storage_limits_of_default_cluster(monkeypatch):
    created = []
    queries = []
    patch_api_with_clusters(monkeypatch, [STORAGE_CAPS_CLUSTER], created, queries)
    serializer = FastCreateLogCollectorResource.RequestSerializer(data=linux_payload(retention=8))
    assert serializer.is_valid(), serializer.errors

    with pytest.raises(ValidationError, match="retention"):
        FastCreateLogCollectorResource().perform_request(serializer.validated_data)

    assert created == []
    # 未传集群时按 BKLOG 默认口径查询（不带 cluster_type，仅公共 ES 集群）
    assert [(query["bk_biz_id"], query.get("cluster_type")) for query in queries] == [(2, None)]


def test_fast_create_allows_storage_settings_within_default_cluster_limits(monkeypatch):
    created = []
    patch_api_with_clusters(monkeypatch, [STORAGE_CAPS_CLUSTER], created)
    serializer = FastCreateLogCollectorResource.RequestSerializer(data=linux_payload(retention=7, storage_replies=0))
    assert serializer.is_valid(), serializer.errors

    result = FastCreateLogCollectorResource().perform_request(serializer.validated_data)

    assert result["collector_config_id"] == 31
    assert created[0]["storage_replies"] == 0


def test_fast_create_skips_limits_missing_from_cluster_setup_config(monkeypatch):
    doris_cluster = {
        "storage_cluster_id": 21,
        "cluster_type": "doris",
        "cluster_config": {"cluster_id": 21, "custom_option": {"setup_config": {"retention_days_max": 7}}},
    }
    created = []
    patch_api_with_clusters(monkeypatch, [doris_cluster], created)
    serializer = FastCreateLogCollectorResource.RequestSerializer(
        data=linux_payload(storage_cluster_id=21, retention=7, es_shards=4096, storage_replies=50)
    )
    assert serializer.is_valid(), serializer.errors

    result = FastCreateLogCollectorResource().perform_request(serializer.validated_data)

    assert result["collector_config_id"] == 31


def test_fast_create_ignores_non_positive_cluster_limits(monkeypatch):
    cluster = {
        "storage_cluster_id": 12,
        "cluster_config": {
            "cluster_id": 12,
            "custom_option": {
                "setup_config": {"retention_days_max": 7, "es_shards_max": 0, "number_of_replicas_max": 0}
            },
        },
    }
    created = []
    patch_api_with_clusters(monkeypatch, [cluster], created)
    serializer = FastCreateLogCollectorResource.RequestSerializer(
        data=linux_payload(storage_cluster_id=12, retention=7, es_shards=513, storage_replies=100)
    )
    assert serializer.is_valid(), serializer.errors

    result = FastCreateLogCollectorResource().perform_request(serializer.validated_data)

    assert result["collector_config_id"] == 31


@pytest.mark.parametrize(
    "serializer_class",
    [FastCreateLogCollectorResource.RequestSerializer, FastCreateLogCollectorAPIResource.RequestSerializer],
)
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("storage_cluster_id", 0),
        ("storage_cluster_id", -1),
        ("retention", 0),
        ("retention", -1),
        ("es_shards", 0),
        ("es_shards", -1),
        ("storage_replies", -1),
        *[
            (field, value)
            for field in ("storage_cluster_id", "retention", "es_shards", "storage_replies")
            for value in (None, 1.5, "invalid")
        ],
    ],
)
def test_fast_create_rejects_invalid_storage_settings(serializer_class, field, value):
    serializer = serializer_class(data=linux_payload(**{field: value}))

    assert not serializer.is_valid()
    assert field in serializer.errors


def test_serializer_accepts_parent_index_set_ids():
    serializer = FastCreateLogCollectorResource.RequestSerializer(data=linux_payload(parent_index_set_ids=[11, 12]))

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["parent_index_set_ids"] == [11, 12]


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
        return {
            "collector_config_id": 31,
            "bk_data_id": 51,
            "subscription_id": None,
            "task_id_list": None,
            "index_set_id": 41,
        }

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
