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
from typing import Any, Dict, List

from .base import BaseEventProcessor


class HostEventProcessor(BaseEventProcessor):
    @classmethod
    def _need_process(cls, origin_event: Dict[str, Any]) -> bool:
        return (origin_event["_meta"]["__domain"], origin_event["_meta"]["__source"]) == ("system", "host")

    def process(self, origin_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        processed_events: List[Dict[str, Any]] = []
        for origin_event in origin_events:
            if not self._need_process(origin_event):
                processed_events.append(origin_event)
                continue

            # TODO 补充模板：alarm_backends/service/access/event/records/oom.py
            processed_events.append(
                {
                    # alias - 展示值、value - 原始数据值。
                    "time": {"value": 1736927543000, "alias": 1736927543000},
                    "type": {"value": "Normal", "alias": "Normal"},
                    "source": {"value": "SYSTEM", "alias": "系统/主机"},
                    "event_name": {"value": "oom", "alias": "进程 OOM"},
                    "event.content": {
                        "value": "oom",
                        "alias": "发现主机（0-127.0.0.1）存在进程（chrome）OOM 异常事件",
                        "detail": {
                            "target": {
                                "label": "主机",
                                "value": "127.0.0.1",
                                "alias": "直连区域[0] / 127.0.0.1",
                                # 展示成链接
                                "type": "link",
                                "url": "https://bk.monitor.com/host/?bk_cloud_id=&bk_cloud_ip=127.0.0.1",
                            },
                            "process": {"label": "进程", "value": "chrome"},
                            "task_memcg": {
                                "label": "进程所属内存 cgroup",
                                "value": "/pods.slice/pods-burstable.slice/pods-burstable-pod1",
                            },
                        },
                    },
                    "target": {
                        "value": "127.0.0.1",
                        "alias": "直连区域[0] / 127.0.0.1",
                        "url": "https://bk.monitor.com/host/?bk_cloud_id=&bk_cloud_ip=127.0.0.1",
                    },
                    "origin_data": {},
                }
            )
        return processed_events
