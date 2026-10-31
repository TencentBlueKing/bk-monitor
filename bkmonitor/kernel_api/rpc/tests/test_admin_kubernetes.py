from unittest.mock import Mock

import pytest
from rest_framework.exceptions import ValidationError

from kernel_api.rpc.functions.admin import kubernetes as module


def params(**overrides):
    return {"bk_tenant_id": "tenant-a", "cluster_id": "BCS-K8S-1", "resource": "pods", **overrides}


@pytest.fixture
def client(monkeypatch):
    client = Mock()
    cluster = Mock(api_client=client)
    lookup = Mock(return_value=cluster)
    monkeypatch.setattr(module, "_get_bcs_cluster_or_raise", lookup)
    client.lookup = lookup
    return client


def discovery(name="pods", namespaced=True, kind="Pod"):
    return {"resources": [{"name": name, "kind": kind, "namespaced": namespaced, "verbs": ["get", "list"]}]}


def test_native_pagination_and_tenant(client):
    client.call_api.side_effect = [
        discovery(),
        {
            "items": [{"kind": "Pod", "metadata": {"name": "web"}}],
            "metadata": {"continue": "next+/=", "resourceVersion": "12"},
        },
    ]
    result = module.list_resources(
        params(
            namespace="default",
            page_size=3,
            **{
                "continue": "previous",
                "label_selector": "app=web",
                "field_selector": "status.phase=Running",
            },
        )
    )
    client.lookup.assert_called_once_with("tenant-a", "BCS-K8S-1")
    call = client.call_api.call_args
    assert call.args == ("/api/v1/namespaces/default/pods", "GET")
    assert dict(call.kwargs["query_params"]) == {
        "limit": 3,
        "continue": "previous",
        "labelSelector": "app=web",
        "fieldSelector": "status.phase=Running",
    }
    assert result["data"]["continue"] == "next+/="
    assert result["data"]["has_more"] is True
    assert result["meta"]["safety_level"] == "inspect"


def test_custom_resource_and_secret_redaction(client):
    client.call_api.side_effect = [
        discovery("widgets", kind="Widget"),
        {"kind": "Widget", "spec": {"password": "hidden"}},
    ]
    result = module.get_resource(
        params(api_version="example.com/v1", resource="widgets", namespace="default", name="one")
    )
    assert client.call_api.call_args.args == ("/apis/example.com/v1/namespaces/default/widgets/one", "GET")
    assert "hidden" not in str(result)
    client.call_api.side_effect = [
        discovery("secrets", kind="Secret"),
        {
            "kind": "Secret",
            "data": {"arbitrary": "c2VjcmV0"},
            "stringData": {"foo": "hidden"},
            "metadata": {"name": "test", "annotations": {"last-applied": "hidden"}},
        },
    ]
    resource = module.get_resource(params(resource="secrets", namespace="default", name="test"))["data"]["resource"]
    assert resource == {"kind": "Secret", "metadata": {"name": "test"}}


@pytest.mark.parametrize(
    "override",
    [
        {"resource": "pods/exec"},
        {"resource": "../pods"},
        {"api_version": "v1/../../proxy"},
        {"namespace": "../default"},
        {"method": "POST"},
        {"watch": True},
        {"page_size": 101},
        {"bk_tenant_id": "__all__"},
        {"bk_tenant_id": ""},
    ],
)
def test_reject_inputs_before_connecting(client, override):
    with pytest.raises(ValidationError):
        module.list_resources(params(**override))
    client.lookup.assert_not_called()


def test_scope_and_missing_resource(client):
    for entries, overrides in [
        (discovery(), {}),
        (discovery("nodes", False, kind="Node"), {"resource": "nodes", "namespace": "default"}),
        (discovery("nodes", False, kind="Node"), {"resource": "unknown"}),
    ]:
        client.call_api.reset_mock()
        client.call_api.side_effect = [entries]
        with pytest.raises(ValidationError):
            module.get_resource(params(name="one", **overrides))
        assert client.call_api.call_count == 1


def test_cluster_scope_and_upstream_failure(client):
    client.call_api.side_effect = [discovery("nodes", False, kind="Node"), {"kind": "Node"}]
    module.get_resource(params(resource="nodes", name="node1"))
    assert client.call_api.call_args.args == ("/api/v1/nodes/node1", "GET")
    client.call_api.side_effect = RuntimeError("upstream forbidden")
    with pytest.raises(RuntimeError, match="upstream forbidden"):
        module.list_resources(params())


