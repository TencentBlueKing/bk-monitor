"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from typing import Any
from collections.abc import Generator

from django.db import models
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext as _

from bkmonitor.models import BCSBaseManager
from bkmonitor.models.bcs_base import BCSBase, BCSBaseResources, BCSLabel
from bkmonitor.utils.common_utils import chunks
from core.drf_resource import api

logger = logging.getLogger("kubernetes")


class BCSContainerManager(BCSBaseManager):
    pass


class BCSContainer(BCSBase, BCSBaseResources):
    name = models.CharField(verbose_name="名称", max_length=128)
    namespace = models.CharField(max_length=128)
    pod_name = models.CharField(max_length=128)
    workload_type = models.CharField(max_length=32)
    workload_name = models.CharField(max_length=128)
    node_ip = models.CharField(max_length=64, null=True)
    node_name = models.CharField(max_length=128)
    image = models.CharField(max_length=128)

    labels = models.ManyToManyField(BCSLabel, through="BCSContainerLabels", through_fields=("resource", "label"))

    objects = BCSContainerManager()

    class Meta:
        unique_together = ["bcs_cluster_id", "namespace", "pod_name", "name"]
        index_together = ["bk_biz_id", "bcs_cluster_id"]

    @staticmethod
    def hash_unique_key(bk_biz_id, bcs_cluster_id, namespace, pod_name, name):
        return BCSContainer.md5str(
            ",".join(
                [
                    str(bk_biz_id),
                    bcs_cluster_id,
                    namespace,
                    pod_name,
                    name,
                ]
            )
        )

    def get_unique_hash(self):
        return self.hash_unique_key(self.bk_biz_id, self.bcs_cluster_id, self.namespace, self.pod_name, self.name)

    def save(self, *args, **kwargs):
        self.unique_hash = self.get_unique_hash()
        super().save(*args, **kwargs)

    def to_meta_dict(self):
        return {
            "pod": self.pod_name,
            "container": self.name,
            "namespace": self.namespace,
            "workload": f"{self.workload_type}:{self.workload_name}",
        }

    @classmethod
    def get_columns(cls, columns_type="list"):
        columns = [
            {
                "id": "name",
                "width": 208,
                "name": _("容器名称"),
                "type": "link" if columns_type == "list" else "string",
                "disabled": False,
                "checked": True,
                "overview": "name",
                "overview_name": _("概览"),
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
                    "name": "NameSpace",
                    "type": "string",
                    "disabled": False,
                    "checked": True,
                    "filterable": True,
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
                    "id": "pod_name",
                    "name": _("Pod名称"),
                    "type": "link",
                    "disabled": False,
                    "checked": True,
                },
                {
                    "id": "workload",
                    "name": _("工作负载"),
                    "type": "link",
                    "disabled": False,
                    "checked": False,
                },
                {
                    "id": "node_name",
                    "name": _("节点名称"),
                    "type": "link",
                    "disabled": False,
                    "checked": True,
                },
                {
                    "id": "node_ip",
                    "name": _("节点IP"),
                    "type": "link",
                    "disabled": False,
                    "checked": False,
                },
                {
                    "id": "image",
                    "name": _("镜像"),
                    "type": "string",
                    "disabled": False,
                    "checked": False,
                },
                {
                    "id": "resource_usage_cpu",
                    "name": _("CPU使用量"),
                    "type": "string",
                    "disabled": False,
                    "checked": True,
                    "sortable": True,
                    "sortable_type": "progress",
                },
                {
                    "id": "resource_usage_memory",
                    "name": _("内存使用量"),
                    "type": "string",
                    "disabled": False,
                    "checked": True,
                    "sortable": True,
                    "sortable_type": "progress",
                },
                {
                    "id": "resource_usage_disk",
                    "name": _("磁盘使用量"),
                    "type": "string",
                    "disabled": False,
                    "checked": True,
                    "sortable": True,
                    "sortable_type": "progress",
                },
                {
                    "id": "age",
                    "name": _("存活时间"),
                    "type": "string",
                    "disabled": False,
                    "checked": True,
                },
            ]
        )

        return columns

    @staticmethod
    def load_list_from_api(params: dict[str, Any]) -> Generator["BCSContainer", Any, None]:
        """
        从API获取Container列表

        Args:
            params: 请求参数
                bk_tenant_id: 租户ID
                bk_biz_id: 业务ID
                bcs_cluster_id: 集群ID
        """
        bk_tenant_id = params["bk_tenant_id"]
        bcs_cluster_id = params["bcs_cluster_id"]
        bk_biz_id = params["bk_biz_id"]

        for c in api.kubernetes.fetch_k8s_container_list_by_cluster(
            bk_tenant_id=bk_tenant_id, bcs_cluster_id=bcs_cluster_id
        ):
            bcs_cluster_id = c.get("bcs_cluster_id")
            bcs_container = BCSContainer()
            bcs_container.bk_biz_id = bk_biz_id
            bcs_container.bcs_cluster_id = bcs_cluster_id
            bcs_container.namespace = c.get("namespace")
            bcs_container.name = c.get("name")
            bcs_container.pod_name = c.get("pod_name")
            bcs_container.workload_type = c.get("workload_type")
            bcs_container.workload_name = c.get("workload_name")
            bcs_container.node_ip = c.get("node_ip")
            bcs_container.node_name = c.get("node_name")
            bcs_container.resource_requests_cpu = c.get("requests_cpu")
            bcs_container.resource_requests_memory = c.get("requests_memory")
            bcs_container.resource_limits_cpu = c.get("limits_cpu")
            bcs_container.resource_limits_memory = c.get("limits_memory")
            bcs_container.image = c.get("image")
            bcs_container.created_at = parse_datetime(c.get("created_at"))
            bcs_container.status = c.get("status")
            bcs_container.last_synced_at = timezone.now()
            bcs_container.deleted_at = None

            # 唯一键
            bcs_container.unique_hash = bcs_container.get_unique_hash()

            bcs_container.api_labels = c.get("labels", {})
            yield bcs_container

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

    def render_workload(self, bk_biz_id, render_type="list"):
        value = f"{self.workload_type}:{self.workload_name}"
        search = [
            {"bcs_cluster_id": self.bcs_cluster_id},
            {"workload_type": self.workload_type},
            {"name": self.workload_name},
        ]
        return self.build_search_link(bk_biz_id, "workload", value, search)

    def render_bcs_cluster_id(self, bk_biz_id, render_type="list"):
        search = [{"bcs_cluster_id": self.bcs_cluster_id}]
        return self.build_search_link(bk_biz_id, "cluster", self.bcs_cluster_id, search)

    def render_pod_name(self, bk_biz_id, render_type="list"):
        search = [{"bcs_cluster_id": self.bcs_cluster_id}, {"name": self.pod_name}]
        return self.build_search_link(bk_biz_id, "pod", self.pod_name, search)

    def render_node_name(self, bk_biz_id, render_type="list"):
        search = [{"bcs_cluster_id": self.bcs_cluster_id}, {"name": self.node_name}]
        return self.build_search_link(bk_biz_id, "node", self.node_name, search)

    def render_node_ip(self, bk_biz_id, render_type="list"):
        search = [{"bcs_cluster_id": self.bcs_cluster_id}, {"ip": self.node_ip}]
        return self.build_search_link(bk_biz_id, "node", self.node_ip, search)

    @classmethod
    def update_usage_resource_and_monitor_status(
        cls, bk_biz_id: int, bcs_cluster_id: str, models: BCSBase, usages: dict, monitor_status_map: dict
    ) -> None:
        # 获得已存在的记录
        old_unique_hash_map = {
            model.unique_hash: (
                model.resource_usage_cpu,
                model.resource_usage_memory,
                model.resource_usage_disk,
                model.monitor_status,
            )
            for model in models
        }

        # 获得新的记录
        new_unique_hash_map = {}
        for item in usages.values():
            keys = item["keys"]
            usage = item["usage"]
            namespace = keys["namespace"]
            pod_name = keys["pod_name"]
            name = keys["container_name"]
            unique_hash = cls.hash_unique_key(bk_biz_id, bcs_cluster_id, namespace, pod_name, name)
            resource_usage_cpu = usage.get("resource_usage_cpu")
            if resource_usage_cpu:
                resource_usage_cpu = round(resource_usage_cpu, 3)
            resource_usage_memory = usage.get("resource_usage_memory")
            resource_usage_disk = usage.get("resource_usage_disk")
            monitor_status = monitor_status_map.get((namespace, pod_name, name), cls.METRICS_STATE_FAILURE)
            new_unique_hash_map[unique_hash] = (
                resource_usage_cpu,
                resource_usage_memory,
                resource_usage_disk,
                monitor_status,
            )

        # 更新资源使用量
        unique_hash_set_for_update = set(old_unique_hash_map.keys()) & set(new_unique_hash_map.keys())
        for unique_hash in unique_hash_set_for_update:
            if new_unique_hash_map[unique_hash] == old_unique_hash_map[unique_hash]:
                continue
            update_kwargs = new_unique_hash_map[unique_hash]
            resource_usage_cpu = update_kwargs[0]
            resource_usage_memory = update_kwargs[1]
            resource_usage_disk = update_kwargs[2]
            monitor_status = update_kwargs[3]
            cls.objects.filter(unique_hash=unique_hash).update(
                **{
                    "resource_usage_cpu": resource_usage_cpu,
                    "resource_usage_memory": resource_usage_memory,
                    "resource_usage_disk": resource_usage_disk,
                    "monitor_status": monitor_status,
                }
            )

        # 将未采集的记录设置为初始状态
        unique_hash_set_for_reset = set(old_unique_hash_map.keys()) - set(new_unique_hash_map.keys())
        if unique_hash_set_for_reset:
            for unique_hash_chunk in chunks(list(unique_hash_set_for_reset), 1000):
                cls.objects.filter(unique_hash__in=unique_hash_chunk).update(
                    **{
                        "resource_usage_cpu": None,
                        "resource_usage_memory": None,
                        "resource_usage_disk": None,
                        "monitor_status": cls.METRICS_STATE_DISABLED,
                    }
                )

    @classmethod
    def sync_resource_usage(cls, bk_biz_id: int, bcs_cluster_id: str) -> None:
        """同步资源使用量和数据状态 ."""
        # 获得cpu, memory, disk使用量
        group_by = ["namespace", "pod_name", "container_name"]
        usages = cls.fetch_container_usage(bk_biz_id, bcs_cluster_id, group_by)
        # 获得资源的数据状态
        usage_resource_map = cls.get_cpu_usage_resource(usages, group_by)
        # 获得采集器的采集健康状态
        container_models = cls.objects.filter(bk_biz_id=bk_biz_id, bcs_cluster_id=bcs_cluster_id)
        # 合并两个来源的数据状态
        monitor_operator_status_up_map = {}
        monitor_status_map = cls.merge_monitor_status(usage_resource_map, monitor_operator_status_up_map)
        # 更新资源使用量和数据状态
        cls.update_usage_resource_and_monitor_status(
            bk_biz_id, bcs_cluster_id, container_models, usages, monitor_status_map
        )

    @classmethod
    def get_filter_workload_type(cls, params):
        return cls.get_filter_tags(params["bk_biz_id"], "workload_type")

    @classmethod
    def get_filter_pod_name(cls, params):
        return cls.get_filter_tags(params["bk_biz_id"], "pod_name")

    @classmethod
    def get_filter_node_ip(cls, params):
        return cls.get_filter_tags(params["bk_biz_id"], "node_ip")


class BCSContainerLabels(models.Model):
    id = models.BigAutoField(primary_key=True)
    resource = models.ForeignKey(BCSContainer, db_constraint=False, on_delete=models.CASCADE)
    label = models.ForeignKey(BCSLabel, db_constraint=False, on_delete=models.CASCADE)
    bcs_cluster_id = models.CharField(verbose_name="集群ID", max_length=128, db_index=True)
