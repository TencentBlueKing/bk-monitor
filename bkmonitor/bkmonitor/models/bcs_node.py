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
import itertools
import logging
import operator
from functools import reduce
from typing import Dict

from django.core.exceptions import EmptyResultSet
from django.db import models
from django.db.models import Q
from django.db.models.query import QuerySet
from django.utils import timezone
from django.utils.translation import ugettext as _

from bkmonitor.models import BCSBaseManager
from bkmonitor.models.bcs_base import BCSBase, BCSBaseUsageResources, BCSLabel
from bkmonitor.utils.common_utils import chunks
from bkmonitor.utils.ip import is_v6
from bkmonitor.utils.kubernetes import BcsClusterType
from core.drf_resource import api

logger = logging.getLogger("kubernetes")


class BCSNodeManager(BCSBaseManager):
    def get_queryset(self):
        # 忽略 eks节点
        return super(BCSNodeManager, self).get_queryset().exclude(name__startswith="eklet-")

    def filter_by_biz_id(
        self,
        bk_biz_id: int,
    ) -> QuerySet:
        """获得资源查询QuerySet ."""
        query_set = Q(bk_biz_id=bk_biz_id)
        if bk_biz_id < 0:
            # 获得bcs空间下的所有集群
            clusters = api.kubernetes.get_cluster_info_from_bcs_space({"bk_biz_id": bk_biz_id})
            if not clusters:
                # 业务下没有集群
                raise EmptyResultSet

            shared_q_list = []
            for cluster_id, value in clusters.items():
                cluster_type = value.get("cluster_type")
                if cluster_type == BcsClusterType.SINGLE:
                    # 只包含bcs空间下的独立集群
                    shared_q_list.append(Q(bcs_cluster_id=cluster_id))
            if shared_q_list:
                query_set = reduce(operator.or_, shared_q_list)
            else:
                # 全部都是共享集群
                raise EmptyResultSet

        return self.filter(query_set)

    def search_control_plane_nodes(self, bk_biz_id: int, bcs_cluster_id: str) -> QuerySet:
        """查询控制节点 ."""
        q = Q(bcs_cluster_id=bcs_cluster_id) & (Q(roles__contains="control-plane") | Q(roles__contains="master"))

        return self.filter_by_biz_id(bk_biz_id).filter(q)

    def search_work_nodes(self, bk_biz_id: int, bcs_cluster_id: str) -> QuerySet:
        """查询工作节点 ."""
        q = Q(bcs_cluster_id=bcs_cluster_id) & ~(Q(roles__contains="control-plane") | Q(roles__contains="master"))
        return self.filter_by_biz_id(bk_biz_id).filter(q)

    def build_promql_param_instance(self, bk_biz_id: int, bcs_cluster_id: str) -> str:
        """构造node节点ip在promql中的instance查询 ."""
        try:
            node_list = self.search_work_nodes(bk_biz_id, bcs_cluster_id)
        except EmptyResultSet:
            node_list = []
        if not node_list:
            return None
        # ipv6 的 instance 的格式形如：[x:x:x:x:x:x:x:x]:port
        ip_list = [f"\\\\[{node.ip}\\\\]:" if is_v6(node.ip) else f"{node.ip}:" for node in node_list if node.ip]
        instance = "^({})".format("|".join(ip_list))
        return instance


