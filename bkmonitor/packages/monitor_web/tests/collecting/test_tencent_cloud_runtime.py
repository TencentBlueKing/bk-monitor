"""腾讯云运行快照和部署能力，仅使用本地动态资源客户端替身。"""

import base64
import json
import re
from collections import Counter
from copy import deepcopy
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest
import yaml
from kubernetes.client.exceptions import ApiException

from core.errors.collecting import CollectConfigParamsError, LegacyConversionFailed
from monitor_web.collecting.deploy import qcloud_lifecycle as lifecycle
from monitor_web.collecting.deploy import tencent_cloud as deploy
from monitor_web.collecting.resources.tencent_cloud import configmap_projection, prepare_configmap_snapshot

from .test_tencent_cloud_configmap import upload
from .test_tencent_cloud_projection import PRODUCT, TEMPLATE, sample_config

TAG = "registry.example:5000/exporter:old"
DIGEST = "sha256:" + "1" * 64
PIN = "registry.example:5000/exporter@" + DIGEST
RESOURCES = {"limits": {"cpu": "250m", "memory": "128Mi"}, "requests": {"cpu": "30m"}}
DEPLOY_TEMPLATE = (
    TEMPLATE.split("---")[0]
    + """---
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
        - name: exporter
          image: registry.example:5000/exporter:old
          resources:
            requests: {{ values.requests | tojson }}
            limits: {{ values.limits | tojson }}
"""
)


@pytest.fixture
def legacy(settings):
    settings.K8S_PLUGIN_COLLECT_CLUSTER_ID = "test-cluster:monitoring"
    settings.BCS_CLUSTER_BK_ENV_LABEL = "test"
    contract = {
        "version": "v0.21.0",
        "products": {"QCE/REDIS": []},
        "templates": [sha256(DEPLOY_TEMPLATE.encode()).hexdigest()],
    }
    settings.TENCENT_CLOUD_EXPORTER_CONTRACTS = {
        TAG: {**contract, "digest": DIGEST, "resources": {"limits": {"cpu": "1"}}},
        PIN: deepcopy(contract),
    }
    settings.TENCENT_CLOUD_METRIC_PLUGIN_CONFIG = {"collector_json": {"template": DEPLOY_TEMPLATE}}
    return sample_config(
        DEPLOY_TEMPLATE,
        {**deepcopy(RESOURCES), "requests": {"cpu": "10m"}, "rate_limit": 20, "is_international": "false"},
        {
            "collector": {"period": 90, "timeout": 60, "metric_relabel_configs": []},
            "plugin": {
                "secret_id": "fixture-access-A",
                "secret_key": "fixture-secret-A",
                "region": "west",
                "products": yaml.safe_dump([PRODUCT]),
            },
        },
    )


@pytest.fixture
def candidate(legacy):
    source = legacy.deployment_config.plugin_version.config
    source.config_json.append({"name": "requests.cpu", "mode": "opt_cmd"})
    legacy.deployment_config.params["plugin"]["requests.cpu"] = "30m"
    projected = configmap_projection(legacy)
    projected["collector"].pop("metric_relabel_configs")
    file = projected["plugin"]["configmaps"][0]
    file.pop("preview")
    projected["plugin"]["configmaps"].append(
        upload({"credential": {"region": "east"}, "products": [PRODUCT]}, str(UUID(int=5)), "second.yaml")
    )
    return projected


