"""通过保存和生命周期入口回放旧模板，不访问集群。"""

from contextlib import nullcontext
from copy import deepcopy
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from kubernetes.client.exceptions import ApiException

from core.errors.collecting import CollectConfigParamsError, CollectConfigVersionChanged
from monitor_web.collecting import tencent_cloud as definitions
from monitor_web.collecting.constant import OperationResult, OperationType
from monitor_web.collecting.deploy import get_collect_installer, qcloud_lifecycle as lifecycle
from monitor_web.collecting.deploy.k8s import resource_identity
from monitor_web.collecting.resources import backend, tencent_cloud
from .test_tencent_cloud_runtime import DEPLOY_TEMPLATE, PIN, TAG, legacy, candidate  # noqa: F401

OLD_META = """metadata:
  name: {{ release_name }}-qcloud-exporter
  labels:
    app.kubernetes.io/name: qcloud-exporter
    app.kubernetes.io/instance: {{ release_name }}
    app.kubernetes.io/managed-by: bk-monitor
    app.kubernetes.io/plugin-id: "{{ plugin.id }}"
    app.kubernetes.io/collect-config-id: "{{ collect.id }}"
    app.kubernetes.io/bk-env: "{{ bk_env }}"
"""
OLD_TEMPLATE = (
    DEPLOY_TEMPLATE.replace(
        "kind: ConfigMap\n",
        "kind: ConfigMap\n" + OLD_META.replace("exporter\n  labels", "exporter-{{ collect.version }}\n  labels"),
    ).replace("kind: Deployment\n", "kind: Deployment\n" + OLD_META)
    + "---\napiVersion: v1\nkind: Service\n"
    + OLD_META
    + "---\napiVersion: v1\nkind: ServiceAccount\n"
    + OLD_META.replace("/plugin-id", "/bk-plugin-id").replace("/collect-config-id", "/bk-collect-config-id")
)


class Cluster:
    def __init__(self):
        self.objects = {}
        self.actions = []
        self.resources = self
        self.failure = None
        self.terminating = set()

    def put(self, body):
        doc = deepcopy(body)
        key = resource_identity(doc)
        doc["metadata"].update(uid="/".join(key), resourceVersion="1", generation=1)
        self.objects[key] = doc

    def get(self, api_version, kind):
        cluster = self

        def read(namespace, name=None, label_selector=None):
            if name is None:
                labels = dict(s.split("=", 1) for s in label_selector.split(","))
                docs = [
                    o
                    for (api, k, _), o in cluster.objects.items()
                    if api == api_version
                    and k == kind
                    and all(o["metadata"]["labels"].get(k) == v for k, v in labels.items())
                ]
                return Mock(to_dict=lambda: {"items": deepcopy(docs)})
            key = (api_version, kind, name)
            if key in cluster.terminating:
                cluster.terminating.remove(key)
                del cluster.objects[key]
                cluster.actions.append(("exited", kind, name))
            if key not in cluster.objects:
                raise ApiException(status=404)
            return Mock(to_dict=lambda: deepcopy(cluster.objects[key]))

        def create(namespace, body):
            if cluster.failure == kind:
                raise ApiException(status=503, reason="sensitive-upstream-error")
            cluster.actions.append(("create", kind, body["metadata"]["name"]))
            assert resource_identity(body) not in cluster.objects
            cluster.put(body)

        def patch(namespace, name, body, content_type):
            assert body["metadata"]["resourceVersion"] == "1"
            cluster.actions.append(("patch", kind, name))
            cluster.put(body)

        def delete(namespace, name, body):
            key = (api_version, kind, name)
            assert body["preconditions"]["uid"] == cluster.objects[key]["metadata"]["uid"]
            cluster.actions.append(("delete", kind, name))
            if kind == "Deployment":
                assert body["propagationPolicy"] == "Foreground"
                cluster.terminating.add(key)
            else:
                del cluster.objects[key]

        return SimpleNamespace(get=read, create=create, patch=patch, delete=delete)


