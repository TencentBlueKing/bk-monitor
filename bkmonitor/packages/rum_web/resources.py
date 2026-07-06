"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
from abc import ABC

from django.utils.translation import gettext_lazy as _

from bkmonitor.share.api_auth_resource import ApiAuthResource


class AsyncColumnsListResource(ApiAuthResource, ABC):
    """
    分页异步接口
    适用于某些表格需要其中某列进行单独请求接口获取数据的情况
    """

    SyncResource = None

    @classmethod
    def get_async_column_item(cls, data, column, **kwargs):
        multi_sub_columns = kwargs.get("multi_sub_columns", None)
        default_value = kwargs.get("default_value", None)
        items = {}
        if column in data or default_value:
            column_data = data.get(column, default_value)
            if multi_sub_columns and isinstance(column_data, dict):
                for sub_column in multi_sub_columns:
                    if sub_column in column_data or default_value:
                        items[f"{sub_column}_{column}"] = column_data.get(sub_column, default_value)
            else:
                items[column] = column_data
        return items

    def get_async_data(self, data, column, column_type=None, **kwargs):
        multi_output_columns = kwargs.get("multi_output_columns")
        columns = multi_output_columns or [column]

        columns_mapping = {i.id: i for i in self.SyncResource.get_columns(column_type)}
        for async_column_name in columns:
            if async_column_name not in columns_mapping:
                raise ValueError(_("不存在的列: {}").format(async_column_name))
            if not columns_mapping[async_column_name].asyncable:
                raise ValueError(_("列: {} 不是异步列").format(async_column_name))

        res = []
        for item in data:
            c_item = copy.deepcopy(item)
            try:
                for async_column_name in columns:
                    async_column = columns_mapping[async_column_name]
                    if async_column.id in c_item:
                        c_item[async_column.id] = async_column.format(c_item)

                res.append(c_item)
            except KeyError:
                continue

        return res