def test_freeze_existing_and_new_profiles(legacy, candidate, settings):
    original = deepcopy((candidate, legacy.deployment_config.params, legacy.deployment_config.plugin_version.config))
    snapshot = prepare_configmap_snapshot(candidate, legacy)
    assert original == (candidate, legacy.deployment_config.params, legacy.deployment_config.plugin_version.config)
    assert snapshot["collector"]["metric_relabel_configs"] == []
    assert snapshot["runtime"] == {"image": PIN, "resources": RESOURCES, "contract": "qcloud-exporter-v0.21.0"}
    assert snapshot["plugin"]["access_key"] == "fixture-access-A"
    assert snapshot["plugin"]["secret_key"] == "fixture-secret-A"
    fresh = deepcopy(candidate)
    fresh["plugin"].update(access_key="new-id", secret_key="new-key")
    assert prepare_configmap_snapshot(fresh)["runtime"]["resources"] == {"limits": {"cpu": "1"}}
    legacy.deployment_config.params = snapshot
    settings.TENCENT_CLOUD_METRIC_PLUGIN_CONFIG = {}
    del settings.TENCENT_CLOUD_EXPORTER_CONTRACTS[TAG]
    del candidate["plugin"]["access_key"]
    candidate["plugin"]["secret_key"] = "new-secret"
    edited = prepare_configmap_snapshot(candidate, legacy)
    assert edited["runtime"] == snapshot["runtime"]
    assert edited["plugin"]["access_key"] == "fixture-access-A" and edited["plugin"]["secret_key"] == "new-secret"
    assert snapshot["plugin"]["secret_key"] == "fixture-secret-A"


@pytest.mark.parametrize("editing", [True, False])
@pytest.mark.parametrize("field", ["secret_key", "metric_relabel_configs"])
def test_reject_client_owned_collector_extras(legacy, candidate, editing, field):
    secret = "fixture-rotated-secret"
    candidate["plugin"].update(access_key="fixture-new-id", secret_key=secret)
    candidate["collector"][field] = secret
    with pytest.raises(CollectConfigParamsError, match="不支持的采集器参数") as err:
        prepare_configmap_snapshot(candidate, legacy if editing else None)
    assert secret not in str(err.value)
    assert secret not in json.dumps(configmap_projection(legacy))


def test_saved_snapshot_projects_only_masked_credentials(legacy, candidate):
    rules = [{"action": "drop", "regex": "ignored"}]
    legacy.deployment_config.params["collector"]["metric_relabel_configs"] = rules
    candidate["plugin"]["secret_key"] = "fixture-rotated-secret"
    candidate["collector"]["period"] = 120
    legacy.deployment_config.params = prepare_configmap_snapshot(candidate, legacy)
    detail = configmap_projection(legacy)
    assert detail["collector"] == {"period": 120, "timeout": 60, "metric_relabel_configs": rules}
    assert detail["plugin"]["secret_key"] is True and detail["plugin"]["access_key"] is True
    assert "fixture-rotated-secret" not in json.dumps(detail)


@pytest.mark.parametrize(
    "change", ["tag-only", "unknown-digest", "different-version", "different-products", "unknown-template"]
)
def test_unverified_runtime_fails(legacy, candidate, settings, change):
    contracts = settings.TENCENT_CLOUD_EXPORTER_CONTRACTS
    if change == "tag-only":
        contracts[TAG].pop("digest")
    elif change == "unknown-digest":
        del contracts[PIN]
    elif change == "different-version":
        contracts[PIN]["version"] = "v0.22.4"
    elif change == "different-products":
        contracts[PIN]["products"] = {"QCE/COS": []}
    else:
        contracts[TAG]["templates"] = []
    with pytest.raises(LegacyConversionFailed):
        prepare_configmap_snapshot(candidate, legacy)


@pytest.mark.parametrize(
    "change", ["client-runtime", "client-preview", "blank-key", "missing-new-key", "secret-in-file"]
)
def test_reject_invalid_snapshot(legacy, candidate, change):
    if change == "client-runtime":
        candidate["runtime"] = {}
    elif change == "client-preview":
        candidate["plugin"]["configmaps"][0]["preview"] = {}
    elif change == "blank-key":
        candidate["plugin"]["access_key"] = ""
    elif change == "missing-new-key":
        legacy = None
    else:
        candidate["plugin"]["configmaps"][0]["content"] += "# fixture-secret-A"
    with pytest.raises(CollectConfigParamsError) as err:
        prepare_configmap_snapshot(candidate, legacy)
    assert "fixture-secret-A" not in str(err.value)