@pytest.fixture
def scene(legacy, candidate, settings, mocker):  # noqa: F811
    cfg = legacy
    cfg.pk = cfg.id
    cfg.allow_rollback = True
    cfg.last_operation = OperationType.EDIT
    cfg.operation_result = OperationResult.SUCCESS
    old = cfg.deployment_config
    old.pk = old.id
    old.parent_id = 0
    old.config_meta_id = cfg.id
    old.last_version = None
    cfg.plugin.packaged_release_version = old.plugin_version
    cfg.save = Mock(side_effect=lambda **kw: setattr(cfg, "deployment_config_id", cfg.deployment_config.pk))
    versions = {old.id: old}

    def record(**params):
        parent = versions.get(params["parent_id"])
        pk = max(versions) + 1
        version = SimpleNamespace(pk=pk, id=pk, last_version=parent, **params)
        versions[pk] = version
        return version

    old.plugin_version.config.collector_json["template"] = OLD_TEMPLATE
    mocker.patch.object(definitions, "LEGACY_TEMPLATE_SHA256", sha256(OLD_TEMPLATE.strip().encode()).hexdigest())
    settings.TENCENT_CLOUD_METRIC_PLUGIN_CONFIG["collector_json"]["template"] = OLD_TEMPLATE.replace(TAG, PIN)
    candidate["plugin"]["configmaps"] = candidate["plugin"]["configmaps"][:1]
    cluster = Cluster()
    mocker.patch.object(lifecycle.transaction, "atomic", side_effect=nullcontext)
    mocker.patch.object(lifecycle.CollectConfigMeta.objects, "select_for_update").return_value.get.return_value = cfg
    mocker.patch.object(lifecycle.CollectConfigMeta.objects, "get", return_value=cfg)
    mocker.patch.object(lifecycle.CollectConfigMeta.objects, "select_related").return_value.get.return_value = cfg
    mocker.patch.object(lifecycle.DeploymentConfigVersion.objects, "create", side_effect=record)
    mocker.patch.object(lifecycle.DeploymentConfigVersion.objects, "filter").return_value.values_list.side_effect = (
        lambda *a, **kw: [v.params for v in versions.values() if v.parent_id == old.pk]
    )
    mocker.patch.object(lifecycle.TencentCloudInstaller, "client", side_effect=lambda *_: nullcontext(cluster))
    installer = get_collect_installer(cfg)
    for obj in installer.legacy_manifests(old, "monitoring"):
        cluster.put(obj)
    for kind, api in [("ServiceMonitor", "monitoring.coreos.com/v1"), ("DataID", "monitoring.bk.tencent.com/v1beta1")]:
        cluster.put({"apiVersion": api, "kind": kind, "metadata": {"name": "shared-plugin", "labels": {}}})
    handler = backend.SaveCollectConfigResource()
    mocker.patch.object(handler, "after_save", side_effect=lambda config, plugin, result: result)
    mocker.patch.object(handler, "get_collector_plugin", side_effect=AssertionError("edit must use source plugin"))

    def save(params=None, source=None):
        return handler.perform_request(
            dict(
                params=deepcopy(candidate if params is None else params),
                id=cfg.id,
                bk_biz_id=cfg.bk_biz_id,
                plugin_id=cfg.plugin_id,
                collect_type="K8S",
                target_node_type="CLUSTER",
                target_object_type="CLUSTER",
                target_nodes=[],
                operation="EDIT",
                name=cfg.name,
                deployment_id=cfg.deployment_config_id if source is None else source,
            )
        )

    return SimpleNamespace(
        cfg=cfg, cluster=cluster, versions=versions, old=old, save=save, params=candidate, installer=installer
    )