class BCSNode(BCSBase, BCSBaseUsageResources):
    name = models.CharField(max_length=128)
    roles = models.CharField(max_length=128, null=True)
    cloud_id = models.CharField(max_length=32)
    ip = models.CharField(max_length=64)
    bk_host_id = models.IntegerField(null=True)
    endpoint_count = models.IntegerField()
    pod_count = models.IntegerField()
    taints = models.TextField(null=True)
    labels = models.ManyToManyField(BCSLabel, through="BCSNodeLabels", through_fields=("resource", "label"))

    objects = BCSNodeManager()

    class Meta:
        unique_together = ["bcs_cluster_id", "name"]
        index_together = ["bk_biz_id", "bcs_cluster_id"]

    @staticmethod
    def hash_unique_key(bk_biz_id, bcs_cluster_id, name):
        return BCSNode.md5str(
            ",".join(
                [
                    str(bk_biz_id),
                    bcs_cluster_id,
                    name,
                ]
            )
        )

    def get_unique_hash(self):
        return self.hash_unique_key(self.bk_biz_id, self.bcs_cluster_id, self.name)

    def save(self, *args, **kwargs):
        self.unique_hash = self.get_unique_hash()
        super().save(*args, **kwargs)

    @classmethod
    def get_columns(cls, columns_type="list"):
        columns = [
            {
                "id": "name",
                "width": 208,
                "name": _("节点名称"),
                "type": "link" if columns_type == "list" else "string",
                "disabled": True,
                "checked": True,
                "overview": "name",
                "overview_name": _("概览"),
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
                    "id": "node_ip",
                    "name": _("节点IP"),
                    "type": "link",
                    "disabled": False,
                    "checked": True,
                },
                {
                    "id": "cloud_id",
                    "name": _("云区域"),
                    "type": "string",
                    "disabled": False,
                    "checked": False,
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
                    "id": "system_cpu_summary_usage",
                    "name": _("CPU使用率"),
                    "type": "progress",
                    "disabled": False,
                    "checked": True,
                    "sortable": True,
                    "sortable_type": "progress",
                    "header_pre_icon": "icon-avg",
                },
                {
                    "id": "system_mem_pct_used",
                    "name": _("应用内存使用率"),
                    "type": "progress",
                    "disabled": False,
                    "checked": True,
                    "sortable": True,
                    "sortable_type": "progress",
                    "header_pre_icon": "icon-avg",
                },
                {
                    "id": "system_io_util",
                    "name": _("磁盘IO使用率"),
                    "type": "progress",
                    "disabled": False,
                    "checked": False,
                    "sortable": True,
                    "sortable_type": "progress",
                },
                {
                    "id": "system_disk_in_use",
                    "name": _("磁盘空间使用率"),
                    "type": "progress",
                    "disabled": False,
                    "checked": True,
                    "sortable": True,
                    "sortable_type": "progress",
                    "header_pre_icon": "icon-avg",
                },
                {
                    "id": "system_load_load15",
                    "name": _("CPU十五分钟负载"),
                    "type": "str",
                    "disabled": False,
                    "checked": False,
                    "sortable": True,
                },
                {
                    "id": "taints",
                    "name": _("污点"),
                    "type": "list",
                    "disabled": False,
                    "checked": False,
                },
                {
                    "id": "node_roles",
                    "name": _("角色"),
                    "type": "list",
                    "disabled": False,
                    "checked": False,
                },
                {
                    "id": "endpoint_count",
                    "name": _("Endpoint数量"),
                    "type": "number",
                    "disabled": False,
                    "checked": False,
                    "sortable": True,
                    "sortable_type": "progress",
                },
                {
                    "id": "label_list",
                    "name": _("标签"),
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

        return columns

    def get_host_link(self, value_field="ip"):
        if self.bk_host_id:
            url = f"?bizId={self.bk_biz_id}#/performance/detail/{self.bk_host_id}"
        else:
            url = f"?bizId={self.bk_biz_id}#/performance/detail/{self.ip}-{self.cloud_id or 0}"
        return {
            "value": getattr(self, value_field),
            "url": url,
            "target": "blank",
        }

    @staticmethod
    def load_list_from_api(params):
        bulk_request_params = [{"bcs_cluster_id": bcs_cluster_id} for bcs_cluster_id in params.keys()]
        api_nodes = api.kubernetes.fetch_k8s_node_list_by_cluster.bulk_request(
            bulk_request_params, ignore_exceptions=True
        )
        # 获得云区域ID
        bcs_cluster_id_list = list(params.keys())
        cloud_info_list = api.kubernetes.fetch_k8s_cloud_id_by_cluster({"bcs_cluster_ids": bcs_cluster_id_list})
        cloud_id_map = {
            cloud_info["bcs_cluster_id"]: cloud_info["bk_cloud_id"] for cloud_info in cloud_info_list if cloud_info
        }
        nodes = []
        for n in itertools.chain.from_iterable(item for item in api_nodes if item):
            bcs_cluster_id = n.get("bcs_cluster_id")
            bk_biz_id = params[bcs_cluster_id]
            bcs_node = BCSNode()
            bcs_node.bk_biz_id = bk_biz_id
            bcs_node.bcs_cluster_id = bcs_cluster_id
            bcs_node.name = n.get("name")
            bcs_node.taints = ",".join(n.get("taints", []))
            bcs_node.roles = ",".join(n.get("node_roles", []))
            bcs_node.ip = n.get("node_ip")
            bcs_node.endpoint_count = n.get("endpoint_count", 0)
            bcs_node.pod_count = n.get("pod_count", 0)
            bcs_node.created_at = n.get("created_at")
            bcs_node.status = n.get("status")
            bcs_node.last_synced_at = timezone.now()
            bcs_node.deleted_at = None
            # 云区域ID
            cloud_id = cloud_id_map.get(bcs_cluster_id)
            cloud_id = cloud_id if cloud_id else 0
            bcs_node.cloud_id = str(cloud_id)

            # 唯一键
            bcs_node.unique_hash = bcs_node.get_unique_hash()

            bcs_node.api_labels = n.get("labels", {})
            nodes.append(bcs_node)

        return nodes

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

    def render_bcs_cluster_id(self, bk_biz_id, render_type="list"):
        search = [{"bcs_cluster_id": self.bcs_cluster_id}]
        return self.build_search_link(bk_biz_id, "cluster", self.bcs_cluster_id, search)

    def render_pod_count(self, bk_biz_id, render_type="list"):
        search = [{"bcs_cluster_id": self.bcs_cluster_id}, {"node_ip": self.ip}]
        return self.build_search_link(bk_biz_id, "pod", self.pod_count, search)

    def render_node_ip(self, bk_biz_id, render_type="list"):
        return self.get_host_link()

    def render_bk_host_id(self, bk_biz_id, render_type="list"):
        return self.get_host_link("bk_host_id")

    def render_node_roles(self, bk_biz_id, render_type="list"):
        if self.roles:
            return self.roles.split(",")
        return []

    def render_taints(self, bk_biz_id, render_type="list"):
        if self.taints:
            return self.taints.split(",")
        return []

    @staticmethod
    def get_monitor_status_by_usage(bk_biz_id: int, bcs_cluster_id: str) -> Dict:
        """根据cpu资源获取数据状态 ."""
        params = {
            "bk_biz_id": bk_biz_id,
            "bcs_cluster_id": bcs_cluster_id,
        }
        # 根据CPU的指标值是否存在判断数据状态
        data = api.kubernetes.fetch_node_cpu_usage(params)
        return data

    @classmethod
    def sync_resource_usage(cls, bk_biz_id, bcs_cluster_id) -> None:
        """同步node的数据状态 ."""
        usage_resource_map = {}
        monitor_operator_status_up_map = {}
        if not api.kubernetes.has_bkm_metricbeat_endpoint_up({"bk_biz_id": bk_biz_id}):
            # 获得资源的数据状态
            usage_resource_map = cls.get_monitor_status_by_usage(bk_biz_id, bcs_cluster_id)
            usage_resource_map = {(ip,): monitor_status for ip, monitor_status in usage_resource_map.items()}
        else:
            # 获得采集器的采集健康状态
            group_by = ["node", "code"]
            monitor_type = "ServiceMonitor"
            metric_value_dict = cls.get_monitor_beat_up_status(bk_biz_id, bcs_cluster_id, monitor_type, group_by)
            code_index = 1
            group_num = len(group_by)
            key_indexes = [0]
            monitor_operator_status_up_map = cls.convert_up_to_monitor_status(
                metric_value_dict, group_num, key_indexes, code_index
            )

        # 合并两个来源的数据状态
        monitor_status_map = cls.merge_monitor_status(usage_resource_map, monitor_operator_status_up_map)
        # 获得已存在的记录
        node_models = cls.objects.filter(bk_biz_id=bk_biz_id, bcs_cluster_id=bcs_cluster_id)
        old_unique_hash_map = {(bk_biz_id, bcs_cluster_id, item.ip): item.monitor_status for item in node_models}
        # 更新资源使用量
        new_unique_hash_map = {(bk_biz_id, bcs_cluster_id, key[0]): value for key, value in monitor_status_map.items()}
        unique_hash_set_for_update = set(old_unique_hash_map.keys()) & set(new_unique_hash_map.keys())
        for unique_hash in unique_hash_set_for_update:
            monitor_status = new_unique_hash_map[unique_hash]
            if monitor_status == old_unique_hash_map[unique_hash]:
                continue
            ip = unique_hash[2]
            cls.objects.filter(bk_biz_id=bk_biz_id, bcs_cluster_id=bcs_cluster_id, ip=ip).update(
                **{
                    "monitor_status": monitor_status,
                }
            )
        # 将未采集的记录设置为无数据
        unique_hash_set_for_reset = set(old_unique_hash_map.keys()) - set(new_unique_hash_map.keys())
        if unique_hash_set_for_reset:
            for unique_hash_chunk in chunks(list(unique_hash_set_for_reset), 1000):
                ip_list = [item[2] for item in unique_hash_chunk]
                cls.objects.filter(bk_biz_id=bk_biz_id, bcs_cluster_id=bcs_cluster_id, ip__in=ip_list).update(
                    **{
                        "monitor_status": cls.METRICS_STATE_DISABLED,
                    }
                )

    @classmethod
    def get_filter_node_ip(cls, params):
        return cls.get_filter_tags(params["bk_biz_id"], "ip", display_name="node_ip")

    @classmethod
    def get_filter_roles(cls, params):
        return cls.get_filter_tags(params["bk_biz_id"], "roles")


class BCSNodeLabels(models.Model):
    resource = models.ForeignKey(BCSNode, db_constraint=False, on_delete=models.CASCADE)
    label = models.ForeignKey(BCSLabel, db_constraint=False, on_delete=models.CASCADE)
    bcs_cluster_id = models.CharField(verbose_name="集群ID", max_length=128, db_index=True)
