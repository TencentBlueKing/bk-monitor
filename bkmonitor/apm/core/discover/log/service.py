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
from apm.core.handlers.query.builder import QueryConfigBuilder, UnifyQuerySet
from apm.models import TopoNode
from bkmonitor.data_source.utils.query import BaseQuery
from constants.apm import TelemetryDataType
from constants.data_source import DataSourceLabel, DataTypeLabel

logger = logging.getLogger("apm")


class ServiceDiscover(Discover):
    """按 APM 日志索引集折叠查询每个服务的最新日志，维护日志节点与心跳。"""

    # 日志查询使用完整调度窗口，不切分。
    SPLIT_SECONDS: int | None = None
    QUERY_MAX_LIMIT: int = BaseQuery.QUERY_MAX_LIMIT

    def discover(self, start_time: int, end_time: int) -> None:
        """查询两个服务名字段的最新日志，合并后写入节点及心跳。"""
        if not self.datasource.index_set_id:
            return
        observed: dict[str, int] = {}
        for field in ("resource.service.name", "resource.server"):
            query: QueryConfigBuilder = (
                QueryConfigBuilder((DataTypeLabel.LOG, DataSourceLabel.BK_LOG_SEARCH))
                .table(str(self.datasource.index_set_id))
                .index_set_id(self.datasource.index_set_id)
                .time_field("time")
                .distinct(field)
                .order_by("time desc")
            )
            logs: list[dict[str, Any]] = list(
                UnifyQuerySet()
                .scope(self.bk_biz_id)
                .start_time(start_time * 1000)
                .end_time(end_time * 1000)
                .time_align(False)
                .add_query(query)
                .limit(self.QUERY_MAX_LIMIT)
            )
            for log in logs:
                resource: dict[str, Any] = log.get("resource") or {}
                if field == "resource.service.name":
                    # 兼容日志记录中嵌套的 service.name 和保留点号的字段名。
                    name = resource.get("service.name") or (resource.get("service") or {}).get("name")
                else:
                    name = resource.get("server")
                if not name:
                    continue
                timestamp: int = int(log["time"]) // 1000
                observed[name] = max(observed.get(name, 0), timestamp)

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
        )
        logger.info(
            "[LogServiceDiscover] bk_biz_id=%s app_name=%s services=%s", self.bk_biz_id, self.app_name, len(observed)
        )