def test_discovery_pagination_excludes_subresources(client):
    client.call_api.return_value = {
        "resources": [
            {"name": "pods/exec", "verbs": ["get"]},
            {"name": "pods", "verbs": ["get", "list"]},
            {"name": "nodes", "verbs": ["list"]},
        ]
    }
    result = module.api_resources({"bk_tenant_id": "tenant-a", "cluster_id": "BCS-K8S-1", "page": 2, "page_size": 1})
    assert result["data"]["total"] == 2
    assert result["data"]["items"][0]["name"] == "nodes"


@pytest.mark.parametrize("kind", ["Pod", "Deployment", "DaemonSet", "Job", "CronJob", "StatefulSet", "ReplicaSet"])
def test_workload_environment_values_are_hidden(kind):
    spec = {
        container_type: [
            {
                "name": "app",
                "env": [
                    {"name": "NORMAL", "value": "hidden-env"},
                    {"name": "REFERENCED", "valueFrom": {"configMapKeyRef": {"name": "config", "key": "setting"}}},
                ],
            }
        ]
        for container_type in ["containers", "initContainers", "ephemeralContainers"]
    }
    if kind != "Pod":
        spec = {"template": {"spec": spec}}
    if kind == "CronJob":
        spec = {"jobTemplate": {"spec": spec}}
    resource = {
        "kind": kind,
        "spec": spec,
        "metadata": {
            "annotations": {
                "kubectl.kubernetes.io/last-applied-configuration": "hidden-annotation",
                "owner": "team",
            }
        },
    }
    result = module._redact(resource)
    assert "hidden-env" not in str(result)
    assert "hidden-annotation" not in str(result)
    assert "NORMAL" in str(result)
    assert "REFERENCED" in str(result)
    assert "setting" in str(result)
    assert result["metadata"]["annotations"]["owner"] == "team"
    assert "hidden-env" in str(resource)  # 不修改上游对象


def test_configmap_hides_all_values_but_keeps_keys():
    result = module._redact(
        {"kind": "ConfigMap", "data": {"setting": "hidden-config"}, "binaryData": {"file": "aGlkZGVu"}}
    )
    assert result["data"] == {"setting": "[REDACTED]"}
    assert result["binaryData"] == {"file": "[REDACTED]"}


@pytest.mark.parametrize("query", ["list", "get"])
def test_custom_workload_nested_pod_template_masks_env(client, query):
    resource = {
        "apiVersion": "workloads.example.com/v1alpha1",
        "kind": "CustomWorkload",
        "spec": {
            "workers": [
                {
                    "podTemplate": {
                        "spec": {
                            "containers": [
                                {
                                    "name": "worker",
                                    "env": [{"name": "NORMAL_SETTING", "value": "hidden-crd-env"}],
                                }
                            ]
                        }
                    }
                }
            ]
        },
    }
    result = {"items": [resource], "metadata": {}} if query == "list" else resource
    client.call_api.side_effect = [discovery("customworkloads", kind="CustomWorkload"), result]
    arguments = params(api_version="workloads.example.com/v1alpha1", resource="customworkloads", namespace="default")
    if query == "get":
        arguments["name"] = "example"
        response = module.get_resource(arguments)
    else:
        response = module.list_resources(arguments)
    assert "hidden-crd-env" not in str(response)
    assert "NORMAL_SETTING" in str(response)
    assert "[REDACTED]" in str(response)


@pytest.mark.parametrize("query", ["list", "get"])
@pytest.mark.parametrize("resource_name,kind", [("configmaps", "ConfigMap"), ("secrets", "Secret")])
def test_redacts_resources_without_kind_using_discovery(client, query, resource_name, kind):
    resource = {
        "metadata": {
            "name": "sample",
            "namespace": "default",
            "annotations": {
                "kubectl.kubernetes.io/last-applied-configuration": "hidden-copy",
                "owner": "team",
            },
        },
        "data": {"ordinary-setting": "hidden-data"},
    }
    if kind == "ConfigMap":
        resource["binaryData"] = {"file": "aGlkZGVu"}
    else:
        resource["stringData"] = {"ordinary-setting": "hidden-string-data"}
    upstream = (
        {"items": [resource], "metadata": {"continue": "next", "resourceVersion": "12"}}
        if query == "list"
        else resource
    )
    client.call_api.side_effect = [discovery(resource_name, kind=kind), upstream]
    arguments = params(resource=resource_name, namespace="default")
    if query == "list":
        data = module.list_resources(arguments)["data"]
        result = data["items"][0]
        assert data["continue"] == "next"
        assert data["resource_version"] == "12"
    else:
        result = module.get_resource({**arguments, "name": "sample"})["data"]["resource"]
    assert result["metadata"]["name"] == "sample"
    assert "kind" not in result  # 类型仅用于遮罩，不补造上游字段。
    if kind == "ConfigMap":
        assert result["data"] == {"ordinary-setting": "[REDACTED]"}
        assert result["binaryData"] == {"file": "[REDACTED]"}
        assert result["metadata"]["annotations"] == {"owner": "team"}
    else:
        assert "data" not in result
        assert "stringData" not in result
        assert "annotations" not in result["metadata"]
    assert resource["data"]["ordinary-setting"] == "hidden-data"
    assert client.call_api.call_count == 2


