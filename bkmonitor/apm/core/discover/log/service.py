"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import time
from typing import Any

from apm.core.discover.log.base import Discover
from apm.core.discover.exceptions import IncompleteDiscoveryError
from apm.models import TopoNode
from constants.apm import TelemetryDataType
from core.drf_resource import api

logger = logging.getLogger("apm")


class ServiceDiscover(Discover):
    """从应用日志表发现服务及最新日志时间，不查询关联索引。"""

    SERVICE_MAX_SIZE = 1000

    def discover(self, start_time: int, end_time: int) -> None:
        observed: dict[str, int] = {}
        table_id: str = self.result_table_id.replace("-", "_").replace(".", "_")
        for field in ("resource.service.name", "resource.server"):
            after_key: dict[str, str] | None = None
            while True:
                composite: dict[str, Any] = {
                    "size": self.SERVICE_MAX_SIZE,
                    "sources": [{"service_name": {"terms": {"field": field}}}],
                }
                if after_key is not None:
                    composite["after"] = after_key
                response: dict[str, Any] = api.log_search.es_query_dsl(
                    indices=f"{table_id}*",
                    body={
                        "size": 0,
                        "query": {"range": {"time": {"format": "epoch_second", "gte": start_time, "lte": end_time}}},
                        "aggs": {
                            "service_names": {
                                "composite": composite,
                                "aggs": {"last_data_at": {"max": {"field": "time"}}},
                            }
                        },
                    },
                )
                if response.get("timed_out") or response.get("_shards", {}).get("failed", 0):
                    raise IncompleteDiscoveryError("incomplete log discovery result")
                aggregation: dict[str, Any] = response["aggregations"]["service_names"]
                for bucket in aggregation["buckets"]:
                    name: str = bucket["key"]["service_name"]
                    timestamp: float | None = bucket["last_data_at"]["value"]
                    if name and timestamp is not None:
                        # ES date 字段的 max 聚合值为毫秒。
                        observed[name] = max(observed.get(name, 0), int(timestamp) // 1000)
                next_key: dict[str, str] | None = aggregation.get("after_key")
                if not aggregation["buckets"] or not next_key:
                    break
                if next_key == after_key:
                    raise IncompleteDiscoveryError("log discovery pagination did not advance")
                after_key = next_key

        TopoNode.upsert_telemetry_nodes(
            self.bk_biz_id,
            self.app_name,
            TelemetryDataType.LOG.value,
            set(observed),
            TopoNode.get_empty_extra_data(),
        )
        TopoNode.touch_heartbeat(
            self.bk_biz_id,
            self.app_name,
            TelemetryDataType.LOG.value,
            observed,
            int(time.time()),
            check_all_services=True,
        )
        logger.info(
            "[LogServiceDiscover] bk_biz_id=%s app_name=%s services=%s", self.bk_biz_id, self.app_name, len(observed)
        )
