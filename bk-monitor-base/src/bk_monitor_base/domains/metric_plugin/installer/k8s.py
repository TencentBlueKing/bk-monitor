import hashlib
import json
import logging
from typing import Any, final
from urllib.parse import urljoin

import yaml
from jinja2 import BaseLoader, Environment
from kubernetes import client as k8s_client
from kubernetes import dynamic as k8s_dynamic
from kubernetes.client.exceptions import ApiException as K8sApiException
from typing_extensions import override

from bk_monitor_base.config import get_config
from bk_monitor_base.domains.metric_plugin.define import (
    MetricPluginDeployment,
    MetricPluginDeploymentScope,
    MetricPluginDeploymentStatusEnum,
    MetricPluginDeploymentVersion,
)
from bk_monitor_base.domains.metric_plugin.models import (
    MetricPluginDeploymentModel,
    MetricPluginDeploymentVersionModel,
)

from .base import BaseInstaller

logger = logging.getLogger(__name__)


SERVICE_MONITOR_TEMPLATE = """
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: {{ plugin_release_name }}
  labels:
    app.kubernetes.io/name: qcloud-exporter
    app.kubernetes.io/instance: {{ plugin_release_name }}
    app.kubernetes.io/managed-by: bk-monitor
    app.kubernetes.io/plugin-id: "{{ plugin.id }}"
    {%- if bk_env %}
    app.kubernetes.io/bk-env: "{{ bk_env }}"
    {%- endif %}
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: qcloud-exporter
      app.kubernetes.io/managed-by: bk-monitor
      app.kubernetes.io/plugin-id: "{{ plugin.id }}"
      {%- if bk_env %}
      app.kubernetes.io/bk-env: "{{ bk_env }}"
      {%- endif %}
  endpoints:
    - port: http
      path: /metrics
      interval: {{ collect.period }}s
      scrapeTimeout: {{ collect.timeout }}s
      honorLabels: false
      relabelings:
        - sourceLabels:
          - "__meta_kubernetes_service_label_app_kubernetes_io_collect_config_id"
          regex: "(.*)"
          targetLabel: "bk_collect_config_id"
          replacement: "${1}"
          action: replace
        - targetLabel: "bk_biz_id"
          replacement: "{{ bk_biz_id }}"
  namespaceSelector:
    matchNames:
    - {{ namespace }}
"""

DATA_ID_TEMPLATE = """
apiVersion: monitoring.bk.tencent.com/v1beta1
kind: DataID
metadata:
  name: {{ plugin_release_name }}
  labels:
    {%- if bk_env %}
    bk_env: "{{ bk_env }}"
    {%- endif %}
    isCommon: "false"
    isSystem: "false"
    usage: metric
spec:
  dataID: {{ plugin.data_id }}
  labels:
    bcs_cluster_id: {{ cluster_id }}
    bk_biz_id: "{{ bk_biz_id }}"
  monitorResource:
    kind: servicemonitor
    namespace: {{ namespace }}
    name: {{ plugin_release_name }}
"""

_jinja_env = Environment(loader=BaseLoader(), autoescape=False)


def _jinja_render(template_str: str, context: dict[str, Any]) -> str:
    """渲染 Jinja2 模板字符串"""
    return _jinja_env.from_string(template_str).render(context)


