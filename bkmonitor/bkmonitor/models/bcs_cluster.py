"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import base64
import datetime
import gzip
import json
import logging
import time
from typing import Any

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext as _
from humanize import naturaldelta
from kubernetes import client as k8s_client

from bkm_space.api import SpaceApi, SpaceTypeEnum
from bkmonitor.models import BCSBaseManager
from bkmonitor.models.bcs_base import BCSBase, BCSLabel
from bkmonitor.utils.kubernetes import get_progress_value
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api

logger = logging.getLogger("kubernetes")


class BCSClusterManager(BCSBaseManager):
    pass


class BCSCluster(BCSBase):
    bk_tenant_id = models.CharField(verbose_name="租户ID", max_length=128, default=DEFAULT_TENANT_ID)
    name = models.CharField(verbose_name="集群名称", max_length=128)
    area_name = models.CharField(verbose_name="区域", max_length=32)
    project_name = models.CharField(verbose_name="业务名", max_length=32)
    environment = models.CharField(verbose_name="环境", max_length=32)
    updated_at = models.DateTimeField(verbose_name="更新时间")
    node_count = models.IntegerField(verbose_name="节点数")
    cpu_usage_ratio = models.FloatField(verbose_name="CPU使用率")
    memory_usage_ratio = models.FloatField(verbose_name="内存使用率")
    disk_usage_ratio = models.FloatField(verbose_name="磁盘使用率")
    data_source = models.CharField(verbose_name="数据来源", default="api", max_length=32)

    gray_status = models.BooleanField(verbose_name="BCS集群灰度接入蓝鲸监控", default=False)
    bcs_monitor_data_source = models.CharField(verbose_name="bcs监控数据源", default="prometheus", max_length=32)

    labels = models.ManyToManyField(BCSLabel, through="BCSClusterLabels", through_fields=("resource", "label"))

    bkmonitor_operator_deployed = models.BooleanField(
        verbose_name="bkmonitor operator部署状态", default=False, null=True
    )
    bkmonitor_operator_version = models.CharField(verbose_name="bkmonitor operator版本", max_length=64, null=True)
    bkmonitor_operator_first_deployed = models.DateTimeField(verbose_name="bkmonitor operator首次部署时间", null=True)
    bkmonitor_operator_last_deployed = models.DateTimeField(verbose_name="bkmonitor operator最后部署时间", null=True)

    # 可选值 enabled , disabled
    alert_status = models.CharField(verbose_name="告警状态", max_length=32, default="enabled")
    space_uid = models.CharField(verbose_name="空间唯一标识", max_length=64, default="")

    objects = BCSClusterManager()

    class Meta:
        index_together = ["bk_biz_id", "bcs_cluster_id"]

    def to_meta_dict(self):
        return {"cluster": self.bcs_cluster_id}

    @staticmethod
    def hash_unique_key(bk_biz_id, bcs_cluster_id):
        return BCSCluster.md5str(
            ",".join(
                [
                    str(bk_biz_id),
                    bcs_cluster_id,
                ]
            )
        )

    def get_unique_hash(self):
        """业务和集群保证唯一性 ."""
        return self.hash_unique_key(self.bk_biz_id, self.bcs_cluster_id)

    @staticmethod
    def get_columns(columns_type="list"):
        return [
            {
                "id": "bcs_cluster_id",
                "width": 208,
                "name": _("集群ID"),
                "type": "link" if columns_type == "list" else "string",
                "disabled": False,
                "checked": True,
                "overview": "name",
                "overview_name": _("概览"),
            },
            {
                "id": "name",
                "name": _("集群名称"),
                "type": "string",
                "disabled": False,
                "checked": True,
            },
            {
                "id": "status",
                "name": _("运行状态"),
                "type": "string",
                "disabled": False,
                "checked": True,
                "filterable": True,
            },
            {
                "id": "monitor_status",
                "name": _("采集状态"),
                "type": "status",
                "disabled": False,
                "checked": False,
            },
            {
                "id": "environment",
                "name": _("环境"),
                "type": "string",
                "disabled": False,
                "checked": False,
            },
            {
                "id": "node_count",
                "name": _("节点数量"),
                "type": "number",
                "disabled": False,
                "checked": True,
                "sortable": True,
                "sortable_type": "progress",
            },
            {
                "id": "cpu_usage_ratio",
                "name": _("CPU使用率"),
                "header_pre_icon": "icon-avg",
                "type": "progress",
                "disabled": False,
                "checked": True,
                "overview": "progress",
                "sortable": True,
                "sortable_type": "progress",
            },
            {
                "id": "memory_usage_ratio",
                "name": _("内存使用率"),
                "header_pre_icon": "icon-avg",
                "type": "progress",
                "disabled": False,
                "checked": True,
                "overview": "progress",
                "sortable": True,
                "sortable_type": "progress",
            },
            {
                "id": "disk_usage_ratio",
                "name": _("磁盘使用率"),
                "header_pre_icon": "icon-avg",
                "type": "progress",
                "disabled": False,
                "checked": True,
                "overview": "progress",
                "sortable": True,
                "sortable_type": "progress",
            },
            {
                "id": "area_name",
                "name": _("区域"),
                "type": "string",
                "disabled": False,
                "checked": False,
            },
            {
                "id": "created_at",
                "name": _("创建时间"),
                "type": "string",
                "disabled": False,
                "checked": True,
            },
            {
                "id": "updated_at",
                "name": _("更新时间"),
                "type": "string",
                "disabled": False,
                "checked": True,
            },
            {
                "id": "project_name",
                "name": _("所属项目"),
                "type": "string",
                "disabled": False,
                "checked": False,
            },
            {
                "id": "description",
                "name": _("描述"),
                "type": "string",
                "disabled": False,
                "checked": False,
            },
        ]

    @staticmethod
    def load_list_from_api(params: dict[str, Any]):
        """
        按业务ID获取所有的cluster

        Args:
            params: 请求参数
                bk_tenant_id: 租户ID
                bk_biz_id: 业务ID, 可选

        Returns:
            list: 集群列表
        """
        bk_tenant_id = params["bk_tenant_id"]
        bk_biz_id = params.get("bk_biz_id")
        request_params = {
            "data_type": "full",
            "bk_tenant_id": bk_tenant_id,
        }
        if bk_biz_id:
            request_params["bk_biz_id"] = bk_biz_id
        # 获得BCS集群列表
        api_clusters = api.kubernetes.fetch_k8s_cluster_list(request_params)
        clusters = []
        # 获得启用了BCS的蓝盾空间
        all_space_list = SpaceApi.list_spaces_dict(bk_tenant_id=bk_tenant_id)
        bk_ci_spaces_list = (
            space
            for space in all_space_list
            if space["space_type_id"] == SpaceTypeEnum.BKCI.value and space["space_code"]
        )
        project_id_to_space_uid = {space["space_code"]: space["space_uid"] for space in bk_ci_spaces_list}
        for c in api_clusters:
            # 将project_id转换为space_uid
            project_id = c["project_id"]
            space_uid = project_id_to_space_uid.get(project_id, "")

            bcs_cluster = BCSCluster()
            bcs_cluster.space_uid = space_uid
            bcs_cluster.bk_biz_id = int(c["bk_biz_id"])
            bcs_cluster.name = c["name"]
            bcs_cluster.bcs_cluster_id = c["cluster_id"]
            bcs_cluster.area_name = c.get("area_name", "")  # cluster-manager 无此字段
            bcs_cluster.project_name = c.get("project_name")
            bcs_cluster.environment = c.get("environment", "")
            bcs_cluster.node_count = c.get("node_count", 0)  # 集群信息 无此字段
            bcs_cluster.cpu_usage_ratio = c.get("cpu_usage_ratio", 0)  # 集群信息 无此字段
            bcs_cluster.memory_usage_ratio = c.get("memory_usage_ratio", 0)  # 集群信息 无此字段
            bcs_cluster.disk_usage_ratio = c.get("disk_usage_ratio", 0)  # 集群信息 无此字段
            bcs_cluster.status = c.get("status")
            bcs_cluster.created_at = c.get("created_at")
            bcs_cluster.updated_at = c.get("updated_at")
            bcs_cluster.last_synced_at = timezone.now()
            bcs_cluster.deleted_at = None

            # 唯一键
            bcs_cluster.unique_hash = bcs_cluster.get_unique_hash()

            clusters.append(bcs_cluster)
        return clusters

    @classmethod
    def sync_resource_usage(cls, bk_biz_id: int, bcs_cluster_id: str) -> None:
        """获取每个集群的cpu/memory/dist usage ."""
        usage = cls.fetch_usage_ratio(bk_biz_id, bcs_cluster_id)
        usage_dict = {}
        for usage_type, value in usage.items():
            usage_dict[f"{usage_type}_usage_ratio"] = value
        value = usage_dict.get("cpu_usage_ratio")
        usage_resource_map = {(bcs_cluster_id,): value}
        # 获得采集器的指标上报状态
        monitor_operator_status_up_map = {}
        # 合并两个来源的状态
        monitor_status_map = cls.merge_monitor_status(usage_resource_map, monitor_operator_status_up_map)
        monitor_status = monitor_status_map.get((bcs_cluster_id,), cls.METRICS_STATE_FAILURE)
        # 获得已存在的记录
        old_unique_hash_map = {
            item["unique_hash"]: (
                item["cpu_usage_ratio"],
                item["memory_usage_ratio"],
                item["disk_usage_ratio"],
                item["monitor_status"],
            )
            for item in cls.objects.filter(bk_biz_id=bk_biz_id, bcs_cluster_id=bcs_cluster_id).values(
                "unique_hash", "cpu_usage_ratio", "memory_usage_ratio", "disk_usage_ratio", "monitor_status"
            )
        }
        # 获得新的记录
        unique_hash = cls.hash_unique_key(bk_biz_id, bcs_cluster_id)
        new_unique_hash_map = {
            unique_hash: (
                usage_dict.get("cpu_usage_ratio"),
                usage_dict.get("memory_usage_ratio"),
                usage_dict.get("disk_usage_ratio"),
                monitor_status,
            )
        }
        # 更新资源使用量
        unique_hash_set_for_update = set(old_unique_hash_map.keys()) & set(new_unique_hash_map.keys())
        for unique_hash in unique_hash_set_for_update:
            if new_unique_hash_map[unique_hash] == old_unique_hash_map[unique_hash]:
                continue
            update_kwargs = new_unique_hash_map[unique_hash]
            update_params = {}
            for index, key in enumerate(
                ["cpu_usage_ratio", "memory_usage_ratio", "disk_usage_ratio", "monitor_status"]
            ):
                if not update_kwargs[index]:
                    continue
                update_params[key] = update_kwargs[index]
            if update_params:
                cls.objects.filter(unique_hash=unique_hash).update(**update_params)

    @classmethod
    def fetch_usage_ratio(cls, bk_biz_id, bcs_cluster_id):
        """获得集群资源使用率 ."""
        end_time = int(time.time() - 60)
        start_time = int(time.time() - 120)
        params = {
            "bk_biz_id": bk_biz_id,
            "usage_type": ["cpu", "memory", "disk"],
            "bcs_cluster_id": bcs_cluster_id,
            "start_time": start_time,
            "end_time": end_time,
        }
        request_results = api.kubernetes.fetch_usage_ratio(params)
        result = {}
        for usage_type, value in request_results.items():
            result[usage_type] = round(value, 2)

        return result

    @classmethod
    def update_monitor_status(cls, params: dict) -> None:
        """更新采集器状态 ."""
        # 获得资源使用率
        bk_biz_id = params["bk_biz_id"]
        bcs_cluster_id = params["bcs_cluster_id"]
        usage = cls.fetch_usage_ratio(bk_biz_id, bcs_cluster_id)
        if not usage:
            return
        usage_dict = {}
        for usage_type, value in usage.items():
            usage_dict[f"{usage_type}_usage_ratio"] = value
        value = usage_dict.get("cpu_usage_ratio")
        usage_resource_map = {(bcs_cluster_id,): value}
        # 获得采集器的指标上报状态
        monitor_operator_status_up_map = {}
        # 合并两个来源的状态
        monitor_status_map = cls.merge_monitor_status(usage_resource_map, monitor_operator_status_up_map)
        monitor_status = monitor_status_map.get((bcs_cluster_id,), cls.METRICS_STATE_FAILURE)
        # 更新资源使用率和采集器状态
        cls.objects.filter(bcs_cluster_id=bcs_cluster_id).update(
            **{
                "cpu_usage_ratio": usage_dict.get("cpu_usage_ratio"),
                "memory_usage_ratio": usage_dict.get("memory_usage_ratio"),
                "disk_usage_ratio": usage_dict.get("disk_usage_ratio"),
                "monitor_status": monitor_status,
            }
        )

    def render_bcs_cluster_id(self, bk_biz_id, render_type="list"):
        if render_type == "list":
            return {
                "icon": "",
                "target": "null_event",
                "key": "",
                "url": "",
                "value": self.bcs_cluster_id,
                "display_value": f"{self.name}({self.bcs_cluster_id})",
            }
        return self.bcs_cluster_id

    def render_cpu_usage_ratio(self, bk_biz_id, render_type="list"):
        return get_progress_value(self.cpu_usage_ratio)

    def render_environment(self, bk_biz_id, render_type="list"):
        environment_names = {"stag": _("测试"), "prod": _("正式")}
        if self.environment:
            return environment_names.get(self.environment, self.environment)
        return ""

    def render_memory_usage_ratio(self, bk_biz_id, render_type="list"):
        return get_progress_value(self.memory_usage_ratio)

    def render_disk_usage_ratio(self, bk_biz_id, render_type="list"):
        return get_progress_value(self.disk_usage_ratio)

    def render_created_at(self, bk_biz_id, render_type="list"):
        if isinstance(self.created_at, int):
            self.created_at = datetime.datetime.fromtimestamp(self.created_at).astimezone()
        return naturaldelta(timezone.now() - self.created_at)

    def render_updated_at(self, bk_biz_id, render_type="list"):
        if isinstance(self.updated_at, int):
            self.updated_at = datetime.datetime.fromtimestamp(self.updated_at).astimezone()
        return naturaldelta(timezone.now() - self.updated_at)

    @cached_property
    def api_client(self) -> k8s_client.ApiClient:
        """
        返回一个可用的k8s APIClient
        注意，此处会有一个缓存，如果是使用shell进行修改了配置项，需要重新赋值实例，否则client会依旧使用旧的配置
        """
        return k8s_client.ApiClient(self.k8s_client_config)

    @cached_property
    def k8s_client_config(self) -> k8s_client.Configuration:
        """返回一个可用的k8s集群配置信息"""
        schema = settings.BCS_API_GATEWAY_SCHEMA
        host = settings.BCS_API_GATEWAY_HOST
        port = settings.BCS_API_GATEWAY_PORT
        k8s_config = k8s_client.Configuration(
            host=f"{schema}://{host}:{port}/clusters/{self.bcs_cluster_id}",
            api_key={"authorization": settings.BCS_API_GATEWAY_TOKEN},
            api_key_prefix={"authorization": "Bearer"},
        )
        k8s_config.verify_ssl = False

        return k8s_config

    @cached_property
    def core_v1_api(self) -> k8s_client.CoreV1Api:
        return k8s_client.CoreV1Api(self.api_client)

    @cached_property
    def custom_objects_api(self) -> k8s_client.CustomObjectsApi:
        return k8s_client.CustomObjectsApi(self.api_client)

    @cached_property
    def apps_v1_api(self) -> k8s_client.AppsV1Api:
        return k8s_client.AppsV1Api(self.api_client)

    @cached_property
    def batch_v1_api(self) -> k8s_client.BatchV1Api:
        return k8s_client.BatchV1Api(self.api_client)

    @cached_property
    def batch_v1_beta1_api(self) -> k8s_client.BatchV1beta1Api:
        return k8s_client.BatchV1beta1Api(self.api_client)

    def sync_operator_info(self):
        try:
            client = self.core_v1_api
            label_selector = "name=bkmonitor-operator-stack,owner=helm,status=deployed"
            secret_list = client.list_secret_for_all_namespaces(label_selector=label_selector)
            item = secret_list.items[0]
            release_b_data = base64.b64decode(base64.b64decode(item.data["release"]))
            json_data = gzip.decompress(release_b_data)
            data = json.loads(json_data)
            self.bkmonitor_operator_deployed = True
            self.bkmonitor_operator_version = data["chart"]["metadata"]["version"]
            self.bkmonitor_operator_first_deployed = data["info"]["first_deployed"]
            self.bkmonitor_operator_last_deployed = data["info"]["last_deployed"]
        except Exception:  # noqa
            self.bkmonitor_operator_deployed = False
        self.save()


class BCSClusterLabels(models.Model):
    id = models.BigAutoField(primary_key=True)
    resource = models.ForeignKey(BCSCluster, db_constraint=False, on_delete=models.CASCADE)
    label = models.ForeignKey(BCSLabel, db_constraint=False, on_delete=models.CASCADE)
    bcs_cluster_id = models.CharField(verbose_name="集群ID", max_length=128)