def test_first_save_exits_old_before_start_then_repeated_save(scene):
    s = scene
    shared = {k: deepcopy(v) for k, v in s.cluster.objects.items() if k[-1] == "shared-plugin"}
    original = deepcopy(s.old.params)
    first = s.save()
    assert first == {"id": s.cfg.pk, "deployment_id": s.old.pk + 1, "can_rollback": True}
    assert s.cfg.deployment_config.parent_id == s.old.pk and s.old.params == original
    events = s.cluster.actions
    assert next(i for i, e in enumerate(events) if e[:2] == ("exited", "Deployment")) < next(
        i for i, e in enumerate(events) if e[:2] == ("create", "Deployment")
    )
    names = set(s.cluster.objects)
    assert len([k for k in names if k[1] == "Deployment"]) == 1
    assert {k: s.cluster.objects[k] for k in shared} == shared
    assert not any(k[1] == "ServiceAccount" for k in names)
    events.clear()
    s.cfg.operation_result = OperationResult.SUCCESS
    second = s.save()
    assert s.cfg.deployment_config.parent_id == first["deployment_id"] and second["id"] == first["id"]
    assert set(s.cluster.objects) == names and events == []
    with pytest.raises(CollectConfigVersionChanged):
        s.save(source=s.old.pk)
    assert len(s.versions) == 3 and events == []


def test_failed_submit_retry_and_stop_start_rollback(scene):
    s = scene
    s.cluster.failure = "Deployment"
    with pytest.raises(lifecycle.CollectConfigDeployError) as exc:
        s.save()
    version = s.cfg.deployment_config
    assert exc.value.data["deployment_id"] == version.pk and exc.value.data["id"] == s.cfg.id
    assert exc.value.code == 3311016 and exc.value.data["files"][0]["uid"] == s.params["plugin"]["configmaps"][0]["uid"]
    assert "sensitive" not in str(exc.value) and s.cfg.operation_result == OperationResult.FAILED
    s.cluster.failure = None
    s.installer.retry()
    assert len(s.versions) == 2 and s.cfg.deployment_config == version
    s.installer.stop()
    assert all(k[-1] == "shared-plugin" for k in s.cluster.objects)
    s.installer.retry()
    assert all(k[-1] == "shared-plugin" for k in s.cluster.objects)
    s.installer.start()
    assert len([k for k in s.cluster.objects if k[1] == "Deployment"]) == 1
    s.cfg.last_operation = OperationType.EDIT
    before = deepcopy(s.old.params)
    assert s.installer.rollback()["deployment_id"] == s.old.pk
    deployments = [obj for key, obj in s.cluster.objects.items() if key[1] == "Deployment"]
    assert len(deployments) == 1 and deployments[0]["metadata"]["labels"][lifecycle.LABEL + "name"] == "qcloud-exporter"
    assert deployments[0]["spec"]["template"]["spec"]["containers"][0]["image"] == PIN
    assert s.cfg.deployment_config == s.old and s.old.params == before
    assert not any(key[1] == "Secret" for key in s.cluster.objects)


def test_static_validation_and_unowned_name(scene):
    s = scene
    params = deepcopy(s.params)
    params["plugin"]["configmaps"][0]["content"] = "bad"
    with pytest.raises(CollectConfigParamsError):
        s.save(params)
    assert len(s.versions) == 1 and not s.cluster.actions
    old_dep = next(obj for k, obj in s.cluster.objects.items() if k[1] == "Deployment")
    old_dep["metadata"]["labels"][lifecycle.LABEL + "collect-config-id"] = "other"
    with pytest.raises(lifecycle.CollectConfigDeployError, match="归属冲突"):
        s.save()
    assert not s.cluster.actions and resource_identity(old_dep) in s.cluster.objects


