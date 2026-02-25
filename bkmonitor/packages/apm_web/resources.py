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
from datetime import datetime

from django.utils.translation import gettext_lazy as _

from apm_web.icon import get_icon

# 导出 profiling 接口给 grafana 仪表盘使用
from apm_web.profile.resources import (  # noqa
    GrafanaQueryProfileLabelResource,
    GrafanaQueryProfileLabelValuesResource,
    GrafanaQueryProfileResource,
    ListApplicationServicesResource,
    QueryServicesDetailResource,
)

# 导出 trace 接口给告警中心使用
from apm_web.trace.resources import ListFlattenSpanResource, ListFlattenTraceResource  # noqa
from bkmonitor.share.api_auth_resource import ApiAuthResource
from monitor_web.scene_view.resources.base import PageListResource
from monitor_web.scene_view.table_format import EndpointListTableFormat, OverviewDataTableFormat


class SidebarPageListResource(PageListResource):
    """
    need_overview: 是否需要概览行
    对于前端左侧边栏需要计算概览的场景适用

    need_dynamic_sort_column: 是否需要动态调整列位置
    对于左侧边栏如果选择了排序列->那么此列需要处于columns的的第二位并且宽度固定(160)
    """

    need_overview = False

    need_dynamic_sort_column = False

    dynamic_sort_column_width = 120

    # 是否需要在返回数据中加入时间范围(用户url的时间范围渲染)
    return_time_range = False
    # 请求数据中的时间字段 只有在return_time_range为True时生效
    timestamp_fields = []

    def get_status_filter(self):
        return []

    def get_pagination_data(self, origin_data, params, column_type=None, skip_sorted=False, **kwargs):
        res = {}
        if not kwargs.get("in_place", False):
            data = copy.deepcopy(origin_data)
        else:
            data = origin_data

        column_formats, column_format_map = self.get_columns_config(data, column_type)
        # 筛选
        data = self.handle_filter(params, data, column_format_map)

        # 计算概览
        if self.need_overview:
            # 调用概览计算函数 -> 使用全量数据计算
            overview_data = self.calc_overview(column_formats, data)
            res["overview_data"] = overview_data

        # 排序
        if params.get("filter_fields"):
            # 跳过排序 保证匹配到的数据位于第一行
            data = self.handle_sort(params, data, skip_sorted=True)
        else:
            data = self.handle_sort(params, data)

        length = len(data)
        # 分页
        data = self.handle_pagination(params, data)

        # 格式化数据
        data = self.handle_format(data, column_formats, params)
        res["total"] = length
        res["data"] = data
        res["columns"] = [column.column() for column in column_formats]

        if self.get_sort_fields():
            res["sort"] = self.list_columns(self.get_sort_fields(), column_type)

        if self.need_dynamic_sort_column:
            # 动态调整排序列
            res["columns"] = self.change_sort_column(
                params.get("sort"), column_formats, res.get("data"), res.get("overview_data")
            )

        if self.get_status_filter():
            res["filter"] = self.get_status_filter()

        self.add_field_to_res(column_formats, res["data"], res.get("overview_data"))

        return res

    def add_extra_params(self, params):
        if self.return_time_range and all(params.get(i) for i in self.timestamp_fields):
            res = {}
            for i in self.timestamp_fields:
                res[i] = datetime.fromtimestamp(params[i]).strftime("%Y-%m-%d+%H:%M:%S")

            return res

        return {}

    def add_field_to_res(self, columns, data, overview_data=None):
        """为结果数据添加 name 字段。

        从概览列中提取 name 字段值，用于前端展示。

        :param columns: 列格式列表
        :param data: 数据列表
        :param overview_data: 概览数据
        """
        overview_column = next(
            (c for c in columns if isinstance(c, OverviewDataTableFormat | EndpointListTableFormat)), None
        )
        if not overview_column:
            return

        def _get_name(value: list | dict | None) -> str:
            if isinstance(value, list) and value:
                return value[0].get("value", "")
            if isinstance(value, dict):
                return value.get("value", "")
            return ""

        for item in data:
            item["name"] = _get_name(item.get(overview_column.id))

        if overview_data:
            overview_data["name"] = _get_name(overview_data.get(overview_column.id))

    def change_sort_column(self, current_sort, columns, data, overview_data):
        format_columns = [c.column() for c in columns]

        if not current_sort:
            return format_columns

        sort_column = next((c for c in columns if c.column()["id"] == current_sort.lstrip("-")), None)

        if not sort_column:
            return format_columns

        format_sort_column = sort_column.column()
        sort_column_index = format_columns.index(format_sort_column)
        front = format_columns[:sort_column_index]
        back = format_columns[sort_column_index:]

        need_clear_progress_columns = []
        for c in columns:
            if c.column_type == "progress" and getattr(c, "clear_if_not_sorted", False) and c.id != sort_column.id:
                need_clear_progress_columns.append(c)

        for i in data:
            # 对于非排序列的进度条类型列 需要将百分比设置成0
            for column in need_clear_progress_columns:
                if i.get(column.id):
                    i[column.id]["value"] = 0

        for i in need_clear_progress_columns:
            if overview_data.get(i.id):
                overview_data[i.id]["value"] = 0

        # 排序列固定宽度
        format_sort_column["width"] = self.dynamic_sort_column_width
        return [front[0]] + [format_sort_column] + front[1:] + back[1:]

    def calc_overview(self, column_formats, data):
        """计算概览数据。

        :param column_formats: 列格式列表
        :param data: 原始数据列表
        :return: 概览数据字典
        """
        empty_row = {c.id: None for c in column_formats}
        res = {}

        for column in column_formats:
            if isinstance(column, OverviewDataTableFormat):
                # OverviewDataTableFormat 列返回固定结构
                res[column.id] = {
                    "icon": get_icon("overview"),
                    "target": "null_event",
                    "url": "",
                    "key": "",
                    "value": column.title,
                }
            elif isinstance(column, EndpointListTableFormat):
                # EndpointListTableFormat 列返回列表格式
                res[column.id] = [
                    {"icon": get_icon("overview"), "target": "null_event", "url": "", "key": "", "value": column.title}
                ]
            elif column.overview_calculate_handler:
                empty_row.pop(column.id)
                value = column.overview_calculate_handler(data)
                res[column.id] = column.format({column.id: value, **empty_row})
            elif column.overview_calculator:
                all_values = [
                    i.get(column.id).get("label") if isinstance(i.get(column.id), dict) else i.get(column.id)
                    for i in data
                    if i.get(column.id)
                ]
                empty_row.pop(column.id)
                calc_value = column.overview_calculator(all_values) if all_values else None
                res[column.id] = column.format({column.id: calc_value, **empty_row})
            else:
                res[column.id] = None

        return res

    def list_columns(self, source, column_type=None):
        res = []
        for i in source:
            res.append({"id": i, "name": self.get_column_by_name(i, column_type)})
        return res

    def get_column_by_name(self, name, column_type=None):
        for i in self.get_columns(column_type=column_type):
            if i.id == name:
                return i.name

        return None


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


class ServiceAndComponentCompatibleResource(SidebarPageListResource):
    def get_pagination_data(self, origin_data, params, column_type=None):
        """
        特殊处理图表配置field参数(侧边栏图表配置selector_panel.target.fields会同步调整)
        """
        # 补充 service_name 防止点击侧边栏跳转失败
        for i in origin_data:
            i.update(
                {
                    "service_name": i["service"],
                }
            )
        return super().get_pagination_data(origin_data, params, column_type, in_place=True)
