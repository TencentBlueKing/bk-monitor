"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RUMAppTarget:
    """RUM 应用维度目标，承载业务 ID 与应用名称"""

    bk_biz_id: int
    app_name: str


@dataclass(frozen=True)
class RUMDatasourceTarget:
    """Trace 数据源查询目标，表示一条`table_id -> APM 应用`的绑定关系"""

    table_id: str
    app: RUMAppTarget

    @classmethod
    def build(cls, bk_biz_id: int, app_name: str, table_id: str) -> "RUMDatasourceTarget":
        return cls(table_id=table_id, app=RUMAppTarget(bk_biz_id=bk_biz_id, app_name=app_name))
