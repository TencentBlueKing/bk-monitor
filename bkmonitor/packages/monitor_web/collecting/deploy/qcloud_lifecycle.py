"""腾讯云新规格复用 K8S 部署版本链，在同一采集配置内切换资源。"""

from contextlib import contextmanager
from functools import wraps
from time import monotonic, sleep

import yaml
from django.conf import settings
from django.db import transaction
from kubernetes import client as k8s_client
from kubernetes import dynamic
from kubernetes.client.exceptions import ApiException

from bkmonitor.utils.request import get_request_tenant_id
from core.errors.collecting import (
    CollectConfigDeployError,
    CollectConfigNotExist,
    CollectConfigParamsError,
    CollectConfigVersionChanged,
    CollectConfigRollbackError,
)
from monitor_web.collecting.constant import OperationResult, OperationType
from monitor_web.collecting.deploy.k8s import K8sInstaller, collector_release_name, resource_identity, stale_resources
from monitor_web.collecting.deploy.tencent_cloud import (
    LABEL,
    apply_resource,
    ownership_labels,
    render_resources,
    file_resources,
    resource_name,
    release_name,
)
from monitor_web.collecting.tencent_cloud import ConfigLoader
from monitor_web.models import CollectConfigMeta, DeploymentConfigVersion


def locked(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        failure = None
        with transaction.atomic():
            self.lock_current()
            try:
                return method(self, *args, **kwargs)
            except CollectConfigDeployError as exc:
                # 先提交 FAILED 状态，再交给 Resource 返回业务异常。
                failure = exc
        raise failure

    return call


class TencentCloudInstaller(K8sInstaller):
    def lock_current(self):
        config = self.collect_config
        if not config.pk:
            return
        try:
            current = CollectConfigMeta.objects.select_for_update().get(
                pk=config.pk, bk_biz_id=config.bk_biz_id, bk_tenant_id=get_request_tenant_id()
            )
        except CollectConfigMeta.DoesNotExist:
            raise CollectConfigNotExist(msg="") from None
        if current.deployment_config_id != config.deployment_config_id:
            raise CollectConfigVersionChanged()
        self.collect_config = current

    @locked
    def apply_current(self, operation, recover):
        if self.collect_config.last_operation != operation:
            raise CollectConfigVersionChanged()
        self.operation(self.collect_config.deployment_config, recover=recover)

    @locked
    def install(self, install_config, operation=None):
        # 兼容旧表单；等待锁期间若已升级，禁止旧参数覆盖新版本。
        if self.collect_config.pk and "runtime" in self.collect_config.deployment_config.params:
            raise CollectConfigParamsError(msg="请刷新并使用 ConfigMap 表单")
        name = install_config.get("name")
        if name is not None:
            self.collect_config.name = name
        return super().install(install_config, operation)

    @locked
    def upgrade(self, params):
        if "runtime" in self.collect_config.deployment_config.params:
            raise CollectConfigParamsError(msg="请刷新并使用 ConfigMap 表单")
        return super().upgrade(params)

    def managed(self, version):
        if "runtime" in version.params:
            return True
        # 回滚后仍需清理失败迁移遗留的文件资源，部署内容按目标旧版本生成。
        children = DeploymentConfigVersion.objects.filter(config_meta_id=self.collect_config.pk, parent_id=version.pk)
        return any("runtime" in params for params in children.values_list("params", flat=True))

    @contextmanager
    def client(self, cluster):
        with k8s_client.ApiClient(self._get_k8s_config(cluster)) as api:
            yield dynamic.DynamicClient(api)

    def manifests(self, version, cluster, namespace):
        config = self.collect_config
        if "runtime" in version.params:
            return render_resources(config, version.params, cluster, namespace, version)
        return self.legacy_manifests(version, namespace)

    def legacy_manifests(self, version, namespace):
        _, rendered = self.render_snapshot(version)
        docs = [doc for doc in yaml.load_all(rendered, Loader=ConfigLoader) if doc]
        for doc in docs:
            expected = self.legacy_owner(doc["kind"])
            if not all(doc["metadata"].get("labels", {}).get(k) == v for k, v in expected.items()):
                raise CollectConfigParamsError(msg="历史模板缺少匹配的采集配置归属")
            doc["metadata"]["namespace"] = namespace
        return docs

    def legacy_owner(self, kind):
        if kind not in {"Deployment", "ConfigMap", "Service", "ServiceAccount"}:
            raise CollectConfigParamsError(msg="历史模板含非配置级资源，无法安全迁移")
        prefix = "bk-" if kind == "ServiceAccount" else ""
        config = self.collect_config
        env = settings.BCS_CLUSTER_BK_ENV_LABEL
        return {
            LABEL + "name": "qcloud-exporter",
            LABEL + "managed-by": "bk-monitor",
            LABEL + "instance": collector_release_name(config.pk, env),
            LABEL + prefix + "collect-config-id": str(config.pk),
            LABEL + prefix + "plugin-id": config.plugin_id,
        }

    def previous_resources(self, version, namespace):
        """从版本链取得旧资源身份；新版文件的删除不依赖文件解析或凭据。"""
        if version and "runtime" not in version.params:
            yield from self.legacy_manifests(version, namespace)
        config = self.collect_config
        labels = ownership_labels(config)
        name = resource_name(f"{release_name(config)}-qcloud-exporter")
        for api, kind in (
            ("v1", "Secret"),
            ("monitoring.coreos.com/v1", "ServiceMonitor"),
            ("monitoring.bk.tencent.com/v1beta1", "DataID"),
        ):
            yield {"apiVersion": api, "kind": kind, "metadata": {"name": name, "labels": labels}}
        if version and "runtime" in version.params:
            for _, name, file_labels in file_resources(config, version.params["plugin"]["configmaps"], labels):
                for api, kind in (
                    ("v1", "ConfigMap"),
                    ("v1", "Service"),
                    ("apps/v1", "Deployment"),
                    ("v1", "ServiceAccount"),
                ):
                    yield {"apiVersion": api, "kind": kind, "metadata": {"name": name, "labels": file_labels}}

    def inventory(self, client, namespace):
        """取本配置实际持有的对象，补齐失败、重试、回滚历史分支的差集。"""
        owner = ownership_labels(self.collect_config)
        for api, kind in (("apps/v1", "Deployment"), ("v1", "ConfigMap"), ("v1", "Service"), ("v1", "ServiceAccount")):
            owners = [owner]
            owners.append(self.legacy_owner(kind))
            for expected in owners:
                selector = ",".join(f"{key}={value}" for key, value in expected.items())
                objects = client.resources.get(api_version=api, kind=kind).get(
                    namespace=namespace, label_selector=selector
                )
                for obj in objects.to_dict()["items"]:
                    if all(obj["metadata"].get("labels", {}).get(k) == v for k, v in expected.items()):
                        yield {"apiVersion": api, "kind": kind, "metadata": obj["metadata"]}

    def delete_owned(self, client, doc, namespace):
        api, kind, name = resource_identity(doc)
        endpoint = client.resources.get(api_version=api, kind=kind)
        try:
            current = endpoint.get(namespace=namespace, name=name).to_dict()["metadata"]
            expected = {k: v for k, v in doc["metadata"]["labels"].items() if k.startswith(LABEL)}
            if any(current.get("labels", {}).get(k) != v for k, v in expected.items()):
                raise CollectConfigParamsError(msg=f"{kind}/{name} 归属冲突")
            endpoint.delete(
                namespace=namespace,
                name=name,
                body={
                    "propagationPolicy": "Foreground",
                    "preconditions": {"uid": current["uid"], "resourceVersion": current["resourceVersion"]},
                },
            )
            if kind == "Deployment":
                deadline = monotonic() + 30
                while monotonic() < deadline:
                    endpoint.get(namespace=namespace, name=name)
                    sleep(0.25)
                raise CollectConfigParamsError(msg=f"{kind}/{name} 等待旧工作负载退出超时")
        except ApiException as exc:
            if exc.status != 404:
                raise

    def reconcile(self, version, stopping=False, recover=True):
        cluster, namespace = self._get_default_cluster()
        desired = [] if stopping else self.manifests(version, cluster, namespace)
        prior = version if stopping or "runtime" not in version.params else version.last_version
        previous = {resource_identity(doc): doc for doc in self.previous_resources(prior, namespace)}
        with self.client(cluster) as client:
            if recover:
                for doc in self.inventory(client, namespace):
                    previous.setdefault(resource_identity(doc), doc)
            desired_ids = {resource_identity(doc) for doc in desired}
            for doc in sorted(stale_resources(previous.values(), desired_ids), key=lambda d: d["kind"] != "Deployment"):
                self.delete_owned(client, doc, namespace)
            for doc in desired:
                try:
                    apply_resource(client, doc)
                except CollectConfigParamsError as exc:
                    uid = doc["metadata"]["labels"].get(LABEL + "file-uid")
                    errors = [{"path": doc["kind"], "message": str(exc)}]
                    data = {"files": [{"uid": uid, "errors": errors}]} if uid else {"errors": errors}
                    raise CollectConfigParamsError(msg=str(exc), data=data) from None

    def operation(self, version, stopping=False, recover=True):
        try:
            self.reconcile(version, stopping, recover)
        except Exception as exc:
            # SDK 异常可能携带 Secret、旧 ConfigMap 或动态客户端的请求体。
            config = self.collect_config
            config.operation_result = OperationResult.FAILED
            config.save(update_fields=["operation_result"])
            detail = str(exc) if isinstance(exc, CollectConfigParamsError) else "集群资源操作失败"
            raise CollectConfigDeployError(
                msg=detail,
                data={
                    "id": config.pk,
                    "deployment_id": version.pk,
                    "can_rollback": bool(version.parent_id) and config.allow_rollback,
                    "status": "FAILED",
                    **(
                        exc.data
                        if isinstance(exc, CollectConfigParamsError) and exc.data
                        else {"errors": [{"path": "resources", "message": detail}]}
                    ),
                },
            ) from None

    def _deploy(self, target_version):
        if self.managed(target_version):
            return self.operation(target_version)
        return super()._deploy(target_version)

    def _undeploy(self, target_version=None):
        version = target_version or self.collect_config.deployment_config
        if self.managed(version):
            return self.operation(version, stopping=True)
        return super()._undeploy(target_version)

    start = locked(K8sInstaller.start)
    stop = locked(K8sInstaller.stop)

    @locked
    def rollback(self, target_version=None):
        parent = self.collect_config.deployment_config.last_version
        if (
            not parent
            or parent.config_meta_id != self.collect_config.pk
            or (target_version is not None and getattr(target_version, "pk", target_version) != parent.pk)
        ):
            raise CollectConfigRollbackError(msg="无可回滚的源版本")
        return super().rollback(parent)

    @locked
    def retry(self, instance_ids=None):
        if self.collect_config.last_operation == OperationType.STOP and self.managed(
            self.collect_config.deployment_config
        ):
            self._undeploy()
            self.collect_config.operation_result = OperationResult.SUCCESS
            self.collect_config.save(update_fields=["operation_result"])
            return
        return super().retry(instance_ids)

    @locked
    def run(self, action=None, scope=None):
        if self.collect_config.last_operation == OperationType.STOP:
            raise CollectConfigParamsError(msg="停用状态不能下发")
        return super().run(action, scope)

    @locked
    def uninstall(self):
        if self.collect_config.last_operation == OperationType.STOP and self.managed(
            self.collect_config.deployment_config
        ):
            self._undeploy()
        return super().uninstall()

    def status(self, *args, **kwargs):
        config = self.collect_config
        version = config.deployment_config
        if not self.managed(version):
            return super().status(*args, **kwargs)
        if config.operation_result == OperationResult.FAILED:
            return self._status_result("FAILED", "资源操作失败")
        if config.last_operation == OperationType.STOP:
            return self._status_result("SUCCESS", "")
        cluster, namespace = self._get_default_cluster()
        state = "SUCCESS"
        try:
            with self.client(cluster) as client:
                for doc in self.previous_resources(version, namespace):
                    api, kind, name = resource_identity(doc)
                    if kind != "Deployment":
                        continue
                    try:
                        result = (
                            client.resources.get(api_version=api, kind=kind)
                            .get(namespace=namespace, name=name)
                            .to_dict()
                        )
                    except ApiException as exc:
                        if exc.status != 404:
                            raise
                        state = "RUNNING"
                        continue
                    status = result.get("status") or {}
                    if status.get("observedGeneration") != result["metadata"].get("generation") or not status.get(
                        "observedGeneration"
                    ):
                        state = "RUNNING"
                    elif any(
                        c["type"] == "Progressing" and c["status"] == "False" for c in status.get("conditions", [])
                    ):
                        return self._status_result("FAILED", f"Deployment/{name} 部署失败")
                    elif any(
                        status.get(k, 0) != result.get("spec", {}).get("replicas", 1)
                        for k in ("replicas", "updatedReplicas", "readyReplicas", "availableReplicas")
                    ):
                        state = "RUNNING"
        except ApiException as exc:
            return self._status_result("FAILED", f"资源查询 HTTP {exc.status}")
        return self._status_result(state, "")
