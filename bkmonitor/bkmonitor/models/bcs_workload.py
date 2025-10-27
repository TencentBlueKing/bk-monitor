"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import itertools

from django.db import models
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext as _

from bkmonitor.models import BCSBase, BCSBaseManager, BCSBaseResources, BCSLabel, BCSPod
from core.drf_resource import api


class BCSWorkloadManager(BCSBaseManager):
    pass


class BCSWorkload(BCSBase, BCSBaseResources):
    type = models.CharField(max_length=128)
    name = models.CharField(max_length=128)
    namespace = models.CharField(max_length=128)
    pod_name_list = models.TextField()
    images = models.TextField()
    pod_count = models.IntegerField()
    container_count = models.IntegerField(default=0)

    labels = models.ManyToManyField(BCSLabel, through="BCSWorkloadLabels", through_fields=("resource", "label"))

    objects = BCSWorkloadManager()

    class Meta:
        unique_together = ["bcs_cluster_id", "namespace", "type", "name"]
        index_together = ["bk_biz_id", "bcs_cluster_id"]

    @staticmethod
    def hash_unique_key(bk_biz_id, bcs_cluster_id, namespace, workload_type, name):
        return BCSWorkload.md5str(
            ",".join(
                [
                    str(bk_biz_id),
                    bcs_cluster_id,
                    namespace,
                    workload_type,
                    name,
                ]
            )
        )

    def get_unique_hash(self):
        return self.hash_unique_key(self.bk_biz_id, self.bcs_cluster_id, self.namespace, self.type, self.name)

    def save(self, *args, **kwargs):
        self.unique_hash = self.get_unique_hash()
        super().save(*args, **kwargs)

    def to_meta_dict(self):
        return {
            "namespace": self.namespace,
            "workload": f"{self.type}:{self.name}",
        }

    @classmethod
    def get_columns(cls, columns_type="list"):
        typed_columns = []

        column_map = {
            "ready": {
                "id": "ready",
                "name": _("Ready数量"),
                "type": "string",
                "disabled": False,
                "checked": True,
            },
            "up_to_date": {
                "id": "up_to_date",
                "name": _("Up To Date数量"),
                "type": "string",
                "disabled": False,
                "checked": True,
            },
            "available": {
                "id": "available",
                "name": _("Available数量"),
                "type": "string",
                "disabled": False,
                "checked": True,
            },
            "desired": {
                "id": "desired",
                "name": "Desired",
                "type": "string",
                "disabled": False,
                "checked": True,
            },
            "current": {
                "id": "current",
                "name": "Current",
                "type": "string",
                "disabled": False,
                "checked": True,
            },
            "schedule": {
                "id": "schedule",
                "name": "Schedule",
                "type": "string",
                "disabled": False,
                "checked": True,
            },
            "suspend": {
                "id": "suspend",
                "name": "Suspend",
                "type": "string",
                "disabled": False,
                "checked": True,
            },
            "active": {
                "id": "active",
                "name": "Active",
                "type": "string",
                "disabled": False,
                "checked": True,
            },
            "last_schedule": {
                "id": "last_schedule",
                "name": "Last Schedule",
                "type": "string",
                "disabled": False,
                "checked": True,
            },
            "completions": {
                "id": "completions",
                "name": "Completions",
                "type": "string",
                "disabled": False,
                "checked": True,
            },
            "duration": {
                "id": "duration",
                "name": "Duration",
                "type": "string",
                "disabled": False,
                "checked": True,
            },
        }
        if columns_type == "Deployment":
            typed_columns = [
                column_map["ready"],
                column_map["up_to_date"],
                column_map["available"],
            ]
        elif columns_type == "StatefulSet":
            typed_columns = [
                column_map["ready"],
            ]
        elif columns_type == "DaemonSet":
            typed_columns = [
                column_map["desired"],
                column_map["current"],
                column_map["ready"],
                column_map["up_to_date"],
                column_map["available"],
            ]
        elif columns_type == "CronJob":
            typed_columns = [
                column_map["schedule"],
                column_map["suspend"],
                column_map["active"],
                column_map["last_schedule"],
            ]
        elif columns_type == "Job":
            typed_columns = [
                column_map["completions"],
                column_map["duration"],
            ]

        default_columns = [
            {
                "id": "name",
                "width": 208,
                "name": _("工作负载名称"),
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

        columns = cls.add_cluster_column(default_columns, columns_type)

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
                    "id": "type",
                    "name": _("类型"),
                    "type": "string",
                    "disabled": False,
                    "checked": True,
                    "filterable": True,
                },
                {
                    "id": "images",
                    "name": _("镜像"),
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
                    "id": "pod_count",
                    "name": _("Pod数量"),
                    "type": "link",
                    "disabled": False,
                    "checked": True,
                    "sortable": True,
                    "sortable_type": "progress",
                },
                {
                    "id": "container_count",
                    "name": _("容器数量"),
                    "type": "link",
                    "disabled": False,
                    "checked": False,
                },
                {
                    "id": "resources",
                    "name": _("资源"),
                    "type": "kv",
                    "disabled": False,
                    "checked": False,
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

        columns.extend(typed_columns)

        return columns

    @staticmethod
    def load_list_from_api(params: dict[str, tuple[str, int]]) -> list["BCSWorkload"]:
        """
        从API获取工作负载列表

        Args:
            params: key为BCS集群ID，value为(租户ID, 业务ID)

        Returns:
            BCSWorkload列表
        """
        bulk_request_params = [
            {"bcs_cluster_id": bcs_cluster_id, "bk_tenant_id": bk_tenant_id}
            for bcs_cluster_id, (bk_tenant_id, _) in params.items()
        ]
        api_workloads = api.kubernetes.fetch_k8s_workload_list_by_cluster.bulk_request(
            bulk_request_params, ignore_exceptions=True
        )

        workloads = []
        for w in itertools.chain.from_iterable(item for item in api_workloads if item):
            # 忽略非顶层的workload，包含两种情况
            # 1. Job是从CronJob生成的
            # 2. ReplicaSet是从Deployment生成的
            top_workload_type = w.get("top_workload_type")
            if top_workload_type or not w.get("namespace"):
                continue

            bcs_cluster_id = w.get("bcs_cluster_id")
            bk_biz_id = params[bcs_cluster_id][1]
            bcs_workload = BCSWorkload()
            bcs_workload.bk_biz_id = bk_biz_id
            bcs_workload.bcs_cluster_id = bcs_cluster_id
            bcs_workload.namespace = w.get("namespace")
            bcs_workload.type = w.get("workload_type")
            bcs_workload.name = w.get("name")
            bcs_workload.pod_name_list = ",".join(w.get("pod_name", []))
            bcs_workload.images = w.get("images", "")
            bcs_workload.pod_count = w.get("pod_count", 0)
            bcs_workload.container_count = w.get("container_number", 0)
            bcs_workload.resource_requests_cpu = w.get("requests_cpu", 0)
            bcs_workload.resource_requests_memory = w.get("requests_memory", 0)
            bcs_workload.resource_limits_cpu = w.get("limits_cpu", 0)
            bcs_workload.resource_limits_memory = w.get("limits_memory", 0)
            bcs_workload.created_at = parse_datetime(w.get("created_at"))
            bcs_workload.status = w.get("status")
            bcs_workload.last_synced_at = timezone.now()
            bcs_workload.deleted_at = None

            # 唯一键
            bcs_workload.unique_hash = bcs_workload.get_unique_hash()

            bcs_workload.api_labels = w.get("labels", {})
            workloads.append(bcs_workload)
        return workloads

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

    def render_pod_name_list(self, bk_biz_id, render_type="list"):
        if not self.pod_name_list:
            self.pod_name_list = "not found"
        return self.pod_name_list.split(",")

    def render_bcs_cluster_id(self, bk_biz_id, render_type="list"):
        search = [{"bcs_cluster_id": self.bcs_cluster_id}]
        return self.build_search_link(bk_biz_id, "cluster", self.bcs_cluster_id, search)

    def render_pod_count(self, bk_biz_id, render_type="list"):
        search = [{"bcs_cluster_id": self.bcs_cluster_id}, {"workload_name": self.name}]
        return self.build_search_link(bk_biz_id, "pod", self.pod_count, search)

    def render_container_count(self, bk_biz_id, render_type="list"):
        search = [{"bcs_cluster_id": self.bcs_cluster_id}, {"workload_name": self.name}]
        return self.build_search_link(bk_biz_id, "container", self.container_count, search)

    @staticmethod
    def get_cpu_usage_resource(bk_biz_id, bcs_cluster_id):
        # 获得Pod的CPU使用量
        pod_items = BCSPod.objects.filter(bk_biz_id=bk_biz_id, bcs_cluster_id=bcs_cluster_id).values(
            "namespace", "name", "resource_usage_cpu"
        )
        data = {}
        for pod_item in pod_items:
            namespace = pod_item["namespace"]
            pod_name = pod_item["name"]
            resource_usage_cpu = pod_item["resource_usage_cpu"]
            if resource_usage_cpu is None:
                continue
            else:
                data[(namespace, pod_name)] = resource_usage_cpu

        return data

    @classmethod
    def sync_resource_usage(cls, bk_biz_id: int, bcs_cluster_id: str) -> None:
        """同步数据状态 ."""
        workload_models = cls.objects.filter(bk_biz_id=bk_biz_id, bcs_cluster_id=bcs_cluster_id)
        pod_models = BCSPod.objects.filter(bk_biz_id=bk_biz_id, bcs_cluster_id=bcs_cluster_id)
        # 更新数据状态
        cls.update_monitor_status_by_pod(workload_models, pod_models)

    @classmethod
    def get_filter_workload_type(cls, params):
        return cls.get_filter_tags(params["bk_biz_id"], "type", display_name="workload_type")


class BCSWorkloadLabels(models.Model):
    id = models.BigAutoField(primary_key=True)
    resource = models.ForeignKey(BCSWorkload, db_constraint=False, on_delete=models.CASCADE)
    label = models.ForeignKey(BCSLabel, db_constraint=False, on_delete=models.CASCADE)
    bcs_cluster_id = models.CharField(verbose_name="集群ID", max_length=128, db_index=True)