def test_upgrade_and_generation_status(scene, mocker):
    s = scene
    s.cfg.plugin.current_version = SimpleNamespace(info=SimpleNamespace(metric_json=[]))
    mocker.patch.object(backend.append_metric_list_cache, "delay")
    result = backend.UpgradeCollectPluginResource().perform_request(
        dict(id=s.cfg.id, bk_biz_id=s.cfg.bk_biz_id, deployment_id=s.old.id, realtime=False, params=deepcopy(s.params))
    )
    assert result["deployment_id"] == s.cfg.deployment_config_id and s.cfg.last_operation == OperationType.UPGRADE
    pod = next(obj for k, obj in s.cluster.objects.items() if k[1] == "Deployment")
    pod["status"] = {k: 1 for k in ("replicas", "readyReplicas", "updatedReplicas", "availableReplicas")}
    pod["status"]["observedGeneration"] = 0

    def status():
        return s.installer.status()[0]["child"][0]["status"]

    assert status() == "RUNNING"
    pod["status"]["observedGeneration"] = 1
    assert status() == "SUCCESS"
    pod["status"]["conditions"] = [{"type": "Progressing", "status": "False"}]
    assert status() == "FAILED"


def test_clone_rebuilds_identity_without_credentials(scene):
    s = scene
    s.save()
    clone = tencent_cloud.clone_snapshot(s.cfg)
    assert clone["plugin"]["access_key"] == clone["plugin"]["secret_key"] == ""
    assert clone["plugin"]["configmaps"][0]["uid"] != s.cfg.deployment_config.params["plugin"]["configmaps"][0]["uid"]
    assert clone["runtime"]["resources"] != s.cfg.deployment_config.params["runtime"]["resources"]


def test_delete_retries_failed_stop_before_removing_database_record(scene, mocker):
    s = scene
    s.save()
    end = mocker.patch.object(lifecycle.K8sInstaller, "uninstall")
    dep = next(obj for key, obj in s.cluster.objects.items() if key[1] == "Deployment")
    labels = dep["metadata"]["labels"]
    labels[lifecycle.LABEL + "plugin-id"] = "external"
    with pytest.raises(lifecycle.CollectConfigDeployError):
        s.installer.stop()
    with pytest.raises(lifecycle.CollectConfigDeployError):
        s.installer.uninstall()
    end.assert_not_called()
    labels[lifecycle.LABEL + "plugin-id"] = s.cfg.plugin_id
    s.installer.uninstall()
    assert all(key[-1] == "shared-plugin" for key in s.cluster.objects)
    end.assert_called_once()


