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
from django.utils.translation import gettext as _

from bkmonitor.models import BCSBaseManager
from bkmonitor.models.bcs_base import BCSBase, BCSLabel
from bkmonitor.models.bcs_pod import BCSPod
from bkmonitor.utils.common_utils import chunks
from core.drf_resource import api


class BCSServiceManager(BCSBaseManager):
    pass


class BCSService(BCSBase):
    name = models.CharField(max_length=128)
    namespace = models.CharField(max_length=128)
    type = models.CharField(max_length=32)
    cluster_ip = models.CharField(max_length=64)
    external_ip = models.CharField(max_length=64)
    ports = models.TextField()
    endpoint_count = models.IntegerField(default=0, null=True)
    pod_count = models.IntegerField(default=0, null=True)
    pod_name_list = models.TextField()

    labels = models.ManyToManyField(BCSLabel, through="BCSServiceLabels", through_fields=("resource", "label"))

    objects = BCSServiceManager()

    class Meta:
        unique_together = ["bcs_cluster_id", "namespace", "name"]
        index_together = ["bk_biz_id", "bcs_cluster_id"]

    def to_meta_dict(self):
        return {
            "service": self.name,
            "namespace": self.namespace,
        }

    @staticmethod
    def hash_unique_key(bk_biz_id, bcs_cluster_id, namespace, name):
        return BCSService.md5str(
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
        super(BCSBase, self).save(*args, **kwargs)

    @classmethod
    def get_columns(cls, columns_type="list"):
        columns = [
            {
                "id": "name",
                "width": 208,
                "name": _("服务名称"),
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
                    "id": "cluster_ip",
                    "name": "Cluster IP",
                    "type": "string",
                    "disabled": False,
                    "checked": False,
                },
                {
                    "id": "external_ip",
                    "name": "External IP",
                    "type": "string",
                    "disabled": False,
                    "checked": False,
                },
                {
                    "id": "ports",
                    "name": "Ports",
                    "type": "list",
                    "disabled": False,
                    "checked": False,
                },
                {
                    "id": "endpoint_count",
                    "name": _("Endpoint数量"),
                    "type": "number",
                    "disabled": False,
                    "checked": True,
                    "sortable": True,
                    "sortable_type": "progress",
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
                    "id": "pod_name_list",
                    "name": _("Pod名称"),
                    "type": "list",
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

        return columns

    @staticmethod
    def load_list_from_api(params: dict[str, tuple[str, int]]) -> list["BCSService"]:
        """
        从API获取Service列表

        Args:
            params: key为BCS集群ID，value为(租户ID, 业务ID)

        Returns:
            BCSService列表
        """
        bulk_request_params = [
            {"bcs_cluster_id": bcs_cluster_id, "bk_tenant_id": bk_tenant_id}
            for bcs_cluster_id, (bk_tenant_id, _) in params.items()
        ]
        api_services = api.kubernetes.fetch_k8s_service_list_by_cluster.bulk_request(
            bulk_request_params, ignore_exceptions=True
        )

        services = []
        for s in itertools.chain.from_iterable(item for item in api_services if item):
            bcs_cluster_id = s.get("bcs_cluster_id")
            bk_biz_id = params[bcs_cluster_id][1]
            bcs_service = BCSService()
            bcs_service.bk_biz_id = bk_biz_id
            bcs_service.bcs_cluster_id = bcs_cluster_id
            bcs_service.namespace = s.get("namespace")
            bcs_service.name = s.get("name")
            bcs_service.type = s.get("type")
            bcs_service.cluster_ip = s.get("cluster_ip")
            bcs_service.external_ip = s.get("external_ip")
            bcs_service.ports = ",".join(s.get("ports"))
            bcs_service.pod_name_list = ",".join(s.get("pod_name", []))
            bcs_service.endpoint_count = s.get("endpoint_count")
            bcs_service.pod_count = s.get("pod_count")
            bcs_service.created_at = s.get("created_at")
            bcs_service.last_synced_at = timezone.now()
            bcs_service.deleted_at = None

            # 唯一键
            bcs_service.unique_hash = bcs_service.get_unique_hash()

            bcs_service.api_labels = s.get("labels", {})
            services.append(bcs_service)
        return services

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
        search = [{"bcs_cluster_id": self.bcs_cluster_id}, {"namespace": self.namespace}, {"service_name": self.name}]
        return self.build_search_link(bk_biz_id, "pod", self.pod_count, search)

    def render_ports(self, bk_biz_id, render_type="list"):
        if not self.ports:
            self.ports = ""
        return self.ports.split(",")

    @classmethod
    def sync_resource_usage(cls, bk_biz_id: int, bcs_cluster_id: str) -> None:
        """同步数据状态 ."""
        service_models = cls.objects.filter(bk_biz_id=bk_biz_id, bcs_cluster_id=bcs_cluster_id)
        pod_models = BCSPod.objects.filter(bk_biz_id=bk_biz_id, bcs_cluster_id=bcs_cluster_id)
        # 更新数据状态
        if not api.kubernetes.has_bkm_metricbeat_endpoint_up({"bk_biz_id": bk_biz_id}):
            cls.update_monitor_status_by_pod(service_models, pod_models)
        else:
            # 获得采集器健康状态
            group_by = ["namespace", "service", "bk_endpoint_url", "code"]
            monitor_type = "ServiceMonitor"
            metric_value_dict = cls.get_monitor_beat_up_status(bk_biz_id, bcs_cluster_id, monitor_type, group_by)
            code_index = 3
            group_num = len(group_by)
            key_indexes = [0, 1]
            monitor_status_map = cls.convert_up_to_monitor_status(metric_value_dict, group_num, key_indexes, code_index)

            # 获得已存在的采集状态
            service_models = cls.objects.filter(bk_biz_id=bk_biz_id, bcs_cluster_id=bcs_cluster_id)
            old_unique_hash_map = {
                cls.hash_unique_key(bk_biz_id, bcs_cluster_id, item.namespace, item.name): item.monitor_status
                for item in service_models
            }
            # 获得新的采集状态
            new_unique_hash_map = {
                cls.hash_unique_key(bk_biz_id, bcs_cluster_id, key[0], key[1]): monitor_status
                for key, monitor_status in monitor_status_map.items()
            }
            # 更新采集状态
            unique_hash_set_for_update = set(old_unique_hash_map.keys()) & set(new_unique_hash_map.keys())
            update_items = {}
            for unique_hash in unique_hash_set_for_update:
                monitor_status = new_unique_hash_map[unique_hash]
                if monitor_status == old_unique_hash_map[unique_hash]:
                    continue
                update_items.setdefault(monitor_status, []).append(unique_hash)
            for monitor_status, unique_hash_list in update_items.items():
                for unique_hash_chunk in chunks(unique_hash_list, 1000):
                    cls.objects.filter(
                        bk_biz_id=bk_biz_id, bcs_cluster_id=bcs_cluster_id, unique_hash__in=unique_hash_chunk
                    ).update(
                        **{
                            "monitor_status": monitor_status,
                        }
                    )
            # 将未采集的记录设置为无数据
            unique_hash_set_for_reset = set(old_unique_hash_map.keys()) - set(new_unique_hash_map.keys())
            if unique_hash_set_for_reset:
                for unique_hash_chunk in chunks(list(unique_hash_set_for_reset), 1000):
                    cls.objects.filter(
                        bk_biz_id=bk_biz_id, bcs_cluster_id=bcs_cluster_id, unique_hash__in=unique_hash_chunk
                    ).update(
                        **{
                            "monitor_status": cls.METRICS_STATE_DISABLED,
                        }
                    )


class BCSServiceLabels(models.Model):
    id = models.BigAutoField(primary_key=True)
    resource = models.ForeignKey(BCSService, db_constraint=False, on_delete=models.CASCADE)
    label = models.ForeignKey(BCSLabel, db_constraint=False, on_delete=models.CASCADE)
    bcs_cluster_id = models.CharField(verbose_name="集群ID", max_length=128, db_index=True)
