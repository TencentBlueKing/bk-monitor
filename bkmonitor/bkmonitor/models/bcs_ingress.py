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
from core.drf_resource import api


class BCSIngressManager(BCSBaseManager):
    pass


class BCSIngress(BCSBase):
    name = models.CharField(max_length=128)
    namespace = models.CharField(max_length=128)
    class_name = models.CharField(max_length=128)
    service_list = models.TextField()

    labels = models.ManyToManyField(BCSLabel, through="BCSIngressLabels", through_fields=("resource", "label"))

    objects = BCSIngressManager()

    class Meta:
        unique_together = ["bcs_cluster_id", "namespace", "name"]
        index_together = ["bk_biz_id", "bcs_cluster_id"]

    def to_meta_dict(self):
        return {
            "ingress": self.name,
            "namespace": self.namespace,
        }

    @staticmethod
    def hash_unique_key(bk_biz_id, bcs_cluster_id, namespace, name):
        return BCSIngress.md5str(
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
                "name": _("名称"),
                "type": "string",
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
                    "id": "class_name",
                    "name": "Class",
                    "type": "string",
                    "disabled": False,
                    "checked": True,
                    "filterable": True,
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
    def load_list_from_api(params: dict[str, tuple[str, int]]) -> list["BCSIngress"]:
        """
        从API获取Ingress列表

        Args:
            params: key为BCS集群ID，value为(租户ID, 业务ID)

        Returns:
            BCSIngress列表
        """
        bulk_request_params = [
            {"bcs_cluster_id": bcs_cluster_id, "bk_tenant_id": bk_tenant_id}
            for bcs_cluster_id, (bk_tenant_id, _) in params.items()
        ]
        api_ingress = api.kubernetes.fetch_k8s_ingress_list_by_cluster.bulk_request(
            bulk_request_params, ignore_exceptions=True
        )

        ingress_list = []
        for ingress in itertools.chain.from_iterable(item for item in api_ingress if item):
            bcs_cluster_id = ingress.get("bcs_cluster_id")
            bk_biz_id = params[bcs_cluster_id][1]
            bcs_ingress = BCSIngress()
            bcs_ingress.bk_biz_id = bk_biz_id
            bcs_ingress.bcs_cluster_id = bcs_cluster_id
            bcs_ingress.namespace = ingress.get("namespace")
            bcs_ingress.name = ingress.get("name")
            bcs_ingress.class_name = ingress.get("class_name") or "-"
            bcs_ingress.service_list = ",".join(ingress.get("service_list", []))
            bcs_ingress.created_at = ingress.get("created_at")
            bcs_ingress.last_synced_at = timezone.now()
            bcs_ingress.deleted_at = None

            # 唯一键
            bcs_ingress.unique_hash = bcs_ingress.get_unique_hash()

            bcs_ingress.api_labels = ingress.get("labels", {})
            ingress_list.append(bcs_ingress)
        return ingress_list

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

    def render_service_list(self, bk_biz_id, render_type="list"):
        if not self.service_list:
            self.service_list = "-"
        return self.service_list.split(",")

    def render_bcs_cluster_id(self, bk_biz_id, render_type="list"):
        search = [{"bcs_cluster_id": self.bcs_cluster_id}]
        return self.build_search_link(bk_biz_id, "cluster", self.bcs_cluster_id, search)


class BCSIngressLabels(models.Model):
    id = models.BigAutoField(primary_key=True)
    resource = models.ForeignKey(BCSIngress, db_constraint=False, on_delete=models.CASCADE)
    label = models.ForeignKey(BCSLabel, db_constraint=False, on_delete=models.CASCADE)
    bcs_cluster_id = models.CharField(verbose_name="集群ID", max_length=128, db_index=True)
