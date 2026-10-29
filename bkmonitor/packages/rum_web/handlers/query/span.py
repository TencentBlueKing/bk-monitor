"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

from bkmonitor.data_source.utils.apm import FilterOperator


from rum_web.handlers.query.base import BaseRumQuery


class SpanQuery(BaseRumQuery):
    def query_detail(self, record_id: str) -> dict[str, Any]:
        """通过 span_id 查询单条 Span 记录。

        :param record_id: Span ID
        :return: 单条记录字典，未找到时返回空字典 ``{}``（保持返回类型稳定，避免调用方额外 ``or {}``）。
        """
        records = self.query_list(
            start_time=None,
            end_time=None,
            offset=0,
            limit=1,
            filters=[{"key": "span_id", "value": [record_id], "operator": FilterOperator.EQUAL}],
        )
        return records[0] if records else {}
