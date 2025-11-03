"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.functional import cached_property
from functools import lru_cache

from core.drf_resource import resource
from core.statistics.metric import Metric, register
from monitor_web.models.uptime_check import (
    UptimeCheckGroup,
    UptimeCheckNode,
    UptimeCheckTask,
)
from monitor_web.statistics.v2.base import BaseCollector


class UptimeCheckCollector(BaseCollector):
    """
    服务拨测
    """

    @cached_property
    def uptimecheck_nodes(self):
        return UptimeCheckNode.objects.filter(bk_biz_id__in=self.biz_info.keys())

    @lru_cache(maxsize=100)
    def all_node_status(self, bk_tenant_id: int):
        return resource.uptime_check.uptime_check_beat(bk_tenant_id=bk_tenant_id)

    @register(labelnames=("bk_biz_id", "bk_biz_name", "protocol", "status"))
    def uptimecheck_task_count(self, metric: Metric):
        """
        拨测任务数
        """
        tasks = UptimeCheckTask.objects.filter(bk_biz_id__in=list(self.biz_info.keys()))
        for task in tasks:
            metric.labels(
                bk_biz_id=task.bk_biz_id,
                bk_biz_name=self.get_biz_name(task.bk_biz_id),
                protocol=task.protocol,
                status=task.status,
            ).inc()

    @register(labelnames=("bk_biz_id", "bk_biz_name", "is_public", "node_id", "node_name"))
    def uptimecheck_node_task_count(self, metric: Metric):
        """
        节点的拨测任务数
        """
        for node in self.uptimecheck_nodes:
            metric.labels(
                bk_biz_id=node.bk_biz_id,
                bk_biz_name=self.get_biz_name(node.bk_biz_id),
                is_public=1 if node.is_common else 0,
                node_id=node.id,
                node_name=node.name,
            ).inc(node.tasks.all().count())

    @register(labelnames=("bk_biz_id", "bk_biz_name", "is_public", "status"))
    def uptimecheck_node_count(self, metric: Metric):
        """
        拨测节点数
        """
        status_mapping = {"0": "RUNNING", "-1": "DOWN", "2": "NEED_UPGRADE"}
        for node in self.uptimecheck_nodes:
            filtered_node_status = list(
                filter(
                    lambda x: (x.get("bk_host_id") == node.bk_host_id)
                    or (x.get("ip") == node.ip and x.get("bk_cloud_id") == node.plat_id),
                    self.all_node_status(node.bk_tenant_id),
                )
            )
            if not filtered_node_status:
                continue
            node_status = filtered_node_status[0]
            metric.labels(
                bk_biz_id=node.bk_biz_id,
                bk_biz_name=self.get_biz_name(node.bk_biz_id),
                is_public=1 if node.is_common else 0,
                status=status_mapping[node_status["status"]],
            ).inc()

    @register(labelnames=("bk_biz_id", "bk_biz_name"))
    def uptimecheck_task_group_count(self, metric: Metric):
        """
        拨测任务组数
        """
        groups = UptimeCheckGroup.objects.filter(bk_biz_id__in=self.biz_info.keys())
        for group in groups:
            metric.labels(bk_biz_id=group.bk_biz_id, bk_biz_name=self.get_biz_name(group.bk_biz_id)).inc()