@final
class K8sInstaller(BaseInstaller):
    """K8S 安装器

    通过 Kubernetes API 管理集群资源，实现采集配置的部署、卸载、启停等操作。

    架构设计：
    1. 根据插件+业务创建 namespace
    2. 业务下一个插件对应一个 DataID
    3. 一个采集对应一个 ServiceMonitor
    4. DataID 资源可以对应 namespace 下的所有 ServiceMonitor
    """

    def __init__(self, deployment: MetricPluginDeployment, operator: str):
        super().__init__(deployment, operator)
        self.plugin_manager = None

    @staticmethod
    def _get_cluster_from_scope(scope: MetricPluginDeploymentScope) -> tuple[str, str]:
        """从部署范围中提取 BCS 集群信息

        要求 target_scope 的 node_type 为 "bcs_cluster"，
        nodes 中第一个节点包含 bcs_cluster_id 和 namespace 字段。

        Returns:
            (cluster_id, namespace) 元组

        Raises:
            ValueError: scope 不包含有效的 BCS 集群信息
        """
        if not scope.nodes:
            raise ValueError("target_scope.nodes is empty, at least one bcs_cluster node is required")
        node = scope.nodes[0]
        cluster_id = node.get("bcs_cluster_id")
        namespace = node.get("namespace")
        if not cluster_id or not namespace:
            raise ValueError(f"target_scope node must contain 'bcs_cluster_id' and 'namespace', got: {node}")
        return str(cluster_id), str(namespace)

    def _get_k8s_config(self, cluster_id: str) -> k8s_client.Configuration:
        """通过 BCS API Gateway 构建 K8S 客户端配置"""
        bcs = get_config().blueking.bcs
        host = urljoin(
            f"{bcs.api_gateway_schema}://{bcs.api_gateway_host}:{bcs.api_gateway_port}",
            f"/clusters/{cluster_id}",
        )
        return k8s_client.Configuration(
            host=host,
            api_key={"authorization": bcs.api_gateway_token},
            api_key_prefix={"authorization": "Bearer"},
        )

    @staticmethod
    def _compare_md5(current_config: dict[str, Any], exists_config: dict[str, Any] | None) -> tuple[bool, str]:
        """比较两个配置的 MD5 值，判断是否存在差异

        Returns:
            (has_diff, current_md5) 元组
        """
        current_md5 = hashlib.md5(json.dumps(current_config, sort_keys=True).encode("utf-8")).hexdigest()

        if not exists_config:
            return True, current_md5

        exists_md5 = exists_config.get("metadata", {}).get("annotations", {}).get("app.kubernetes.io/config-md5")
        return current_md5 != exists_md5, current_md5

    @classmethod
    def _create_or_update_dynamic_resource(
        cls,
        dynamic_client: k8s_dynamic.DynamicClient,
        yaml_template: str | dict[str, Any],
        context: dict[str, Any],
    ) -> None:
        """幂等地创建或更新动态 K8S 资源

        通过 MD5 对比判断是否需要更新，无变更时跳过操作。
        """
        if isinstance(yaml_template, str):
            yaml_str = _jinja_render(yaml_template, context)
            config: dict[str, Any] = yaml.safe_load(yaml_str)
        else:
            config = yaml_template

        resource_client: Any = dynamic_client.resources.get(  # pyright: ignore[reportUnknownVariableType]
            api_version=config["apiVersion"], kind=config["kind"]
        )

        try:
            exists_config: Any = resource_client.get(  # pyright: ignore[reportUnknownVariableType]
                namespace=context["namespace"], name=config["metadata"]["name"]
            )
        except K8sApiException as e:
            if e.status != 404:
                raise
            exists_config = None

        diff, config_md5 = cls._compare_md5(config, exists_config)  # pyright: ignore[reportUnknownArgumentType]
        if not diff:
            return

        if exists_config:
            try:
                resource_client.delete(namespace=context["namespace"], name=config["metadata"]["name"])
            except K8sApiException as e:
                if e.status != 404:
                    raise

        config["metadata"].setdefault("annotations", {})["app.kubernetes.io/config-md5"] = config_md5
        try:
            resource_client.create(namespace=context["namespace"], body=config)
        except K8sApiException as e:
            if e.status != 409:
                raise

    def _create_plugin_public_resource(self, context: dict[str, Any]) -> None:
        """创建公共资源（Namespace、DataID、ServiceMonitor）"""
        cluster_id: str = context["cluster_id"]
        namespace: str = context["namespace"]

        with k8s_client.ApiClient(self._get_k8s_config(cluster_id)) as api_client:
            core_client = k8s_client.CoreV1Api(api_client)
            namespace_body = {
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {"name": namespace, "labels": {"name": namespace}},
            }
            try:
                core_client.create_namespace(body=namespace_body)
            except K8sApiException as e:
                if e.status != 409:
                    raise

            dynamic_client = k8s_dynamic.DynamicClient(api_client)
            self._create_or_update_dynamic_resource(dynamic_client, DATA_ID_TEMPLATE, context)
            self._create_or_update_dynamic_resource(dynamic_client, SERVICE_MONITOR_TEMPLATE, context)

    def _render_yaml(self, context: dict[str, Any]) -> str:
        """渲染插件模板 YAML

        Raises:
            ValueError: 插件 define 中缺少 template 字段
        """
        template = self.plugin.define.get("template")
        if not template:
            raise ValueError("template is required in plugin define")
        return _jinja_render(template, context)

    def _get_context(self, deployment_version: MetricPluginDeploymentVersion) -> dict[str, Any]:
        """构建模板渲染上下文"""
        define: dict[str, Any] = self.plugin.define
        collect_params: dict[str, Any] = deployment_version.params

        values: dict[str, Any] = dict(define.get("values") or {})

        for key, value in collect_params.get("plugin", {}).items():
            keys: list[str] = key.split(".")
            sub_value = values
            for index, sub_key in enumerate(keys):
                if index == len(keys) - 1:
                    sub_value[sub_key] = value
                    break
                if not isinstance(sub_value.get(sub_key), dict):
                    sub_value[sub_key] = {}
                sub_value = sub_value[sub_key]
            values[key] = value

        cluster_id, namespace = self._get_cluster_from_scope(deployment_version.target_scope)

        plugin_id = self.plugin.id.replace("_", "-")
        bk_env: str = get_config().blueking.bcs.cluster_bk_env_label
        if bk_env:
            release_name = f"bk-monitor-collector-{self.deployment.id}-{bk_env}"
            plugin_release_name = f"bk-monitor-plugin-{plugin_id}-{bk_env}"
        else:
            release_name = f"bk-monitor-collector-{self.deployment.id}"
            plugin_release_name = f"bk-monitor-plugin-{plugin_id}"

        data_id = self.plugin.related_params.get("data_id", 0)

        return {
            "bk_biz_id": self.deployment.bk_biz_id,
            "bk_env": bk_env,
            "release_name": release_name,
            "plugin_release_name": plugin_release_name,
            "cluster_id": cluster_id,
            "namespace": namespace,
            "values": values,
            "collect": {
                "id": self.deployment.id,
                "name": self.deployment.name,
                "version": deployment_version.version,
                "period": collect_params.get("collector", {}).get("period", 60),
                "timeout": collect_params.get("collector", {}).get("timeout", 60),
            },
            "plugin": {
                "id": self.plugin.id,
                "version": self.plugin.version_str(),
                "data_id": data_id,
            },
        }

    def _deploy(self, deployment_version: MetricPluginDeploymentVersion) -> None:
        """部署 K8S 资源"""
        context = self._get_context(deployment_version)
        cluster_id = context["cluster_id"]

        self._create_plugin_public_resource(context)

        with k8s_client.ApiClient(self._get_k8s_config(cluster_id)) as api_client:
            client = k8s_dynamic.DynamicClient(api_client)
            for config in yaml.safe_load_all(self._render_yaml(context)):
                if not config:
                    continue
                self._create_or_update_dynamic_resource(client, config, context)

    def _undeploy(self, deployment_version: MetricPluginDeploymentVersion) -> None:
        """卸载 K8S 资源"""
        context = self._get_context(deployment_version)
        cluster_id: str = context["cluster_id"]
        namespace: str = context["namespace"]

        with k8s_client.ApiClient(configuration=self._get_k8s_config(cluster_id)) as api_client:
            client = k8s_dynamic.DynamicClient(api_client)
            for config in yaml.safe_load_all(self._render_yaml(context)):
                if not config:
                    continue
                rc: Any = client.resources.get(  # pyright: ignore[reportUnknownVariableType]
                    api_version=config["apiVersion"], kind=config["kind"]
                )
                try:
                    rc.delete(namespace=namespace, name=config["metadata"]["name"])
                except K8sApiException as e:
                    if e.status != 404:
                        raise

    def _save_deployment_version(self, deployment_version: MetricPluginDeploymentVersion) -> None:
        """保存部署版本记录并更新当前版本标识"""
        deployment_model = MetricPluginDeploymentModel.objects.get(id=deployment_version.deployment_id)
        remote_scope = deployment_version.remote_scope
        MetricPluginDeploymentVersionModel.objects.update_or_create(
            bk_tenant_id=deployment_version.bk_tenant_id,
            bk_biz_id=deployment_version.bk_biz_id,
            deployment=deployment_model,
            version=deployment_version.version,
            defaults={
                "plugin_version": (
                    f"{deployment_version.plugin_version.major}.{deployment_version.plugin_version.minor}"
                ),
                "params": deployment_version.params,
                "target_node_type": deployment_version.target_scope.node_type,
                "target_nodes": deployment_version.target_scope.nodes,
                "remote_node_type": remote_scope.node_type if remote_scope else "",
                "remote_nodes": remote_scope.nodes if remote_scope else [],
                "is_current": True,
                "created_by": deployment_version.created_by,
            },
        )
        MetricPluginDeploymentVersionModel.objects.filter(
            deployment=deployment_model,
            bk_tenant_id=deployment_model.bk_tenant_id,
            bk_biz_id=deployment_model.bk_biz_id,
        ).exclude(version=deployment_version.version).update(is_current=False)

    @override
    def install(self, deployment_version: MetricPluginDeploymentVersion) -> Any:
        """安装指定部署版本

        保存版本记录后部署 K8S 资源，失败时更新部署状态为 FAILED。
        """
        if not self.deployment_version:
            self.deployment_version = self._get_current_deployment_version()

        is_modified, diff_result = self.get_version_diff(self.deployment_version, deployment_version)
        if not is_modified and self.deployment_version:
            deployment_version.version = self.deployment_version.version

        self._save_deployment_version(deployment_version)
        self.deployment_version = deployment_version

        self.deployment.status = MetricPluginDeploymentStatusEnum.DEPLOYING.value
        self._save()

        try:
            self._deploy(deployment_version)
            self.deployment.status = MetricPluginDeploymentStatusEnum.RUNNING.value
        except K8sApiException:
            logger.exception("deploy k8s resource failed for deployment %s", self.deployment.id)
            self.deployment.status = MetricPluginDeploymentStatusEnum.FAILED.value
        self._save()

        return diff_result

    @override
    def uninstall(self) -> None:
        """卸载采集配置"""
        current_version = self._get_current_deployment_version()
        if current_version:
            try:
                self._undeploy(current_version)
            except K8sApiException:
                logger.exception("undeploy k8s resource failed for deployment %s", self.deployment.id)

        MetricPluginDeploymentVersionModel.objects.filter(deployment_id=self.deployment.id).delete()

    @override
    def stop(self) -> None:
        """停止采集（卸载 K8S 资源但保留记录）"""
        self.deployment.status = MetricPluginDeploymentStatusEnum.STOPPING.value
        self._save()

        current_version = self._get_current_deployment_version()
        if current_version:
            try:
                self._undeploy(current_version)
                self.deployment.status = MetricPluginDeploymentStatusEnum.STOPPED.value
            except K8sApiException:
                logger.exception("undeploy k8s resource failed for deployment %s", self.deployment.id)
                self.deployment.status = MetricPluginDeploymentStatusEnum.FAILED.value
            self._save()

    @override
    def start(self) -> None:
        """启动采集（重新部署 K8S 资源）"""
        self.deployment.status = MetricPluginDeploymentStatusEnum.STARTING.value
        self._save()

        current_version = self._get_current_deployment_version()
        if not current_version:
            logger.warning("no current version for deployment %s, skip start", self.deployment.id)
            return

        try:
            self._deploy(current_version)
            self.deployment.status = MetricPluginDeploymentStatusEnum.RUNNING.value
        except K8sApiException:
            logger.exception("deploy k8s resource failed for deployment %s", self.deployment.id)
            self.deployment.status = MetricPluginDeploymentStatusEnum.FAILED.value
        self._save()

    @override
    def run(
        self,
        action: str | None = None,
        scope: MetricPluginDeploymentScope | None = None,
    ) -> Any:
        """主动执行部署"""
        current_version = self._get_current_deployment_version()
        if current_version:
            self._deploy(current_version)

    @override
    def retry(self, scope: MetricPluginDeploymentScope | None = None) -> Any:
        """重试部署"""
        self.deployment.status = MetricPluginDeploymentStatusEnum.DEPLOYING.value
        self._save()

        current_version = self._get_current_deployment_version()
        if not current_version:
            return

        try:
            self._deploy(current_version)
            self.deployment.status = MetricPluginDeploymentStatusEnum.RUNNING.value
        except K8sApiException:
            logger.exception("deploy k8s resource failed for deployment %s", self.deployment.id)
            self.deployment.status = MetricPluginDeploymentStatusEnum.FAILED.value
        self._save()

    @override
    def revoke(self, scope: MetricPluginDeploymentScope | None = None) -> Any:
        """K8S 类型不支持撤销操作"""
        pass

    @override
    def status(self, *args: Any, **kwargs: Any) -> Any:
        """查询采集状态

        检查 K8S 资源中 Deployment/StatefulSet 的就绪情况。

        Returns:
            包含 deployment_status 和 instance_status 的状态字典
        """
        current_version = self._get_current_deployment_version()
        if not current_version:
            return {
                "deployment_status": self.deployment.status,
                "instance_count": 0,
                "instance_status": {},
            }

        if self.deployment.status == MetricPluginDeploymentStatusEnum.STOPPED.value:
            return {
                "deployment_status": self.deployment.status,
                "instance_count": 1,
                "instance_status": {
                    "default": {
                        "status": "stopped",
                        "current_step": "",
                        "error_message": "",
                    }
                },
            }

        context = self._get_context(current_version)
        cluster_id: str = context["cluster_id"]
        namespace: str = context["namespace"]

        status_str = "success"
        error_msg = ""

        try:
            with k8s_client.ApiClient(self._get_k8s_config(cluster_id)) as api_client:
                client = k8s_dynamic.DynamicClient(api_client)

                for resource in yaml.safe_load_all(self._render_yaml(context)):
                    if not resource:
                        continue

                    api_version = resource["apiVersion"]
                    kind = resource["kind"]
                    rc: Any = client.resources.get(  # pyright: ignore[reportUnknownVariableType]
                        api_version=api_version, kind=kind
                    )

                    try:
                        result: Any = rc.get(  # pyright: ignore[reportUnknownVariableType]
                            namespace=namespace, name=resource["metadata"]["name"]
                        )
                    except K8sApiException as e:
                        status_str = "failed"
                        error_msg = f"query {kind}/{resource['metadata']['name']} status failed, {e}"
                        break

                    if kind.lower() in ("deployment", "statefulset"):
                        replicas: int = result["status"].get("replicas", 0)  # pyright: ignore[reportUnknownVariableType]
                        ready_replicas: int = result["status"].get("readyReplicas", 0)  # pyright: ignore[reportUnknownVariableType]
                        if replicas == ready_replicas:
                            continue

                        for condition in result["status"].get("conditions", []):  # pyright: ignore[reportUnknownVariableType]
                            if condition["type"] == "Progressing" and condition["status"] == "False":
                                status_str = "failed"
                                error_msg = "部署超时，请检查配置是否正确"
                                break
                        else:
                            status_str = "running"
                            error_msg = (
                                f"{kind}/{resource['metadata']['name']} is running, "
                                f"replicas: {replicas}, readyReplicas: {ready_replicas}"
                            )

                        # 非 success 状态直接退出循环
                        break
        except K8sApiException as e:
            status_str = "failed"
            error_msg = f"k8s api error: {e}"

        return {
            "deployment_status": self.deployment.status,
            "instance_count": 1,
            "instance_status": {
                "default": {
                    "status": status_str,
                    "current_step": "",
                    "error_message": error_msg,
                }
            },
        }