def resources(config, params):
    return deploy.render_resources(config, params, "test-cluster", "monitoring")


def test_resources_and_routing(legacy, candidate):
    snapshot = prepare_configmap_snapshot(candidate, legacy)
    manifests = resources(legacy, snapshot)
    assert Counter(m["kind"] for m in manifests) == {
        "ConfigMap": 2,
        "Service": 2,
        "Deployment": 2,
        "Secret": 1,
        "DataID": 1,
        "ServiceMonitor": 1,
    }
    secret, monitor = manifests[0], manifests[-1]
    assert {k: base64.b64decode(v).decode() for k, v in secret["data"].items()} == {
        "access_key": "fixture-access-A",
        "secret_key": "fixture-secret-A",
    }
    release = f"bk-monitor-collector-{legacy.id}-test"
    assert secret["metadata"]["name"] == monitor["metadata"]["name"] == f"{release}-qcloud-exporter"
    for manifest in manifests:
        labels = manifest["metadata"]["labels"]
        assert labels[deploy.LABEL + "instance"] == release
        assert labels[deploy.LABEL + "plugin-id"] == legacy.plugin_id
        assert labels[deploy.LABEL + "collect-config-id"] == str(legacy.id)
        assert labels[deploy.LABEL + "bk-env"] == "test"
        assert labels[deploy.LABEL + "managed-by"] == "bk-monitor"
    rows = {(m["kind"], m["metadata"]["name"]): m for m in manifests}
    legacy.deployment_config.params = snapshot
    files = configmap_projection(legacy)["plugin"]["configmaps"]
    for file in files:
        name = next(
            m["metadata"]["name"]
            for m in manifests
            if m["kind"] == "Service" and m["metadata"]["labels"][deploy.LABEL + "file-uid"] == file["uid"]
        )
        assert name.startswith(f"{release}-qcloud-exporter-")
        assert len(name) <= 63
        doc = rows["ConfigMap", name]
        assert doc["data"] == {"qcloud.yml": file["preview"]["qcloud_yaml"]}
        creds = yaml.safe_load(doc["data"]["qcloud.yml"])["credential"]
        assert creds["access_key"] == creds["secret_key"] == ""
        pod = rows["Deployment", name]["spec"]["template"]
        selector = rows["Service", name]["spec"]["selector"]
        assert selector == pod["metadata"]["labels"] == rows["Deployment", name]["spec"]["selector"]["matchLabels"]
        assert selector[deploy.LABEL + "file-uid"] == str(UUID(file["uid"]))
        assert monitor["spec"]["selector"]["matchLabels"].items() <= selector.items()
        assert selector[deploy.LABEL + "name"] != "qcloud-exporter"
        container = pod["spec"]["containers"][0]
        assert container["image"] == PIN and container["resources"] == RESOURCES
        assert pod["spec"]["volumes"][0]["configMap"]["name"] == name
        assert container["command"][-1] == "--config.file=" + container["volumeMounts"][0]["mountPath"] + "/qcloud.yml"
        assert {e["name"]: e["valueFrom"]["secretKeyRef"] for e in container["env"]} == {
            var: {"name": secret["metadata"]["name"], "key": key} for key, var in deploy.ENV_KEYS.items()
        }
    text = json.dumps(manifests[1:])
    assert all(value not in text for value in (*secret["data"].values(), "fixture-access-A", "fixture-secret-A"))
    route = next(m for m in manifests if m["kind"] == "DataID")
    assert route["spec"]["dataID"] == legacy.data_id
    assert route["spec"]["monitorResource"] == {
        "name": monitor["metadata"]["name"],
        "namespace": "monitoring",
        "kind": "servicemonitor",
    }
    other = deepcopy(legacy)
    other.id += 1
    others = resources(other, snapshot)
    assert {m["metadata"]["name"] for m in others}.isdisjoint(m["metadata"]["name"] for m in manifests)
    assert not monitor["spec"]["selector"]["matchLabels"].items() <= others[-1]["metadata"]["labels"].items()


