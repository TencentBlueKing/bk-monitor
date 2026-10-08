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

import arrow
from arrow.parser import ParserError

from apm.core.discover.log.base import Discover
from apm.core.handlers.query.builder import QueryConfigBuilder, UnifyQuerySet
from apm.models import TopoNode
from bkmonitor.data_source.utils.query import BaseQuery
from bkmonitor.data_source.exceptions import IncompleteQueryResultError
from constants.apm import TelemetryDataType
from constants.data_source import DataSourceLabel, DataTypeLabel

logger = logging.getLogger("apm")


class ServiceDiscover(Discover):
    """按 APM 日志索引集折叠查询每个服务的最新日志，维护日志节点与心跳。"""

    QUERY_MAX_LIMIT = BaseQuery.QUERY_MAX_LIMIT

    def discover(self, start_time: int, end_time: int) -> None:
        """分别查询两个服务名字段，全部查询及时间校验成功后再写入。

        查询窗口以秒传入，QueryBuilder 使用毫秒；索引集未配置时跳过。
        任一查询达到条数上限时，仅检查已观测节点；查询不完整或时间异常时保留旧心跳。
        """
        if not self.datasource.index_set_id:
            return
        observed: dict[str, int] = {}
        complete: bool = True
        for field in ("resource.service.name", "resource.server"):
            query = (
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
            complete = complete and len(logs) < self.QUERY_MAX_LIMIT
            for log in logs:
                resource = log.get("resource") or {}
                if field == "resource.service.name":
                    # 兼容日志记录中嵌套的 service.name 和保留点号的字段名。
                    name = resource.get("service.name") or (resource.get("service") or {}).get("name")
                else:
                    name = resource.get("server")
                if not name:
                    continue
                raw_time = log.get("time")
                try:
                    if raw_time is None:
                        raise ValueError("missing log time")
                    # ES date 的原始值允许毫秒数值、数字字符串或带时区的日期字符串。
                    if isinstance(raw_time, int | float) or (isinstance(raw_time, str) and raw_time.isdigit()):
                        timestamp = float(raw_time) / 1000
                    else:
                        timestamp = arrow.get(raw_time).float_timestamp
                except (ValueError, TypeError, OverflowError, ParserError) as error:
                    raise IncompleteQueryResultError("invalid log time in collapsed query result") from error
                if not start_time <= timestamp <= end_time:
                    raise IncompleteQueryResultError("log time is outside the requested discovery window")
                observed[name] = max(observed.get(name, 0), int(timestamp))

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
            check_all_services=complete,
        )
        logger.info(
            "[LogServiceDiscover] bk_biz_id=%s app_name=%s services=%s", self.bk_biz_id, self.app_name, len(observed)
        )
