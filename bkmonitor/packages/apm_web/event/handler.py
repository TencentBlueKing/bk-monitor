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

import datetime
from typing import Any, Dict, List, Optional

from bkmonitor.data_source.unify_query.builder import UnifyQuerySet
from bkmonitor.utils.time_tools import time_interval_align
from monitor_web.data_explorer.event.constants import EventDomain, EventSource


class EventQueryHelper:
    TIME_FIELD_ACCURACY = 1

    # 默认查询近 1h 的数据
    DEFAULT_TIME_DURATION: datetime.timedelta = datetime.timedelta(hours=1)

    # 最多查询近 30d 的数据
    MAX_TIME_DURATION: datetime.timedelta = datetime.timedelta(days=180)

    @classmethod
    def time_range_qs(cls, start_time: Optional[int] = None, end_time: Optional[int] = None) -> UnifyQuerySet:
        start_time, end_time = cls._get_time_range(start_time, end_time)
        return UnifyQuerySet().start_time(start_time).end_time(end_time)

    @classmethod
    def _get_time_range(cls, start_time: Optional[int] = None, end_time: Optional[int] = None):
        now: int = int(datetime.datetime.now().timestamp())
        # 最早查询起始时间
        earliest_start_time: int = now - int(cls.MAX_TIME_DURATION.total_seconds())
        # 默认查询起始时间
        default_start_time: int = now - int(cls.DEFAULT_TIME_DURATION.total_seconds())

        # 开始时间不能小于 earliest_start_time
        start_time = max(earliest_start_time, start_time or default_start_time)
        # 结束时间不能大于 now
        end_time = min(now, end_time or now)

        # 省略未完成的一分钟，避免数据不准确引起误解
        interval: int = 60
        start_time = time_interval_align(start_time, interval) * cls.TIME_FIELD_ACCURACY
        end_time = time_interval_align(end_time, interval) * cls.TIME_FIELD_ACCURACY

        return start_time, end_time


class EventHandler:
    def __init__(self, bk_biz_id: int, app_name: str, service_name: str):
        self.bk_biz_id: int = bk_biz_id
        self.app_name: str = app_name
        self.service_name: str = service_name

    def get_config(self) -> List[Dict[str, Any]]:
        return [
            {
                "table": "k8s_event",
                "domain": EventDomain.K8S.value,
                "source": EventSource.BCS.value,
                "relations": [
                    # 集群 / 命名空间 / Workload 类型 / Workload 名称
                    # case 1：勾选整个集群
                    # {"bcs_cluster_id": "BCS-K8S-00000"},
                    # case 2：勾选整个 Namespace
                    {"bcs_cluster_id": "BCS-K8S-00000", "namespace": "blueking"},
                    # case 3：勾选整个 WorkloadType
                    {"bcs_cluster_id": "BCS-K8S-00000", "namespace": "blueking", "kind": "Deployment"},
                    # case 4：勾选 Workload
                    # Deployment 包括 Pod、HorizontalPodAutoscaler、ReplicaSet 事件
                    # DaemonSet / StatefulSet 包括 Pod
                    {
                        "bcs_cluster_id": "BCS-K8S-00000",
                        "namespace": "blueking",
                        "kind": "Deployment",
                        "name": "bk-monitor-api",
                    },
                ],
            },
            {
                "table": "system_event",
                "domain": EventDomain.SYSTEM.value,
                "source": EventSource.HOST.value,
                "relations": [
                    {"bk_biz_id": self.bk_biz_id},
                ],
            },
        ]