@pytest.mark.parametrize("env", ["", "long-env-" * 6 + "a"])
def test_names_keep_legacy_identity_and_remain_distinct(legacy, candidate, settings, env):
    snapshot = prepare_configmap_snapshot(candidate, legacy)
    settings.BCS_CLUSTER_BK_ENV_LABEL = env
    old = deploy.K8sInstaller(legacy)._get_context(legacy.deployment_config)
    assert old["release_name"] == f"bk-monitor-collector-{legacy.id}" + (f"-{env}" if env else "")

    manifests = resources(legacy, snapshot)
    names = {obj["metadata"]["name"] for obj in manifests}
    assert len(names) == 3  # 配置本身和两个文件
    assert all(re.fullmatch(r"[a-z][a-z0-9-]{0,61}[a-z0-9]", name) for name in names)
    assert old["plugin_release_name"] not in names
    if not env:
        assert manifests[0]["metadata"]["labels"][deploy.LABEL + "instance"] == old["release_name"]
    legacy.bk_tenant_id = "another-tenant"
    others = resources(legacy, snapshot)
    assert names.isdisjoint(obj["metadata"]["name"] for obj in others)
    assert manifests[-1]["spec"]["selector"] != others[-1]["spec"]["selector"]


@pytest.mark.parametrize("value", [123, None])
def test_data_id_uses_single_lookup_before_writes(legacy, candidate, value, mocker):
    snapshot = prepare_configmap_snapshot(candidate, legacy)

    class Config(SimpleNamespace):
        data_id = mocker.PropertyMock(side_effect=[value])

    config = Config(**{k: v for k, v in vars(legacy).items() if k != "data_id"})
    connection = mocker.patch.object(deploy.k8s_client, "ApiClient")
    if value is None:
        with pytest.raises(CollectConfigParamsError, match="DataID"):
            lifecycle.TencentCloudInstaller(config).reconcile(SimpleNamespace(params=snapshot, last_version=None))
        connection.assert_not_called()
    else:
        route = next(obj for obj in resources(config, snapshot) if obj["kind"] == "DataID")
        assert route["spec"]["dataID"] == value
    vars(Config)["data_id"].assert_called_once_with()


def test_repair_cross_namespace_scraping(legacy, candidate):
    monitor = resources(legacy, prepare_configmap_snapshot(candidate, legacy))[-1]
    current = deepcopy(monitor)
    current["metadata"]["resourceVersion"] = "7"
    current["spec"]["namespaceSelector"]["any"] = True
    client = Mock()
    api = client.resources.get.return_value
    api.get.return_value.to_dict.return_value = current
    deploy.apply_resource(client, monitor)
    desired = api.patch.call_args.kwargs["body"]["spec"]["namespaceSelector"]
    assert desired == {"matchNames": ["monitoring"], "any": False}
    current["spec"]["namespaceSelector"] = desired
    deploy.apply_resource(client, monitor)
    api.patch.assert_called_once()


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ("file", {"ConfigMap": 1, "Deployment": 1}),
        ("secret", {"Secret": 1, "Deployment": 2}),
        ("period", {"ServiceMonitor": 1}),
        ("rename", {}),
        ("reorder", {}),
    ],
)
def test_only_affected_resources_change(legacy, candidate, change, expected):
    snapshot = prepare_configmap_snapshot(candidate, legacy)
    before = resources(legacy, snapshot)
    files = snapshot["plugin"]["configmaps"]
    if change == "file":
        files[1]["content"] = files[1]["content"].replace("east", "south")
    elif change == "secret":
        snapshot["plugin"]["secret_key"] = "rotated-secret"
    elif change == "period":
        snapshot["collector"]["period"] = 120
    elif change == "rename":
        files[0]["filename"] = "renamed.yaml"
    else:
        files.reverse()
    after = {(m["kind"], m["metadata"]["name"]): m for m in resources(legacy, snapshot)}
    assert Counter(m["kind"] for m in before if m != after[m["kind"], m["metadata"]["name"]]) == expected


