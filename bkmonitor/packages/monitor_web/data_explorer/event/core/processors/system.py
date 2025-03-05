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

            # 1-OOM
            oom = {
                "value": "oom",
                "alias": "主机（0-127.0.0.1）进程（chrome）OOM",
                "detail": {
                    "process": {"label": "进程", "value": "chrome"},
                    "task_memcg": {
                        "label": "进程所属内存 cgroup",
                        "value": "/pods.slice/pods-burstable.slice/pods-burstable-pod1",
                    },
                },
            }
            # # 2-DiskFull
            # disk_full = {
            #     "value": "disk_full",
            #     "alias": "主机（0-127.0.0.1）磁盘（/）已满",
            #     "detail": {
            #         "fstype": {"label": "文件系统类型", "value": "ext4"},
            #         "file_system": {"label": "文件系统", "value": "/dev/vda1"},
            #     },
            # }
            # # 3-DiskReadOnly
            # disk_read_only = {
            #     "value": "disk_read_only",
            #     "alias": "主机（0-127.0.0.1）磁盘（{fs}）只读，原因：{type}",
            #     "detail": {
            #         "fs": {"label": "文件系统", "value": "ext4"},
            #         "position": {"label": "磁盘位置", "value": "1111"},
            #         "type": {"label": "只读原因", "value": "xxxxx"},
            #     },
            # }
            # # 4-CoreFile
            # core_file = {
            #     "value": "process MsgServer create corefile at /data/corefile/core.1_MsgServer",
            #     # 参考：alarm_backends/service/access/event/records/corefile.py，1/2/3 表示不同 case，正式写代码都用 alias
            #     # case-1：executable & signal 不为空。
            #     "alias": "主机（0-127.0.0.1）进程（MsgServer）因异常信号（{signal}）产生 corefile（/data/corefile/core.1_MsgServer）",
            #     # case-2：executable 不为空。
            #     "alias1": "主机（0-127.0.0.1）进程（MsgServer）产生 corefile（/data/corefile/core.1_MsgServer）",
            #     # case-3：signal 不为空。
            #     "alias2": "主机（0-127.0.0.1）因异常信号（{signal}）产生 corefile（/data/corefile/core.1_MsgServer）",
            #     # case-4：executable & signal 为空。
            #     "alias3": "主机（0-127.0.0.1）产生 corefile（/data/corefile/core.1_MsgServer）",
            #     "detail": {
            #         "corefile": {"label": "CoreDump 文件", "value": "/data/corefile/core.1_MsgServer"},
            #         "executable": {"label": "可执行文件", "value": "MsgServer"},
            #     },
            # }
            # # 5-AgentLost
            # agent_lost = {
            #     "value": "AgentLost",
            #     "alias": "主机（0-127.0.0.1）Agent 失联",
            #     "detail": {"bk_agent_id": {"label": "AgentID", "value": "02000000005254001dc07917062465625198"}},
            # }
            processed_events.append(
                {
                    # alias - 展示值、value - 原始数据值。
                    "time": {"value": 1736927543000, "alias": 1736927543000},
                    "type": {"value": "Normal", "alias": "Normal"},
                    "source": {"value": "SYSTEM", "alias": "系统/主机"},
                    "event_name": {"value": "oom", "alias": "进程 OOM"},
                    "event.content": oom,
                    "target": {
                        "value": "127.0.0.1",
                        "alias": "直连区域[0] / 127.0.0.1",
                        "scenario": "主机监控",
                        "url": "https://bk.monitor.com/host/?bk_cloud_id=&bk_cloud_ip=127.0.0.1",
                    },
                    "origin_data": {},
                }
            )
        return processed_events
