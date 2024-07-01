# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import logging
from typing import Dict, List, Optional

from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import ugettext as _
from django_mysql.models import QuerySet

from bkmonitor.models import BCSBase, BCSBaseManager, BCSBaseResources, BCSLabel
from bkmonitor.utils.casting import force_float
from bkmonitor.utils.common_utils import chunks
from bkmonitor.utils.kubernetes import get_progress_value
from core.drf_resource import api

logger = logging.getLogger("kubernetes")


class BCSPodManager(BCSBaseManager):
    def get_workload_type_list(self, params):
        """获得所有workload类型，包含自定义类型 ."""
        default_workload_type_list = [
            "CronJob",
            "DaemonSet",
            "Deployment",
            "Job",
            "StatefulSet",
        ]

        if params:
            bk_biz_id = params.get("bk_biz_id")
            bcs_cluster_id = params.get("bcs_cluster_id")
            filter_kwargs = Q()
            if bk_biz_id:
                filter_kwargs = filter_kwargs & Q(bk_biz_id=bk_biz_id)
            if bcs_cluster_id:
                filter_kwargs = filter_kwargs & Q(bcs_cluster_id=bcs_cluster_id)
            items = self.filter(filter_kwargs).values("workload_type").distinct()
            workload_type_list = [item["workload_type"] for item in items if item["workload_type"]]
            if not workload_type_list:
                workload_type_list = default_workload_type_list
        else:
            workload_type_list = default_workload_type_list
        return sorted(workload_type_list)