def unmask_rule(resource="configmaps", **overrides):
    return {
        "bk_tenant_id": "tenant-a",
        "cluster_id": "BCS-K8S-1",
        "namespace": "default",
        "api_group": "",
        "resource": resource,
        "resource_names": ["allowed"],
        **overrides,
    }


@pytest.mark.parametrize("query", ["list", "get"])
def test_unmask_configmap_only_matching_names_and_fields(client, query):
    objects = [
        {
            "metadata": {
                "name": name,
                "namespace": "default",
                "annotations": {
                    "kubectl.kubernetes.io/last-applied-configuration": "hidden-copy",
                    "password": "hidden-annotation",
                },
            },
            "data": {"password": "raw-config-password"},
            "binaryData": {"file": "cmF3"},
        }
        for name in ["allowed", "other"]
    ]
    client.call_api.side_effect = [
        discovery("configmaps", kind="ConfigMap"),
        {"items": objects, "metadata": {"continue": "next"}} if query == "list" else objects[0],
    ]
    args = params(resource="configmaps", namespace="default", include_sensitive=True, unmask_rules=[unmask_rule()])
    response = module.list_resources(args) if query == "list" else module.get_resource({**args, "name": "allowed"})
    data = response["data"]
    item = data["items"][0] if query == "list" else data["resource"]
    assert item["data"]["password"] == "raw-config-password"
    assert item["binaryData"]["file"] == "cmF3"
    assert "hidden-copy" not in str(response)
    assert "hidden-annotation" not in str(response)
    assert data["unmasked_resources"] == [{"namespace": "default", "name": "allowed"}]
    assert data["unmasked_count"] == 1
    if query == "list":
        assert data["items"][1]["data"]["password"] == "[REDACTED]"
        assert data["continue"] == "next"
    assert client.call_api.call_count == 2


@pytest.mark.parametrize(
    "overrides",
    [
        {"bk_tenant_id": "other"},
        {"cluster_id": "other"},
        {"namespace": "other"},
        {"api_group": "apps"},
        {"resource": "pods"},
        {"resource_names": ["other"]},
    ],
)
def test_unmask_scope_denied_before_lookup(client, overrides):
    from rest_framework.exceptions import PermissionDenied

    with pytest.raises(PermissionDenied):
        module.get_resource(
            params(
                resource="configmaps",
                namespace="default",
                name="allowed",
                include_sensitive=True,
                unmask_rules=[unmask_rule(**overrides)],
            )
        )
    client.lookup.assert_not_called()


@pytest.mark.parametrize(
    "args,exception",
    [
        ({"include_sensitive": True}, ValidationError),
        (
            {"include_sensitive": True, "namespace": "default"},
            __import__("rest_framework.exceptions", fromlist=["PermissionDenied"]).PermissionDenied,
        ),
    ],
)
def test_unmask_requires_namespace_and_rules(client, args, exception):
    with pytest.raises(exception):
        module.list_resources(params(**args))
    client.lookup.assert_not_called()


def test_secret_cannot_be_unmasked(client):
    from rest_framework.exceptions import PermissionDenied

    client.call_api.return_value = discovery("secrets", kind="Secret")
    with pytest.raises(PermissionDenied):
        module.list_resources(
            params(
                resource="secrets",
                namespace="default",
                include_sensitive=True,
                unmask_rules=[unmask_rule(resource="secrets", resource_names=[])],
            )
        )
    assert client.call_api.call_count == 1


@pytest.mark.parametrize("include_sensitive", [False, True])
def test_custom_workload_unmask_env_only_when_requested(client, include_sensitive):
    obj = {
        "metadata": {"name": "allowed", "namespace": "default"},
        "spec": {
            "nested": {
                "containers": [
                    {"env": [{"name": "PASSWORD", "value": "raw-env-password"}], "password": "hidden-spec-password"}
                ]
            }
        },
    }
    client.call_api.side_effect = [discovery("workers", kind="CustomWorker"), {"items": [obj], "metadata": {}}]
    data = module.list_resources(
        params(
            api_version="example.com/v2",
            resource="workers",
            namespace="default",
            include_sensitive=include_sensitive,
            unmask_rules=[unmask_rule(resource="workers", api_group="example.com", resource_names=[])],
        )
    )["data"]
    assert ("raw-env-password" in str(data)) is include_sensitive
    assert "hidden-spec-password" not in str(data)
    if include_sensitive:
        assert data["unmasked_count"] == 1
