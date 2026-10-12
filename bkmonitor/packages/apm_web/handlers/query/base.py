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
from typing import Any

from bkmonitor.data_source.utils.apm import TraceDatasourceTarget
from bkmonitor.data_source.utils import types
from bkmonitor.data_source.utils.query import BaseQuery as DataSourceBaseQuery

logger = logging.getLogger("apm")


class BaseQuery(DataSourceBaseQuery):
    """APM SaaS 查询基类。"""

    def __init__(self, data_sources: list[TraceDatasourceTarget]) -> None:
        self.data_sources: list[TraceDatasourceTarget] = data_sources

    def _query_fields(
        self,
        targets: list[tuple[types.TableId, types.SpaceUid]],
        start_time: int | None,
        end_time: int | None,
    ) -> dict[str, dict[str, Any]]:
        """查询字段元数据，并在空结果时记录当前数据源。"""

        fields_info = super()._query_fields(targets, start_time, end_time)
        if not fields_info:
            logger.warning("[BaseQuery] query fields returned empty: data_sources=%s", self.data_sources)
        return fields_info