@pytest.mark.django_db(transaction=True, databases=["default", "monitor_api"])
def test_competing_edits_commit_one_version(legacy, candidate, settings, mocker):  # noqa: F811
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from django.db import connections
    from monitor_web.models import CollectorPluginConfig, CollectorPluginInfo, CollectorPluginMeta, PluginVersionHistory
    from monitor_web.models.collecting import CollectConfigMeta, DeploymentConfigVersion

    definition = legacy.deployment_config.plugin_version.config
    definition.collector_json["template"] = OLD_TEMPLATE
    mocker.patch.object(definitions, "LEGACY_TEMPLATE_SHA256", sha256(OLD_TEMPLATE.strip().encode()).hexdigest())
    plugin = CollectorPluginMeta.objects.create(
        plugin_id=legacy.plugin_id, bk_biz_id=legacy.bk_biz_id, plugin_type="K8S"
    )
    release = PluginVersionHistory.objects.create(
        plugin_id=plugin.plugin_id,
        stage="release",
        config_version=1,
        info_version=1,
        config=CollectorPluginConfig.objects.create(
            config_json=definition.config_json, collector_json=definition.collector_json
        ),
        info=CollectorPluginInfo.objects.create(),
    )
    old = DeploymentConfigVersion.objects.create(
        plugin_version=release, config_meta_id=0, params=legacy.deployment_config.params, target_node_type="CLUSTER"
    )
    cfg = CollectConfigMeta.objects.create(
        plugin_id=plugin.plugin_id,
        bk_biz_id=plugin.bk_biz_id,
        name="sample",
        deployment_config=old,
        target_object_type="CLUSTER",
        collect_type="K8S",
        last_operation="EDIT",
        operation_result="SUCCESS",
    )
    old.config_meta_id = cfg.pk
    old.save()
    mocker.patch.object(CollectConfigMeta, "data_id", new=property(lambda self: 1))
    cluster = Cluster()
    mocker.patch.object(lifecycle.TencentCloudInstaller, "client", side_effect=lambda *_: nullcontext(cluster))
    installer = get_collect_installer(cfg)
    for manifest in installer.legacy_manifests(old, "monitoring"):
        cluster.put(manifest)
    barrier = Barrier(2)

    def save_same_parent():
        try:
            source = CollectConfigMeta.objects.get(pk=cfg.pk)
            barrier.wait(timeout=10)
            data = {"params": deepcopy(candidate), "deployment_id": old.pk}
            try:
                return tencent_cloud.save_configmap(data, source)[1]["deployment_id"]
            except CollectConfigVersionChanged:
                return None
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        versions = list(pool.map(lambda _: save_same_parent(), range(2)))
    cfg.refresh_from_db()
    assert sorted(v for v in versions if v is not None) == [cfg.deployment_config_id]
    assert cfg.deployment_config.parent_id == old.pk and cfg.deployment_config.params["runtime"]["image"] == PIN
    assert DeploymentConfigVersion.objects.filter(config_meta_id=cfg.pk).count() == 2
    assert not any(
        key[1] == "Deployment" and doc["metadata"]["labels"][lifecycle.LABEL + "name"] == "qcloud-exporter"
        for key, doc in cluster.objects.items()
    )

    # 已迁移配置的直接克隆入口不能复制密钥和部署关系，也不能立即运行。
    mocker.patch.object(
        backend.resource.collecting,
        "collect_config_detail",
        return_value={"collect_type": "K8S", "id": cfg.pk, "bk_biz_id": cfg.bk_biz_id},
    )
    backend.CloneCollectConfigResource().perform_request({"id": cfg.pk, "bk_biz_id": cfg.bk_biz_id})
    clone = CollectConfigMeta.objects.get(name=cfg.name + "_copy", bk_biz_id=cfg.bk_biz_id)
    assert clone.last_operation == OperationType.STOP
    cloned_version = clone.deployment_config
    assert cloned_version.parent_id == 0 and cloned_version.config_meta_id == clone.pk
    assert cloned_version.params["plugin"]["secret_key"] == cloned_version.params["plugin"]["access_key"] == ""
    assert (
        cloned_version.params["plugin"]["configmaps"][0]["uid"]
        != cfg.deployment_config.params["plugin"]["configmaps"][0]["uid"]
    )

    # 新建入口先验证凭据和文件，再取得业务插件并首次部署。
    create = backend.SaveCollectConfigResource()
    lookup = mocker.patch.object(create, "get_collector_plugin", return_value=plugin)
    mocker.patch.object(create, "after_save", side_effect=lambda config, plugin, result: result)
    data = dict(
        bk_biz_id=cfg.bk_biz_id,
        plugin_id=plugin.plugin_id,
        collect_type="K8S",
        target_node_type="CLUSTER",
        target_object_type="CLUSTER",
        target_nodes=[],
        name="fresh",
        params=deepcopy(candidate),
        label="os",
    )
    with pytest.raises(CollectConfigParamsError):
        create.perform_request(data)
    lookup.assert_not_called()
    data["params"]["plugin"].update(access_key="fixture-new-id", secret_key="fixture-new-secret")
    result = create.perform_request(data)
    fresh = CollectConfigMeta.objects.get(pk=result["id"])
    assert fresh.pk not in (cfg.pk, clone.pk) and fresh.deployment_config.parent_id == 0
    assert fresh.deployment_config.config_meta_id == fresh.pk and not result["can_rollback"]
    lookup.assert_called_once()