class BCSPod(BCSBase, BCSBaseResources):
    name = models.CharField(max_length=128)
    namespace = models.CharField(max_length=128)
    node_name = models.CharField(max_length=128)
    node_ip = models.CharField(max_length=64, null=True, db_index=True)
    workload_type = models.CharField(max_length=128)
    workload_name = models.CharField(max_length=128)
    total_container_count = models.IntegerField()
    ready_container_count = models.IntegerField()
    pod_ip = models.CharField(max_length=64, null=True)
    images = models.TextField()
    restarts = models.IntegerField()
    updated_at = models.DateTimeField(auto_now=True)

    request_cpu_usage_ratio = models.FloatField(verbose_name="CPU使用率(request)", null=True, default=0)
    limit_cpu_usage_ratio = models.FloatField(verbose_name="CPU使用率(limit)", null=True, default=0)
    request_memory_usage_ratio = models.FloatField(verbose_name="内存使用率(request)", null=True, default=0)
    limit_memory_usage_ratio = models.FloatField(verbose_name="内存使用率(limit)", null=True, default=0)

    labels = models.ManyToManyField(BCSLabel, through="BCSPodLabels", through_fields=("resource", "label"), blank=True)

    objects = BCSPodManager()

    class Meta:
        unique_together = ["bcs_cluster_id", "namespace", "name"]
        index_together = ["bk_biz_id", "bcs_cluster_id"]

    @staticmethod
    def hash_unique_key(bk_biz_id, bcs_cluster_id, namespace, name):
        return BCSPod.md5str(
            ",".join(
                [
                    str(bk_biz_id),
                    bcs_cluster_id,
                    namespace,
                    name,
                ]
            )
        )

    def get_unique_hash(self):
        return self.hash_unique_key(self.bk_biz_id, self.bcs_cluster_id, self.namespace, self.name)

    def save(self, *args, **kwargs):
        self.unique_hash = self.get_unique_hash()
        super().save(*args, **kwargs)

    @classmethod
    def get_columns(cls, columns_type="list"):
        columns = [
            {
                "id": "name",
                "width": 208,
                "name": _("Pod名称"),
                "type": "link" if columns_type == "list" else "string",
                "disabled": True,
                "checked": True,
                "overview": "name",
                "overview_name": _("概览"),
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
                "id": "ready",
                "name": _("是否就绪(实例运行数/期望数)"),
                "type": "string",
                "disabled": False,
                "checked": True,
            },
            {
                "id": "bcs_cluster_id",
                "name": _("集群ID"),
                "type": "link",
                "disabled": False,
                "checked": True,
                "filterable": True,
            },
        ]

        columns = cls.add_cluster_column(columns, columns_type)

        columns.extend(
            [
                {
                    "id": "namespace",
                    "name": _("名字空间"),
                    "type": "string",
                    "disabled": False,
                    "checked": True,
                    "filterable": True,
                },
                {
                    "id": "total_container_count",
                    "name": _("容器数量"),
                    "type": "link",
                    "disabled": False,
                    "checked": False,
                },
                {
                    "id": "restarts",
                    "name": _("重启次数"),
                    "type": "number",
                    "disabled": False,
                    "checked": True,
                    "sortable": True,
                    "sortable_type": "progress",
                },
                {
                    "id": "monitor_status",
                    "name": _("采集状态"),
                    "type": "status",
                    "disabled": False,
                    "checked": True,
                },
                {
                    "id": "age",
                    "name": _("存活时间"),
                    "type": "string",
                    "disabled": False,
                    "checked": False,
                },
            ]
        )

        columns.extend(cls.get_resource_usage_ratio_columns())
        columns.extend(cls.get_resource_usage_columns())
        columns.extend(cls.get_container_resources_columns())
        columns.extend(
            [
                {
                    "id": "pod_ip",
                    "name": "Pod IP",
                    "type": "string",
                    "disabled": False,
                    "checked": True,
                },
                {
                    "id": "node_ip",
                    "name": _("节点IP"),
                    "type": "link",
                    "disabled": False,
                    "checked": True,
                },
                {
                    "id": "node_name",
                    "name": _("节点名称"),
                    "type": "link",
                    "disabled": False,
                    "checked": False,
                },
                {
                    "id": "workload",
                    "name": _("工作负载"),
                    "type": "string",
                    "disabled": False,
                    "checked": False,
                },
                {
                    "id": "label_list",
                    "name": _("标签"),
                    "type": "kv",
                    "disabled": False,
                    "checked": False,
                },
                {
                    "id": "images",
                    "name": _("镜像"),
                    "type": "list",
                    "disabled": False,
                    "checked": False,
                },
            ]
        )

        return columns

    @staticmethod
    def load_list_from_api(params):
        bcs_cluster_id = params["bcs_cluster_id"]
        bk_biz_id = params["bk_biz_id"]

        for p in api.kubernetes.fetch_k8s_pod_list_by_cluster(bcs_cluster_id=bcs_cluster_id):
            bcs_cluster_id = p.get("bcs_cluster_id")
            bcs_pod = BCSPod()
            bcs_pod.bk_biz_id = bk_biz_id
            bcs_pod.bcs_cluster_id = bcs_cluster_id
            bcs_pod.name = p.get("name")
            bcs_pod.namespace = p.get("namespace")
            bcs_pod.node_name = p.get("node_name")
            bcs_pod.node_ip = p.get("node_ip")
            bcs_pod.workload_type = p.get("workload_type")
            bcs_pod.workload_name = p.get("workload_name")
            bcs_pod.total_container_count = p.get("total_container_count")
            bcs_pod.ready_container_count = p.get("ready_container_count")
            bcs_pod.pod_ip = p.get("pod_ip", "")
            bcs_pod.images = ",".join(p.get("image_id_list", []))
            bcs_pod.restarts = p.get("restarts")

            bcs_pod.resource_requests_cpu = force_float(p.get("requests_cpu", 0))
            bcs_pod.resource_requests_memory = p.get("requests_memory")
            bcs_pod.resource_limits_cpu = force_float(p.get("limits_cpu", 0))
            bcs_pod.resource_limits_memory = p.get("limits_memory")

            bcs_pod.created_at = p.get("created_at")
            bcs_pod.status = p.get("status")
            bcs_pod.last_synced_at = timezone.now()
            bcs_pod.deleted_at = None

            # 唯一键
            bcs_pod.unique_hash = bcs_pod.get_unique_hash()
            bcs_pod.api_labels = p.get("labels", {})
            yield bcs_pod

    def render_workload(self, bk_biz_id, render_type="list"):
        return f"{self.workload_type}:{self.workload_name}"

    def render_bcs_cluster_id(self, bk_biz_id, render_type="list"):
        search = [{"bcs_cluster_id": self.bcs_cluster_id}]
        return self.build_search_link(bk_biz_id, "cluster", self.bcs_cluster_id, search)

    def render_total_container_count(self, bk_biz_id, render_type="list"):
        search = [{"bcs_cluster_id": self.bcs_cluster_id}, {"pod_name": self.name}]
        return self.build_search_link(bk_biz_id, "container", self.total_container_count, search)

    def render_node_name(self, bk_biz_id, render_type="list"):
        search = [{"bcs_cluster_id": self.bcs_cluster_id}, {"name": self.node_name}]
        return self.build_search_link(bk_biz_id, "node", self.node_name, search)

    def render_node_ip(self, bk_biz_id, render_type="list"):
        search = [{"bcs_cluster_id": self.bcs_cluster_id}, {"ip": self.node_ip}]
        return self.build_search_link(bk_biz_id, "node", self.node_ip, search)

    def render_ready(self, bk_biz_id, render_type="list"):
        return f"{self.ready_container_count}/{self.total_container_count}"

    def render_images(self, bk_biz_id, render_type="list"):
        return self.images.split(",")

    def render_name(self, bk_biz_id, render_type="list"):
        if render_type == "list":
            return {
                "icon": "",
                "target": "null_event",
                "key": "",
                "url": "",
                "value": self.name,
            }
        return self.name

    def render_request_cpu_usage_ratio(self, bk_biz_id, render_type="list"):
        return get_progress_value(self.request_cpu_usage_ratio)

    def render_limit_cpu_usage_ratio(self, bk_biz_id, render_type="list"):
        return get_progress_value(self.limit_cpu_usage_ratio)

    def render_request_memory_usage_ratio(self, bk_biz_id, render_type="list"):
        return get_progress_value(self.request_memory_usage_ratio)

    def render_limit_memory_usage_ratio(self, bk_biz_id, render_type="list"):
        return get_progress_value(self.limit_memory_usage_ratio)

    @classmethod
    def update_usage_resource_and_monitor_status(
        cls, bk_biz_id: int, pods: QuerySet["BCSPod"], usages: Dict, monitor_status_map: Dict
    ) -> None:
        # 获得已存在的记录
        old_unique_hash_map = {pod.unique_hash: pod for pod in pods}

        # 获得新的记录
        new_unique_hash_map = {}
        for item in usages.values():
            keys = item["keys"]
            usage = item["usage"]
            namespace = keys["namespace"]
            name = keys["pod_name"]
            bcs_cluster_id = keys["bcs_cluster_id"]
            unique_hash = cls.hash_unique_key(bk_biz_id, bcs_cluster_id, namespace, name)
            resource_usage_cpu = usage.get("resource_usage_cpu")
            if resource_usage_cpu:
                resource_usage_cpu = round(resource_usage_cpu, 3)
            resource_usage_memory = usage.get("resource_usage_memory")
            resource_usage_disk = usage.get("resource_usage_disk")
            # 采集状态
            monitor_status = monitor_status_map.get((bcs_cluster_id, namespace, name), cls.METRICS_STATE_FAILURE)
            new_unique_hash_map[unique_hash] = {
                "resource_usage_cpu": resource_usage_cpu,
                "resource_usage_memory": resource_usage_memory,
                "resource_usage_disk": resource_usage_disk,
                "monitor_status": monitor_status,
            }

        # 更新资源使用量
        current_time = timezone.now()
        pods_for_update: List[BCSPod] = []
        unique_hash_set_for_update = set(old_unique_hash_map) & set(new_unique_hash_map)
        for unique_hash in unique_hash_set_for_update:
            pod: BCSPod = old_unique_hash_map[unique_hash]
            new_usages = new_unique_hash_map[unique_hash]
            if all(getattr(pod, usage) == value for usage, value in new_usages.items()):
                continue
            pod.resource_usage_cpu = new_usages["resource_usage_cpu"]
            pod.resource_usage_memory = new_usages["resource_usage_memory"]
            pod.resource_usage_disk = new_usages["resource_usage_disk"]
            pod.monitor_status = new_usages["monitor_status"]
            # 计算资源使用率
            pod.limit_cpu_usage_ratio = calculate_usage_ratio(pod.resource_usage_cpu, pod.resource_limits_cpu)
            pod.request_cpu_usage_ratio = calculate_usage_ratio(pod.resource_usage_cpu, pod.resource_requests_cpu)
            pod.limit_memory_usage_ratio = calculate_usage_ratio(pod.resource_usage_memory, pod.resource_limits_memory)
            pod.request_memory_usage_ratio = calculate_usage_ratio(
                pod.resource_usage_memory, pod.resource_requests_memory
            )
            pod.updated_at = current_time

            pods_for_update.append(pod)

        cls.objects.bulk_update(
            pods_for_update,
            batch_size=2000,
            fields=[
                "resource_usage_cpu",
                "resource_usage_memory",
                "resource_usage_disk",
                "monitor_status",
                "request_cpu_usage_ratio",
                "limit_cpu_usage_ratio",
                "request_memory_usage_ratio",
                "limit_memory_usage_ratio",
                "updated_at",
            ],
        )

        # 将未采集的记录设置为初始状态
        unique_hash_set_for_reset = set(old_unique_hash_map) - set(new_unique_hash_map)
        if unique_hash_set_for_reset:
            for unique_hash_chunk in chunks(list(unique_hash_set_for_reset), 1000):
                cls.objects.filter(unique_hash__in=unique_hash_chunk).update(
                    **{
                        "resource_usage_cpu": None,
                        "resource_usage_memory": None,
                        "resource_usage_disk": None,
                        "monitor_status": cls.METRICS_STATE_DISABLED,
                        "request_cpu_usage_ratio": 0,
                        "limit_cpu_usage_ratio": 0,
                        "request_memory_usage_ratio": 0,
                        "limit_memory_usage_ratio": 0,
                        "updated_at": current_time,
                    }
                )

    @classmethod
    def sync_resource_usage(cls, bk_biz_id: int, bcs_cluster_id: Optional[str] = None) -> None:
        """同步资源使用量和数据状态 ."""
        # 获得cpu, memory, disk使用量
        group_by = ["bcs_cluster_id", "namespace", "pod_name"]
        usages = cls.fetch_container_usage(bk_biz_id, bcs_cluster_id, group_by)
        # 获得资源的数据状态
        usage_resource_map = cls.get_cpu_usage_resource(usages, group_by)
        # 获得采集器的采集健康状态
        pod_models = cls.objects.filter(bk_biz_id=bk_biz_id)
        if bcs_cluster_id is not None:
            pod_models.filter(bcs_cluster_id=bcs_cluster_id)
        # 合并两个来源的数据状态
        monitor_operator_status_up_map = {}
        monitor_status_map = cls.merge_monitor_status(usage_resource_map, monitor_operator_status_up_map)
        # 更新资源使用量和数据状态
        cls.update_usage_resource_and_monitor_status(bk_biz_id, pod_models, usages, monitor_status_map)

    @classmethod
    def get_filter_workload_type(cls, params):
        return cls.get_filter_tags(params["bk_biz_id"], "workload_type")

    @classmethod
    def get_filter_name(cls, params):
        return cls.get_filter_tags(params["bk_biz_id"], "name")

    @classmethod
    def get_filter_node_ip(cls, params):
        """节点IP搜索条件 ."""
        return cls.get_filter_tags(params["bk_biz_id"], "node_ip")


class BCSPodLabels(models.Model):
    resource = models.ForeignKey(BCSPod, db_constraint=False, on_delete=models.CASCADE)
    label = models.ForeignKey(BCSLabel, db_constraint=False, on_delete=models.CASCADE)
    bcs_cluster_id = models.CharField(verbose_name="集群ID", max_length=128, db_index=True)


def calculate_usage_ratio(usage: float, limit: float, precision: int = 4) -> float:
    """计算使用率。"""
    if not (usage and limit):
        return 0
    return round(force_float(usage / limit), precision) * 100
