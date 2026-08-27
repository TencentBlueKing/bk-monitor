"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import TYPE_CHECKING, Self, cast

from bkmonitor.data_source.utils.apm import TraceDatasourceTarget
from bkmonitor.data_source.utils.query import BaseQuery as DataSourceBaseQuery

if TYPE_CHECKING:
    from apm_web.models import Application


class BaseQuery(DataSourceBaseQuery):
    """APM SaaS 查询基类。"""

    def __init__(self, data_sources: list[TraceDatasourceTarget]) -> None:
        self.data_sources: list[TraceDatasourceTarget] = data_sources

    @classmethod
    def from_application(cls, application: "Application") -> Self:
        """根据 APM 应用构造携带数据保留期的查询对象。"""

        return cls(
            [
                TraceDatasourceTarget.build(
                    bk_biz_id=cast(int, application.bk_biz_id),
                    app_name=cast(str, application.app_name),
                    table_id=cast(str, application.trace_result_table_id),
                    retention=cast(int, application.es_retention),
                )
            ]
        )
