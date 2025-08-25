"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
from typing import Any

import yaml
from django.conf import settings
from kubernetes import client as k8s_client
from kubernetes import dynamic as k8s_dynamic

from bkmonitor.utils.template import jinja_render
from core.drf_resource import api
from monitor_web.commons.data_access import PluginDataAccessor
from monitor_web.plugin.constant import PluginType
import hashlib

logger = logging.getLogger(__name__)
QCLOUD_MONITOR_API_VERSION = "monitoring.bk.tencent.com/v1beta1"
QCLOUD_MONITOR_KIND = "QCloudMonitor"

QCLOUD_MONITOR_TEMPLATE = """
apiVersion: monitoring.bk.tencent.com/v1beta1
kind: QCloudMonitor
metadata:
    name: {{ resource_name }}
    namespace: {{ namespace }}
    labels:
        app.kubernetes.io/name: qcloud-exporter
        monitoring.bk.tencent.com/managed-by: bkmonitor-operator
        app.kubernetes.io/task-id: "{{ task_id }}"
        {%- if bk_env %}
        app.kubernetes.io/bk-env: "{{ bk_env }}"
        {%- endif %}
spec:
    config:
        enableExporterMetrics: true
        fileContent: |
            credential:
                access_key: {{ secret_id }}
                secret_key: {{ secret_key }}
                region: {{ region_code }}
                is_internal: {{ is_internal }}
            is_international: {{ is_international }}
            rate_limit: 10
            products:
                - namespace: {{ product_namespace }}
                  all_metrics: {{ all_metrics | lower }}
                  all_instances: {{ all_instances | lower }}
                  {%- if only_include_metrics %}
                  only_include_metrics: 
                  {%- for metric in only_include_metrics %}
                    - {{ metric }}
                  {%- endfor %}
                  {%- endif %}
                  {%- if req_params %}
                  req_params: |
{{ req_params | indent(22) }}
                  {%- endif %}
        logLevel: info
        maxRequests: 0
    dataID: {{ data_id }}
    interval: {{ collect_interval }}
    timeout: {{ collect_timeout }}
    exporter:
        image: ccr.ccs.tencentyun.com/rig-agent/qcloud-exporter:v0.13.1-filter-3
        resources:
            requests:
                cpu: {{ requests_cpu | default("1") }}
                memory: {{ requests_memory | default("512Mi") }}
            limits:
                cpu: {{ limits_cpu | default("0.2") }}
                memory: {{ limits_memory | default("128Mi") }}
    extendLabels:
        {%- if extend_labels %}
        {%- for key, value in extend_labels.items() %}
        {{ key }}: {{ value }}
        {%- endfor %}
        {%- else %}
        {}
        {%- endif %}
    interval: {{ collect_interval | default("60s") }}
    timeout: {{ collect_timeout | default("60s") }}
"""


