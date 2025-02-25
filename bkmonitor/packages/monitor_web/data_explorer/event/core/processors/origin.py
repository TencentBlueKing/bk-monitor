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

from django.utils.translation import gettext_lazy as _

from ...constants import EventDomain, EventSource
from .base import BaseEventProcessor


class OriginEventProcessor(BaseEventProcessor):
    """原始事件数据处理器"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def process(self, origin_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # TODO 根据 source & domain 获取
        # - 第一优先级：dimensions.source & dimensions.domain
        # - 第二优先级：origin_event["_meta"]["data_label"] -> k8s_event、system_event、cicd_event

        domain: str = "K8S"
        source: str = "BCS"
        source_alias: str = _("{domain}/{source}").format(
            domain=EventDomain.from_value(domain).label, source=EventSource.from_value(source).label
        )

        # 目标：
        # - 输出统一事件前端格式，除 source 外其他展示字段的 alias 保持和 value 一致，等待 k8s、cicd、system 等事件处理器处理。
        # - 为了控制样例篇幅 _meta & origin_data 省略部分字段，根据事件数据返回值补充即可。
        return [
            {
                "time": {"value": 1736927543000, "alias": 1736927543000},
                # 如果 dimensions.type 不存在，或者值不为 Normal / Warning，默认填充 Default。
                "type": {"value": "Normal", "alias": "Normal"},
                "source": {"value": "SYSTEM", "alias": source_alias},
                "event_name": {"value": "oom", "alias": "oom"},
                "event.content": {"value": "oom", "alias": "oom", "detail": {}},
                "target": {"value": "127.0.0.1", "alias": "127.0.0.1", "url": ""},
                "_meta": {
                    # 记录 __domain & __source
                    "__domain": domain,
                    "__source": source,
                    "__data_label": "system_event",
                    "__doc_id": "6848190063902810938",
                    "__index": "v2_gse_system_event_20250201_0",
                    "__result_table": "gse_system_event.__default__",
                    "_time_": 1740111073000,
                },
                "origin_data": {
                    "time": 1737281113,
                    "dimensions.ip": "127.0.0.1",
                    "dimensions.bk_biz_id": "11",
                    "dimensions.bk_cloud_id": "0",
                    "event.content": "oom",
                    "event.count": 1,
                    "target": "0:127.0.0.1",
                    "event_name": "OOM",
                },
            },
        ]
