"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2024 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import hashlib
import json
import logging
from typing import Any
from urllib.parse import urljoin

import yaml
from django.conf import settings
from django.utils.translation import gettext as _
from kubernetes import client as k8s_client
from kubernetes import dynamic as k8s_dynamic

from bkmonitor.utils.template import jinja_render
from constants.cmdb import TargetNodeType
from core.errors.collecting import (
    CollectConfigRollbackError,
    DeleteCollectConfigError,
    ToggleConfigStatusError,
)
from monitor_web.collecting.constant import OperationResult, OperationType
from monitor_web.models.collecting import DeploymentConfigVersion
from monitor_web.models.plugin import PluginVersionHistory

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


class K8sInstaller(BaseInstaller):
    """
    k8s安装器

    1. 根据插件+业务创建namespace
    2. 业务下的一个插件对应一个dataid
    3. 一个采集对应一个servicemonitor
    4. dataid资源可以对应namespace下的所有servicemonitor
    """

    def _get_default_cluster(self) -> tuple[str, str]:
        """
        获取默认集群信息
        """
        if not settings.K8S_PLUGIN_COLLECT_CLUSTER_ID:
            raise ValueError("K8S_PLUGIN_COLLECT_CLUSTER_ID is required, contact administrator")

        cluster_id, namespace = settings.K8S_PLUGIN_COLLECT_CLUSTER_ID.split(":")
        return cluster_id, namespace

    @staticmethod
    def _get_k8s_config(cluster_id: str) -> k8s_client.Configuration:
        """
        获取k8s配置
        """
        host = urljoin(
            f"{settings.BCS_API_GATEWAY_SCHEMA}://{settings.BCS_API_GATEWAY_HOST}:{settings.BCS_API_GATEWAY_PORT}",
            f"/clusters/{cluster_id}",
        )
        config = k8s_client.Configuration(
            host=host,
            api_key={"authorization": settings.BCS_API_GATEWAY_TOKEN},
            api_key_prefix={"authorization": "Bearer"},
        )
        return config

    @staticmethod
    def _compare_md5(current_config: dict[str, Any], exists_config: dict[str, Any]) -> tuple[bool, str]:
        """
        比较两个配置的MD5值是否相等
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
    ):
        """
        创建或更新动态资源配置
        """
        # 渲染yaml配置
        if isinstance(yaml_template, str):
            yaml_str: str = jinja_render(yaml_template, context)
            config: dict[str, Any] = yaml.load(yaml_str, Loader=yaml.FullLoader)
        else:
            config = yaml_template

        resource_client = dynamic_client.resources.get(api_version=config["apiVersion"], kind=config["kind"])

        # 查询已存在的配置
        try:
            exists_config = resource_client.get(namespace=context["namespace"], name=config["metadata"]["name"])
        except k8s_client.exceptions.ApiException as e:
            if e.status != 404:
                raise e
            exists_config = None

        # 比较配置MD5值
        diff, config_md5 = cls._compare_md5(config, exists_config)
        if not diff:
            return

        # 删除旧的配置
        if exists_config:
            try:
                resource_client.delete(namespace=context["namespace"], name=config["metadata"]["name"])
            except k8s_client.exceptions.ApiException as e:
                if e.status != 404:
                    raise e

        # 创建新的配置
        config["metadata"].setdefault("annotations", {})["app.kubernetes.io/config-md5"] = config_md5
        try:
            resource_client.create(namespace=context["namespace"], body=config)
        except k8s_client.exceptions.ApiException as e:
            if e.status != 409:
                raise e

    def _create_plugin_public_resource(self, context: dict[str, Any]):
        """
        创建公共资源配置
        """
        cluster_id: str = context["cluster_id"]
        namespace: str = context["namespace"]

        with k8s_client.ApiClient(self._get_k8s_config(cluster_id)) as api_client:
            # 创建namespace
            client = k8s_client.CoreV1Api(api_client)
            namespace_body = {
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {"name": namespace, "labels": {"name": namespace}},
            }
            try:
                client.create_namespace(body=namespace_body)
            except k8s_client.exceptions.ApiException as e:
                if e.status != 409:
                    raise e

            dynamic_client = k8s_dynamic.DynamicClient(api_client)

            # 创建dataid资源
            self._create_or_update_dynamic_resource(dynamic_client, DATA_ID_TEMPLATE, context)

            # 创建servicemonitor资源
            self._create_or_update_dynamic_resource(dynamic_client, SERVICE_MONITOR_TEMPLATE, context)

    def _render_yaml(self, target_version: DeploymentConfigVersion, context: dict[str, Any]) -> str:
        """
        渲染yaml配置
        """
        # 获取部署配置
        yaml_template = target_version.plugin_version.config.collector_json.get("template")
        if not yaml_template:
            raise ValueError("template is required in plugin config")

        return jinja_render(yaml_template, context)

    def _deploy(self, target_version: DeploymentConfigVersion):
        """
        部署k8s资源配置
        """
        context = self._get_context(target_version)
        cluster_id = context["cluster_id"]

        # 创建namespace和dataid资源
        self._create_plugin_public_resource(context)

        resources: set[tuple[str, str, str]] = set()
        with k8s_client.ApiClient(self._get_k8s_config(cluster_id)) as api_client:
            client = k8s_dynamic.DynamicClient(api_client)

            for config in yaml.safe_load_all(self._render_yaml(target_version, context)):
                if not config:
                    continue
                resources.add((config["apiVersion"], config["kind"], config["metadata"]["name"]))
                self._create_or_update_dynamic_resource(client, config, context)

            # 清理旧版本的资源
            if not target_version.last_version:
                return

            last_context = self._get_context(target_version.last_version)
            for config in yaml.safe_load_all(self._render_yaml(target_version.last_version, last_context)):
                if not config or (config["apiVersion"], config["kind"], config["metadata"]["name"]) in resources:
                    continue

                # 如果资源在新版本中不存在，则删除
                resource_client = client.resources.get(api_version=config["apiVersion"], kind=config["kind"])
                try:
                    resource_client.delete(namespace=context["namespace"], name=config["metadata"]["name"])
                except k8s_client.exceptions.ApiException as e:
                    if e.status != 404:
                        raise e

    def _undeploy(self, target_version: DeploymentConfigVersion | None = None):
        """
        卸载k8s资源配置
        """
        if not target_version:
            target_version = self.collect_config.deployment_config

        context = self._get_context(target_version)
        cluster_id: str = context["cluster_id"]
        namespace: str = context["namespace"]

        with k8s_client.ApiClient(configuration=self._get_k8s_config(cluster_id)) as api_client:
            client = k8s_dynamic.DynamicClient(api_client)

            for config in yaml.safe_load_all(self._render_yaml(target_version, context)):
                if not config:
                    continue
                api_version = config["apiVersion"]
                kind = config["kind"]
                resource_client = client.resources.get(api_version=api_version, kind=kind)
                try:
                    resource_client.delete(namespace=namespace, name=config["metadata"]["name"])
                except k8s_client.exceptions.ApiException as e:
                    if e.status != 404:
                        raise e

    def _get_context(self, target_version: DeploymentConfigVersion) -> dict[str, Any]:
        """
        获取上下文配置
        """
        plugin_version: PluginVersionHistory = target_version.plugin_version
        collector_json: dict[str, Any] = plugin_version.config.collector_json

        collect_params: dict[str, Any] = target_version.params

        # 获取插件默认配置
        values: dict[str, Any] = collector_json.get("values") or {}

        # 将采集配置参数合并到values中
        for key, value in collect_params.get("plugin", {}).items():
            keys: list[str] = key.split(".")

            sub_value = values
            for index, sub_key in enumerate(keys):
                # 如果是最后一个key，则直接赋值
                if index == len(keys) - 1:
                    sub_value[sub_key] = value
                    break

                # 如果不是最后一个key，且value不是dict，则创建一个dict
                if not isinstance(sub_value.get(sub_key), dict):
                    sub_value[sub_key] = {}
                sub_value = sub_value[sub_key]
            values[key] = value

        cluster_id, namespace = self._get_default_cluster()

        plugin_id = self.collect_config.plugin.plugin_id.replace("_", "-")
        bk_env: str = settings.BCS_CLUSTER_BK_ENV_LABEL
        if bk_env:
            release_name = f"bk-monitor-collector-{self.collect_config.id}-{bk_env}"
            plugin_release_name = f"bk-monitor-plugin-{plugin_id}-{bk_env}"
        else:
            release_name = f"bk-monitor-collector-{self.collect_config.id}"
            plugin_release_name = f"bk-monitor-plugin-{plugin_id}"

        return {
            "bk_biz_id": self.collect_config.bk_biz_id,
            "bk_env": bk_env,
            "release_name": release_name,
            "plugin_release_name": plugin_release_name,
            "cluster_id": cluster_id,
            "namespace": namespace,
            "values": values,
            "collect": {
                "id": self.collect_config.id,
                "name": self.collect_config.name,
                "version": target_version.id,
                "period": collect_params.get("collector", {}).get("period", 60),
                "timeout": collect_params.get("collector", {}).get("timeout", 60),
            },
            "plugin": {
                "id": self.collect_config.plugin_id,
                "version": plugin_version.version,
                "data_id": self.collect_config.data_id,
            },
        }

    def install(self, install_config: dict, operation: str | None = None) -> dict:
        """
        安装采集配置
        """
        # 创建新的部署记录
        deployment_config_params = {
            "plugin_version": self.plugin.packaged_release_version,
            "target_node_type": TargetNodeType.CLUSTER,
            # TODO: 目前仅使用内置的k8s集群，后续根据需求支持自定义集群
            "target_nodes": [],
            "params": install_config["params"],
            "config_meta_id": self.collect_config.pk or 0,
            "parent_id": self.collect_config.deployment_config_id or 0,
        }
        new_version = DeploymentConfigVersion.objects.create(**deployment_config_params)

        self.collect_config.deployment_config = new_version
        self.collect_config.operation_result = OperationResult.DEPLOYING
        if operation:
            self.collect_config.last_operation = operation
        else:
            self.collect_config.last_operation = OperationType.EDIT if self.collect_config.pk else OperationType.CREATE
        self.collect_config.save()

        # 如果是首次创建，更新部署配置关联的采集配置ID
        if not new_version.config_meta_id:
            new_version.config_meta_id = self.collect_config.pk
            new_version.save()

        try:
            self._deploy(new_version)
        except k8s_client.exceptions.ApiException as e:
            logger.error(f"deploy k8s resource failed: {e}")
            self.collect_config.operation_result = OperationResult.FAILED
            self.collect_config.save()

        return {
            "id": self.collect_config.pk,
            "deployment_id": new_version.pk,
            "can_rollback": bool(new_version.parent_id),
        }

    def upgrade(self, params: dict):
        """
        升级采集配置
        """
        current_version = self.collect_config.deployment_config

        params["collector"]["period"] = current_version.params.get("collector", {}).get("period", 60)
        params["collector"]["period"] = current_version.params.get("collector", {}).get("timeout", 60)

        # 创建新的部署记录
        deployment_config_params = {
            "plugin_version": self.plugin.packaged_release_version,
            "target_node_type": TargetNodeType.CLUSTER,
            # TODO: 目前仅使用内置的k8s集群，后续根据需求支持自定义集群
            "target_nodes": [],
            "params": params,
            "config_meta_id": self.collect_config.pk,
            "parent_id": current_version.pk,
        }
        new_version = DeploymentConfigVersion.objects.create(**deployment_config_params)

        # 更新采集配置
        self.collect_config.operation_result = OperationResult.DEPLOYING
        self.collect_config.last_operation = OperationType.UPGRADE
        self.collect_config.deployment_config = new_version
        self.collect_config.save()

        try:
            self._deploy(new_version)
        except k8s_client.exceptions.ApiException as e:
            logger.error(f"deploy k8s resource failed: {e}")
            self.collect_config.operation_result = OperationResult.FAILED
            self.collect_config.save()

        return {"id": self.collect_config.pk, "deployment_id": new_version.pk}

    def uninstall(self):
        """
        卸载采集配置
        """
        # 判断是否已经停用
        if self.collect_config.last_operation != OperationType.STOP:
            raise DeleteCollectConfigError({"msg": _("采集配置未停用")})

        # 删除部署记录及采集配置
        DeploymentConfigVersion.objects.filter(config_meta_id=self.collect_config.id).delete()
        self.collect_config.delete()

    def rollback(self, target_version: int | DeploymentConfigVersion | None = None):
        """
        回滚采集配置
        """
        # 判断是否支持回滚
        if not self.collect_config.allow_rollback:
            raise CollectConfigRollbackError({"msg": _("当前操作不支持回滚，或采集配置正处于执行中")})

        # 获取目标版本
        if not target_version:
            target_version = self.collect_config.deployment_config.last_version
        elif isinstance(target_version, int):
            target_version = DeploymentConfigVersion.objects.get(pk=target_version)

        # 更新采集配置
        self.collect_config.deployment_config = target_version
        self.collect_config.operation_result = OperationResult.PREPARING
        self.collect_config.last_operation = OperationType.ROLLBACK
        self.collect_config.save()

        try:
            self._deploy(target_version=target_version)
        except k8s_client.exceptions.ApiException as e:
            logger.error(f"deploy k8s resource failed: {e}")
            self.collect_config.operation_result = OperationResult.FAILED
            self.collect_config.save()

        return {"id": self.collect_config.pk, "deployment_id": target_version.pk}

    def start(self):
        """
        启动采集配置
        """
        if self.collect_config.last_operation != OperationType.STOP:
            raise ToggleConfigStatusError({"msg": _("采集配置未处于停用状态，无法执行启动操作")})

        self.collect_config.operation_result = OperationResult.PREPARING
        self.collect_config.last_operation = OperationType.START
        self.collect_config.save()

        try:
            self._deploy(self.collect_config.deployment_config)
        except k8s_client.exceptions.ApiException as e:
            logger.error(f"deploy k8s resource failed: {e}")
            self.collect_config.operation_result = OperationResult.FAILED
            self.collect_config.save()

    def stop(self):
        """
        停止采集配置
        """
        if self.collect_config.last_operation == OperationType.STOP:
            raise ToggleConfigStatusError({"msg": _("采集配置已处于停用状态，无需重复执行停止操作")})

        self.collect_config.operation_result = OperationResult.PREPARING
        self.collect_config.last_operation = OperationType.STOP
        self.collect_config.save()

        try:
            self._undeploy()
        except k8s_client.exceptions.ApiException as e:
            logger.error(f"undeploy k8s resource failed: {e}")
            self.collect_config.operation_result = OperationResult.FAILED
            self.collect_config.save()

    def run(self, action: str = None, scope: dict[str, Any] = None):
        """
        主动执行采集配置
        """
        self._deploy(self.collect_config.deployment_config)

    def retry(self, instance_ids: list[str] = None):
        """
        重试采集配置
        """
        self.collect_config.operation_result = OperationResult.PREPARING
        self.collect_config.save()

        try:
            self._deploy(self.collect_config.deployment_config)
        except k8s_client.exceptions.ApiException as e:
            logger.error(f"deploy k8s resource failed: {e}")
            self.collect_config.operation_result = OperationResult.FAILED
            self.collect_config.save()

    def revoke(self, instance_ids: list[int] = None):
        """
        撤销采集配置（该类型不需要实现）
        """

    def status(self, *args, **kwargs):
        """
        状态查询
        """
        target_version = self.collect_config.deployment_config

        if self.collect_config.last_operation == OperationType.STOP:
            return [
                {
                    "child": [
                        {
                            "instance_id": "default",
                            "instance_name": _("公共采集集群"),
                            "status": "SUCCESS",
                            "plugin_version": target_version.plugin_version.version,
                            "log": "",
                            "action": "",
                            "steps": {},
                        }
                    ],
                    "node_path": _("集群"),
                    "label_name": "",
                    "is_label": False,
                }
            ]

        context = self._get_context(target_version)

        cluster_id, namespace = self._get_default_cluster()
        with k8s_client.ApiClient(self._get_k8s_config(cluster_id)) as api_client:
            client = k8s_dynamic.DynamicClient(api_client)

            status, log = "SUCCESS", ""
            for resource in yaml.safe_load_all(self._render_yaml(target_version, context)):
                if not resource:
                    continue

                api_version = resource["apiVersion"]
                kind = resource["kind"]

                resource_client = client.resources.get(api_version=api_version, kind=kind)
                try:
                    result = resource_client.get(namespace=namespace, name=resource["metadata"]["name"])
                except k8s_client.exceptions.ApiException as e:
                    status = "FAILED"
                    log = f"query {kind}/{resource['metadata']['name']} status failed, {e}"
                    break

                # 如果是Deployment或StatefulSet，进一步判断是否正常运行
                if kind.lower() in ["deployment", "statefulset"]:
                    replicas = result["status"]["replicas"]
                    ready_replicas = result["status"]["readyReplicas"]
                    if replicas == ready_replicas:
                        continue

                    # 增加 deployment 超时判断
                    for condition in result["status"].get("conditions", []):
                        if condition["type"] == "Progressing" and condition["status"] == "False":
                            status = "FAILED"
                            log = _("部署超时，请检查配置是否正确。如果确认配置无误，请联系管理员")
                            break
                    else:
                        status = "RUNNING"
                        log = (
                            f"{kind}/{resource['metadata']['name']} is running, "
                            f"replicas: {replicas}, readyReplicas: {ready_replicas}"
                        )

                    # 如果状态不正常，直接退出
                    if status != "SUCCESS":
                        break

        return [
            {
                "child": [
                    {
                        "instance_id": "default",
                        "instance_name": _("公共采集集群"),
                        "status": status,
                        "plugin_version": self.collect_config.deployment_config.plugin_version.version,
                        "log": log,
                        "action": "",
                        "steps": {},
                    }
                ],
                "node_path": _("集群"),
                "label_name": "",
                "is_label": False,
            }
        ]

    def instance_status(self, instance_id: str):
        return {"log_detail": ""}
