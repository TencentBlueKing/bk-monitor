# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import copy
from abc import ABC
from functools import cmp_to_key

from bkmonitor.share.api_auth_resource import ApiAuthResource
from monitor_web.scene_view.table_format import DefaultTableFormat


class PageListResource(ApiAuthResource, ABC):
    def get_columns(self, column_type=None):
        return []

    def get_columns_dict(self, column_type=None):
        res = {}
        for column in self.get_columns(column_type):
            res[column.id] = column

        return res

    def get_details(self, item):
        details = []
        for column in self.get_columns():
            value = item.get(column["id"], "")
            details.append(
                {
                    "key": column["id"],
                    "name": column["name"],
                    "type": column["type"],
                    "value": value,
                }
            )
        return details

    def get_sort_fields(self):
        return []

    def get_filter_fields(self):
        return []

    def sort(self, items, sort_field=None):
        default_sort_fields = self.get_sort_fields()
        # 无默认且无传入排序字段则直接返回
        if not default_sort_fields and not sort_field:
            return items
        # 更新排序字段
        if sort_field:
            if isinstance(sort_field, list):
                default_sort_fields = sort_field
            elif isinstance(sort_field, str):
                default_sort_fields = sort_field.split(",")
            else:
                return items
        # 获取字段map
        column_map = {column.id: column for column in self.get_columns()}

        # 构造基础排序
        def _get_sort_value(item):
            sort_value = []
            for field in default_sort_fields:
                reverse = False
                if field.startswith("-"):
                    reverse = True
                    field = field[1:]
                column = column_map.get(field, DefaultTableFormat())
                sort_value.append(column.get_sort_key(item, reverse))
            return sort_value

        # 排序方法
        def _sort(item_a, item_b):
            item_a_value = _get_sort_value(item_a)
            item_b_value = _get_sort_value(item_b)
            for i in range(min(len(item_a_value), len(item_b_value))):
                value_a = item_a_value[i]
                value_b = item_b_value[i]
                reverse = value_a[1]
                cmp_a = value_a[0]
                cmp_b = value_b[0]

                if isinstance(cmp_a, dict):
                    cmp_a = cmp_a["value"]

                if isinstance(cmp_b, dict):
                    cmp_b = cmp_b["value"]

                if cmp_a > cmp_b:
                    return 1 if not reverse else -1
                if cmp_a < cmp_b:
                    return -1 if not reverse else 1
            return 0

        return sorted(items, key=cmp_to_key(_sort))

    def get_filter_keyword_data(self, data, keyword):
        filter_fields = self.get_filter_fields()
        if not filter_fields or not keyword:
            return data
        result = []
        for item in data:
            for field in filter_fields:
                value = item.get(field, "")
                if value:
                    if isinstance(value, str):
                        if keyword.lower() in value.lower():
                            result.append(item)
                            break
                    else:
                        # 自定义获取值 针对非字符串如dict情况
                        filter_value = self.get_columns_dict()[field].get_filter_value(value)
                        if keyword.lower() in filter_value.lower():
                            result.append(item)
                            break

        return result

    def check_filter(self, row: dict, filter_dict: dict, column_map: dict):
        for filter_field, values in filter_dict.items():
            value = column_map.get(filter_field, DefaultTableFormat()).get_value(row)
            if isinstance(values, bool):
                values = "on" if values else "off"
            if value not in values:
                return False
        return True

    def get_filter_dict_data(self, data: list, filter_dict: dict, column_map: dict):
        if not filter_dict:
            return data
        return [item for item in data if self.check_filter(item, filter_dict, column_map)]

    def get_response_columns(self, data, column_type=None):
        # 获取字段信息
        column_formats = self.get_columns(column_type=column_type)
        filterable_column_map = [column for column in column_formats if column.filterable and not column.filter_list]
        # 遍历数据获取筛选列表
        for item in data:
            for column in filterable_column_map:
                item_val = column.get_filter_key(item)
                if item_val in column.filter_list:
                    continue
                column.filter_list.append(item_val)
        return column_formats

    def handle_pagination(self, params, data):
        page = params.get("page", 1)
        page_size = params.get("page_size", 10)
        offset = (page - 1) * page_size
        return data[offset : offset + page_size]

    def handle_filter(self, params, data, column_format_map):
        # 筛选
        data = self.get_filter_keyword_data(data, params.get("keyword", ""))
        data = self.get_filter_dict_data(data, params.get("filter_dict", {}), column_format_map)
        return data

    def handle_sort(self, params, data, skip_sorted=False):
        if not skip_sorted:
            # 排序
            data = self.sort(data, params.get("sort", None))
        else:
            if data:
                data = [data[0]] + self.sort(data[1:], params.get("sort", None))
        return data

    def handle_format(self, data, column_formats, params):
        # 格式化数据

        extra_params = self.add_extra_params(params)

        for result_data_item in data:
            item = copy.deepcopy(result_data_item)
            item.update(extra_params)
            for column in column_formats:
                try:
                    result_data_item[column.id] = column.format(item)
                except KeyError:
                    # maybe get metric data failed
                    continue

        return data

    def add_extra_params(self, data):
        return {}

    def get_columns_config(self, data, column_type, params=None):
        column_formats = self.get_response_columns(data, column_type)
        if not params:
            column_format_map = {column.id: column for column in column_formats}
        else:
            column_format_map = {column.id: column for column in column_formats if column.display(params)}
            column_formats = [i for i in column_formats if i.id in column_format_map]
        return column_formats, column_format_map

    def get_pagination_data(self, data, params, column_type=None, skip_sorted=False):
        column_formats, column_format_map = self.get_columns_config(data, column_type, params)

        # 筛选
        data = self.handle_filter(params, data, column_format_map)

        # 排序
        data = self.handle_sort(params, data, skip_sorted)

        length = len(data)
        # 分页
        data = self.handle_pagination(params, data)

        # 格式化数据
        data = self.handle_format(data, column_formats, params)

        return {"columns": [column.column() for column in column_formats], "total": length, "data": data}