def test_create_patch_noop_conflict_and_redaction(legacy, candidate):
    manifest = resources(legacy, prepare_configmap_snapshot(candidate, legacy))[0]
    client = Mock()
    api = client.resources.get.return_value
    api.get.side_effect = ApiException(status=404)
    deploy.apply_resource(client, manifest)
    api.create.assert_called_once_with(body=manifest, namespace="monitoring")
    current = deepcopy(manifest)
    current["metadata"]["resourceVersion"] = "5"
    api.get.side_effect = None
    api.get.return_value.to_dict.return_value = current
    deploy.apply_resource(client, manifest)
    api.patch.assert_not_called()
    current["data"]["unexpected"] = "stale"
    deploy.apply_resource(client, manifest)
    patch = api.patch.call_args.kwargs["body"]
    assert patch["data"]["unexpected"] is None and patch["metadata"]["resourceVersion"] == "5"
    assert "resourceVersion" not in manifest["metadata"]
    api.patch.side_effect = ApiException(status=409, reason="fixture-secret-A")
    with pytest.raises(CollectConfigParamsError, match="409") as error:
        deploy.apply_resource(client, manifest)
    assert "fixture-secret-A" not in str(error.value)
    current["metadata"]["labels"][deploy.LABEL + "collect-config-id"] = "unrelated"
    with pytest.raises(CollectConfigParamsError, match="资源归属"):
        deploy.apply_resource(client, manifest)
    assert api.patch.call_count == 2
    api.delete.assert_not_called()


@pytest.mark.parametrize("kind", ["Service", "ServiceMonitor"])
def test_repair_selector_drift(legacy, candidate, kind):
    manifest = next(
        obj for obj in resources(legacy, prepare_configmap_snapshot(candidate, legacy)) if obj["kind"] == kind
    )
    current = json.loads(json.dumps(manifest))
    current["metadata"]["labels"]["obsolete"] = "external"
    current["metadata"]["resourceVersion"] = "7"
    selector = current["spec"]["selector"]
    if kind == "ServiceMonitor":
        selector["matchExpressions"] = [{"key": "obsolete", "operator": "Exists"}]
        selector = selector["matchLabels"]
    selector["obsolete"] = "true"
    client = Mock()
    api = client.resources.get.return_value
    api.get.return_value.to_dict.return_value = current
    deploy.apply_resource(client, manifest)
    patch = api.patch.call_args.kwargs["body"]
    assert "obsolete" not in patch["metadata"]["labels"]
    corrected = patch["spec"]["selector"]
    if kind == "ServiceMonitor":
        assert corrected["matchExpressions"] is None
        corrected = corrected["matchLabels"]
    assert corrected["obsolete"] is None


def test_deploy_preflights_all_files_before_writes(legacy, candidate, mocker):
    snapshot = prepare_configmap_snapshot(candidate, legacy)
    connection = mocker.patch.object(deploy.k8s_client, "ApiClient")
    mocker.patch.object(lifecycle.TencentCloudInstaller, "inventory", return_value=[])
    mocker.patch.object(lifecycle.dynamic, "DynamicClient")
    apply = mocker.patch.object(lifecycle, "apply_resource")
    lifecycle.TencentCloudInstaller(legacy).reconcile(SimpleNamespace(params=snapshot, last_version=None))
    assert [c.args[1]["kind"] for c in apply.call_args_list] == [
        "Secret",
        "ConfigMap",
        "Service",
        "ConfigMap",
        "Service",
        "DataID",
        "Deployment",
        "Deployment",
        "ServiceMonitor",
    ]
    apply.reset_mock()
    connection.reset_mock()
    snapshot["plugin"]["configmaps"][1]["content"] = "invalid"
    with pytest.raises(CollectConfigParamsError):
        lifecycle.TencentCloudInstaller(legacy).reconcile(SimpleNamespace(params=snapshot, last_version=None))
    connection.assert_not_called()
    apply.assert_not_called()
