"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import abc
import itertools

from django.db import models
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext as _
from furl import furl
from kubernetes.client.rest import ApiException

from bkmonitor.models import BCSBase, BCSCluster
from core.drf_resource import api


class BCSMonitor(BCSBase):
    class Meta:
        abstract = True

    # Prometheus Operator CRD 版本
    GROUP: str = "monitoring.coreos.com"
    # 版本信息
    VERSION: str = "v1"

    name = models.CharField(max_length=128)
    namespace = models.CharField(max_length=128)
    endpoints = models.CharField(max_length=32)
    metric_path = models.CharField(max_length=128)
    metric_port = models.CharField(max_length=32)
    metric_interval = models.CharField(max_length=8)

    @classmethod
    @abc.abstractmethod
    def fetch_k8s_monitor_list_by_cluster(cls, params: dict[str, tuple[str, int]]) -> list[dict]:
        """获取指定集群的k8s监控列表"""
        raise NotImplementedError

    @classmethod
    def hash_unique_key(cls, bk_biz_id, bcs_cluster_id, namespace, name, metric_path, metric_port, metric_interval):
        return cls.md5str(
            ",".join(
                [
                    str(bk_biz_id),
                    bcs_cluster_id,
                    namespace,
                    name,
                    metric_path,
                    metric_port,
                    metric_interval,
                ]
            )
        )

    def get_unique_hash(self):
        return self.hash_unique_key(
            self.bk_biz_id,
            self.bcs_cluster_id,
            self.namespace,
            self.name,
            self.metric_path,
            self.metric_port,
            self.metric_interval,
        )

    def save(self, *args, **kwargs):
        self.unique_hash = self.get_unique_hash()
        super().save(*args, **kwargs)

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
                    "id": "metric_path",
                    "name": _("Metric路径"),
                    "type": "string",
                    "disabled": False,
                    "checked": True,
                },
                {
                    "id": "metric_port",
                    "name": _("端口"),
                    "type": "string",
                    "disabled": False,
                    "checked": True,
                },
                {
                    "id": "metric_interval",
                    "name": _("周期(s)"),
                    "type": "string",
                    "disabled": False,
                    "checked": True,
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

    @classmethod
    def load_list_from_api(cls, params: dict[str, tuple[str, int]]) -> list["BCSMonitor"]:
        """
        从API获取Monitor列表

        Args:
            params: key为集群ID，value为(租户ID, 业务ID)
        Returns:
            list[BCSMonitor]: 监控列表
        """
        api_resources = cls.fetch_k8s_monitor_list_by_cluster(params)

        monitors = []
        for r in itertools.chain.from_iterable(item for item in api_resources if item):
            bcs_cluster_id = r.get("bcs_cluster_id")
            bk_biz_id = params[bcs_cluster_id][1]
            metric_path_list = list(set(r.get("metric_path")))
            metric_port_list = r.get("metric_port")
            metric_interval_list = r.get("metric_interval")
            for i, metric_path in enumerate(metric_path_list):
                bcs_monitor = cls()
                bcs_monitor.bk_biz_id = bk_biz_id
                bcs_monitor.bcs_cluster_id = bcs_cluster_id
                bcs_monitor.namespace = r.get("namespace")
                bcs_monitor.name = r.get("name")
                bcs_monitor.metric_path = metric_path
                bcs_monitor.metric_port = metric_port_list[i]
                bcs_monitor.metric_interval = metric_interval_list[i]
                bcs_monitor.created_at = parse_datetime(r.get("created_at"))
                bcs_monitor.last_synced_at = timezone.now()
                bcs_monitor.deleted_at = None

                bcs_monitor.monitor_status = cls.METRICS_STATE_STATE_SUCCESS
                # 唯一键
                bcs_monitor.unique_hash = bcs_monitor.get_unique_hash()

                bcs_monitor.api_labels = r.get("labels", {})
                monitors.append(bcs_monitor)
        return monitors

    def render_bcs_cluster_id(self, bk_biz_id, render_type="list"):
        search = [{"bcs_cluster_id": self.bcs_cluster_id}]
        return self.build_search_link(bk_biz_id, "cluster", self.bcs_cluster_id, search)

    def fetch(self):
        try:
            cluster = BCSCluster.objects.get(bcs_cluster_id=self.bcs_cluster_id)
        except BCSCluster.DoesNotExist:
            raise Exception("cluster do not exist")
        plurals = self.PLURALS
        resource = cluster.custom_objects_api.get_cluster_custom_object(
            group=self.GROUP, version=self.VERSION, plural=plurals, name=self.name
        )
        return resource

    def apply(self, body):
        try:
            cluster = BCSCluster.objects.get(bcs_cluster_id=self.bcs_cluster_id)
        except BCSCluster.DoesNotExist:
            raise Exception("cluster do not exist")
        plurals = self.PLURALS
        try:
            # 如果apiserver存在对应的资源，更新替换，否则创建对应的资源
            resource = cluster.custom_objects_api.get_namespaced_custom_object(
                group=self.GROUP, version=self.VERSION, plural=plurals, namespace=self.namespace, name=self.name
            )
            cluster.custom_objects_api.replace_namespaced_custom_object(
                group=self.GROUP,
                version=self.VERSION,
                plural=plurals,
                namespace=self.namespace,
                name=self.name,
                body=body,
            )
        except ApiException:
            resource = cluster.custom_objects_api.create_namespaced_custom_object(
                group=self.GROUP, version=self.VERSION, plural=plurals, namespace=self.namespace, body=body
            )
        return resource

    @classmethod
    def sync_resource_usage(cls, bk_biz_id: int, bcs_cluster_id: str) -> None:
        """同步数据状态 ."""
        # 更新数据状态
        if not api.kubernetes.has_bkm_metricbeat_endpoint_up({"bk_biz_id": bk_biz_id}):
            return

        # 获得采集器健康状态
        group_by = ["namespace", "bk_monitor_name", "bk_endpoint_url", "endpoint", "code"]
        monitor_type = cls.PLURAL
        metric_value_dict = cls.get_monitor_beat_up_status(bk_biz_id, bcs_cluster_id, monitor_type, group_by)
        code_index = 4
        group_num = len(group_by)
        key_indexes = [0, 1, 2, 3]
        monitor_status_map = cls.convert_up_to_monitor_status(metric_value_dict, group_num, key_indexes, code_index)

        # 获得已存在的采集状态
        history_models = cls.objects.filter(bk_biz_id=bk_biz_id, bcs_cluster_id=bcs_cluster_id)
        old_unique_hash_map = {
            (item.namespace, item.name, item.metric_path, item.metric_port): item.monitor_status
            for item in history_models
        }
        # 获得新的采集状态
        new_unique_hash_map = {
            (
                key[0],
                key[1],
                str(furl(key[2]).path),
                key[3],
            ): monitor_status
            for key, monitor_status in monitor_status_map.items()
        }
        # 更新采集状态
        unique_hash_set_for_update = set(old_unique_hash_map.keys()) & set(new_unique_hash_map.keys())
        for unique_hash in unique_hash_set_for_update:
            monitor_status = new_unique_hash_map[unique_hash]
            if monitor_status == old_unique_hash_map[unique_hash]:
                continue
            namespace = unique_hash[0]
            name = unique_hash[1]
            metric_path = unique_hash[2]
            metric_port = unique_hash[3]
            cls.objects.filter(
                bk_biz_id=bk_biz_id,
                bcs_cluster_id=bcs_cluster_id,
                namespace=namespace,
                name=name,
                metric_path=metric_path,
                metric_port=metric_port,
            ).update(
                **{
                    "monitor_status": monitor_status,
                }
            )
        # 将未采集的记录设置为无数据
        unique_hash_set_for_reset = set(old_unique_hash_map.keys()) - set(new_unique_hash_map.keys())
        if unique_hash_set_for_reset:
            for unique_hash in unique_hash_set_for_reset:
                namespace = unique_hash[0]
                name = unique_hash[1]
                metric_path = unique_hash[2]
                metric_port = unique_hash[3]
                cls.objects.filter(
                    bk_biz_id=bk_biz_id,
                    bcs_cluster_id=bcs_cluster_id,
                    namespace=namespace,
                    name=name,
                    metric_path=metric_path,
                    metric_port=metric_port,
                ).update(
                    **{
                        "monitor_status": cls.METRICS_STATE_DISABLED,
                    }
                )
