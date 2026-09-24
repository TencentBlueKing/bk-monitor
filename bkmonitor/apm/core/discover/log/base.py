"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from apm.models import LogDataSource


class Discover:
    def __init__(self, datasource: LogDataSource) -> None:
        self.datasource = datasource
        self.bk_biz_id: int = datasource.bk_biz_id
        self.app_name: str = datasource.app_name
        self.result_table_id: str = datasource.result_table_id