class QCloudMonitoringTaskDeployer:
    """
    腾讯云监控采集任务部署器

    负责将云监控采集任务配置部署到 K8S 集群
    """

    def __init__(self, task_id: str):
        """
        初始化部署器

        Args:
            task_id: 云监控采集任务ID
        """
        self.task_id = task_id
        self.task = None
        self.regions = []
        self.data_id = None

        # 加载任务配置
        self._load_task_config()

    def _load_task_config(self):
        """
        加载任务配置
        """
        from monitor_web.models.qcloud import CloudMonitoringTask, CloudMonitoringTaskRegion

        try:
            self.task = CloudMonitoringTask.objects.get(task_id=self.task_id)
            self.regions = list(
                CloudMonitoringTaskRegion.objects.filter(task_id=self.task_id, is_deleted=False).order_by("region_id")
            )

            if not self.regions:
                raise ValueError(f"任务 {self.task_id} 没有配置地域信息")

            logger.info(f"加载任务配置成功: task_id={self.task_id}, regions={len(self.regions)}")

        except CloudMonitoringTask.DoesNotExist:
            raise ValueError(f"任务不存在: task_id={self.task_id}")

    def _get_plugin_config(self) -> dict[str, Any]:
        """
        获取插件配置

        Returns:
            dict: 插件配置
        """
        if not settings.TENCENT_CLOUD_METRIC_PLUGIN_CONFIG:
            raise ValueError("TENCENT_CLOUD_METRIC_PLUGIN_CONFIG is not set, please contact administrator")

        return settings.TENCENT_CLOUD_METRIC_PLUGIN_CONFIG

    def _create_data_id(self):
        """
        为任务创建 data_id
        """
        try:
            # 创建插件数据访问器，每个任务一个 data_id
            plugin_config = self._get_plugin_config()

            # 创建虚拟插件版本对象用于数据接入
            class MockPluginVersion:
                def __init__(self, task_config, plugin_config):
                    self.info = self
                    self.config = self
                    self.plugin = self

                    # 基本信息
                    self.plugin_id = settings.TENCENT_CLOUD_METRIC_PLUGIN_ID
                    self.plugin_type = PluginType.K8S
                    self.label = plugin_config.get("label", "os")

                    # 配置信息
                    self.metric_json = []  # K8S 类型插件不需要预定义指标
                    self.enable_field_blacklist = True  # 启用单指标单表
                    self.config_json = plugin_config.get("config_json", [])

            mock_plugin_version = MockPluginVersion(self.task, plugin_config)

            # 创建数据访问器
            accessor = PluginDataAccessor(
                plugin_version=mock_plugin_version,
                operator="system",
                data_label=settings.TENCENT_CLOUD_METRIC_PLUGIN_ID,
            )

            # 使用任务ID作为后缀创建独立的 data_id
            self.data_id = accessor.access(per_collect_suffix=self.task_id)
            self.task.data_id = self.data_id
            self.task.save(update_fields=["data_id", "update_time"])

            logger.info(f"创建 data_id 成功: task_id={self.task_id}, data_id={self.data_id}")

        except Exception as e:
            logger.error(f"创建 data_id 失败: task_id={self.task_id}, error={str(e)}")
            raise

    def _get_k8s_config(self, cluster_id: str) -> k8s_client.Configuration:
        """
        获取 K8S 集群配置

        Args:
            cluster_id: 集群ID

        Returns:
            k8s_client.Configuration: K8S 配置
        """
        from urllib.parse import urljoin

        # 检查必需的配置
        if not all(
            [
                settings.BCS_API_GATEWAY_SCHEMA,
                settings.BCS_API_GATEWAY_HOST,
                settings.BCS_API_GATEWAY_PORT,
                settings.BCS_API_GATEWAY_TOKEN,
            ]
        ):
            raise ValueError("BCS API Gateway configuration is incomplete, contact administrator")

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

    def _get_default_cluster(self) -> tuple[str, str]:
        """
        获取默认集群信息

        Returns:
            tuple: (cluster_id, namespace)
        """
        if not settings.K8S_PLUGIN_COLLECT_CLUSTER_ID:
            raise ValueError("K8S_PLUGIN_COLLECT_CLUSTER_ID is required, contact administrator")

        try:
            cluster_id, namespace = settings.K8S_PLUGIN_COLLECT_CLUSTER_ID.split(":")
            return cluster_id, namespace
        except ValueError:
            raise ValueError(
                f"Invalid K8S_PLUGIN_COLLECT_CLUSTER_ID format: {settings.K8S_PLUGIN_COLLECT_CLUSTER_ID}, "
                "expected format: 'cluster_id:namespace'"
            )

    def _convert_req_params(self, region) -> str | None:
        """
        调用 API 将 region 的 tags/filters 配置转换为 req_params JSON 字符串
        """
        try:
            params_payload = {
                "namespace": self.task.namespace,
                "tags": region.tags_config,
                "filters": region.filters_config,
            }
            converted_params = api.qcloud_monitor.convert_params(params_payload)
            # 使用 json.dumps 确保输出的是一个 JSON 字符串
            return json.dumps(converted_params.get("req_params", {}), indent=4)
        except Exception as e:
            logger.error(f"转换 req_params 失败: task_id={self.task_id}, region={region.region_code}, error={e}")
            return None

    def _create_qcloud_monitor_resource(self, region):
        """
        为指定地域创建或更新 QCloudMonitor 资源

        Args:
            region: 地域配置对象 (CloudMonitoringTaskRegion 实例)
        """
        try:
            cluster_id, namespace = self._get_default_cluster()
            plugin_config = self._get_plugin_config()

            # 构建资源名称
            resource_name = f"qcloud-{self.task_id}-{region.region_code}".lower().replace("_", "-")

            # 获取镜像和资源配置
            collector_json = plugin_config.get("collector_json", {})
            values = collector_json.get("values", {})

            # all_metrics 和 only_include_metrics 互斥
            if region.selected_metrics:
                all_metrics = False
                only_include_metrics = region.selected_metrics
            else:
                all_metrics = True
                only_include_metrics = []

            # all_instances
            all_instances = not (region.tags_config or region.filters_config)

            # extend_labels
            extend_labels = {
                item["name"]: item["value"] for item in region.dimensions_config if "name" in item and "value" in item
            }

            # 调用 API 转换 req_params
            req_params = self._convert_req_params(region)

            # 构建渲染上下文
            context = {
                "resource_name": resource_name,
                "namespace": namespace,
                "task_id": self.task_id,
                "data_id": self.data_id,
                "collect_interval": self.task.collect_interval,
                "collect_timeout": self.task.collect_timeout,
                "product_namespace": self.task.namespace,
                "bk_env": getattr(settings, "BCS_CLUSTER_BK_ENV_LABEL", ""),
                # 凭证信息
                "secret_id": self.task.secret_id,
                "secret_key": self.task.secret_key,
                "region_code": region.region_code,
                "is_internal": self.task.is_internal,
                "is_international": self.task.is_international,
                # 产品和实例配置
                "all_instances": all_instances,
                "all_metrics": all_metrics,
                "only_include_metrics": only_include_metrics,
                "custom_query_dimensions": region.dimensions_config,
                "req_params": req_params,
                # 镜像和资源配置
                "requests_cpu": values.get("requests", {}).get("cpu", "1000m"),
                "requests_memory": values.get("requests", {}).get("memory", "512Mi"),
                "limits_cpu": values.get("limits", {}).get("cpu", "200m"),
                "limits_memory": values.get("limits", {}).get("memory", "128Mi"),
                # 扩展标签
                "extend_labels": extend_labels,
            }

            # 渲染 YAML 配置
            yaml_str = jinja_render(QCLOUD_MONITOR_TEMPLATE, context)
            config = yaml.load(yaml_str, Loader=yaml.FullLoader)

            # 部署到 K8S 集群
            with k8s_client.ApiClient(self._get_k8s_config(cluster_id)) as api_client:
                dynamic_client = k8s_dynamic.DynamicClient(api_client)

                # 获取 QCloudMonitor 资源客户端
                resource_client = dynamic_client.resources.get(
                    api_version=QCLOUD_MONITOR_API_VERSION, kind=QCLOUD_MONITOR_KIND
                )

                # 检查资源是否已存在
                try:
                    exists_config = resource_client.get(namespace=namespace, name=resource_name)
                    if exists_config:
                        try:
                            # 尝试删除已有资源（如果存在）
                            resource_client.delete(namespace=namespace, name=resource_name)
                            logger.info(f"删除旧 QCloudMonitor 资源成功: {resource_name}")
                        except k8s_client.exceptions.ApiException as del_e:
                            # 若为不存在则继续创建，其他错误抛出
                            if del_e.status != 404:
                                raise del_e

                except k8s_client.exceptions.ApiException as e:
                    if e.status == 404:
                        raise e
                    exists_config = None

                diff, config_md5 = self._compare_md5(config, exists_config)
                if not diff:
                    return

                if exists_config:
                    try:
                        resource_client.delete(namespace=namespace, name=resource_name)
                    except k8s_client.exceptions.ApiException as e:
                        if e.status != 404:
                            raise e

                config["metadata"].setdefault("annotations", {})["app.kubernetes.io/config-md5"] = config_md5
                try:
                    resource_client.create(namespace=namespace, body=config)
                except k8s_client.exceptions.ApiException as e:
                    if e.status != 409:
                        raise e

        except Exception as e:
            logger.error(f"创建 QCloudMonitor 资源失败: region={region.region_code}, error={str(e)}")
            raise

    def deploy(self):
        """
        部署腾讯云监控采集任务
        """
        try:
            # 1. 创建 data_id
            self._create_data_id()

            # 2. 为每个地域创建 QCloudMonitor 资源
            for region in self.regions:
                self._create_qcloud_monitor_resource(region)

            # 3. 更新任务状态
            self.task.status = self.task.STATUS_SUCCESS
            self.task.save()

            # 4. 更新地域状态
            for region in self.regions:
                region.status = region.STATUS_SUCCESS
                region.save()

            logger.info(f"腾讯云监控任务部署成功: task_id={self.task_id}")

        except Exception as e:
            logger.error(f"腾讯云监控任务部署失败: task_id={self.task_id}, error={str(e)}")

            # 更新任务状态为失败
            self.task.status = self.task.STATUS_FAILED
            self.task.save()

            # 更新地域状态为失败
            for region in self.regions:
                region.status = region.STATUS_FAILED
                region.save()

            raise

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
