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
import operator
from abc import ABC
from datetime import datetime

from django.utils.translation import ugettext_lazy as _

from apm_web.icon import get_icon
from apm_web.utils import group_by
from bkmonitor.share.api_auth_resource import ApiAuthResource
from core.drf_resource import api
from monitor_web.scene_view.resources.base import PageListResource
from monitor_web.scene_view.table_format import OverviewDataTableFormat


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

    def get_pagination_data(self, origin_data, params, column_type=None, skip_sorted=False):
        res = {}
        data = copy.deepcopy(origin_data)

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
        """
        针对overview_data做处理

        要求
        1. data和overview_data里每条数据需要有name字段，值为概览列的值
        2. overview_data里面 key需要为switch_to_overview
        """
        overview_column = None

        for column in columns:
            if isinstance(column, OverviewDataTableFormat):
                overview_column = column

        if overview_column:
            for i in data:
                i["name"] = i.get(overview_column.id).get("value")

            if overview_data:
                overview_data["name"] = overview_data.get(overview_column.id).get("value")

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
        """
        计算概览数据
        """
        d = {}
        for c in column_formats:
            d[c.id] = None

        res = {}

        for column in column_formats:
            if isinstance(column, OverviewDataTableFormat):
                # 如果为overview列 概览数据中需要保持固定结构返回
                res[column.id] = {
                    "icon": get_icon("overview"),
                    "target": "null_event",
                    "url": "",
                    "key": "",
                    "value": column.title,
                }
            else:
                if column.overview_calculate_handler:
                    d.pop(column.id)
                    v = column.overview_calculate_handler(data)
                    if v is None:
                        res[column.id] = column.format({column.id: None, **d})
                    else:
                        res[column.id] = column.format({column.id: v, **d})
                else:
                    if column.overview_calculator:
                        all_values = [
                            i.get(column.id).get("label") if isinstance(i.get(column.id), dict) else i.get(column.id)
                            for i in data
                            if i.get(column.id)
                        ]
                        d.pop(column.id)
                        if all_values:
                            res[column.id] = column.format({column.id: column.overview_calculator(all_values), **d})
                        else:
                            res[column.id] = column.format({column.id: None, **d})
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

    def get_async_column_item(self, data, column):
        if column in data:
            return {column: data[column]}

        return {}

    def get_async_data(self, data, column, column_type=None):
        async_column = next((i for i in self.SyncResource.get_columns(column_type) if i.id == column), None)
        if not async_column:
            raise ValueError(_("不存在的列: {}").format(column))
        if not async_column.asyncable:
            raise ValueError(_("列: {} 不是异步列").format(column))

        res = []
        for item in data:
            c_item = copy.deepcopy(item)
            try:
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
        特殊处理侧边栏逻辑
        侧边栏在以下场景会存在：
        1. 应用接口/错误页面
            不需要添加额外参数
        2. 服务接口/错误页面
            需要添加service_(kind/category/predicate_value)额外参数 用于前端点击侧边栏某项后保持url参数不变
        3. 组件接口/错误页面
            需要添加component_(kind/category/predicate_value)和service_(kind/category/predicate_value)额外参数
        """

        if params.get("kind") == "component" or params.get("service_params", {}).get("kind") == "component":
            add_data = {}
            # 组件接口/错误页面
            if params.get("service_params"):
                component_extra_data = {
                    "category": params["service_params"].get("category"),
                    "kind": params["service_params"].get("kind"),
                    "predicate_value": params["service_params"].get("predicate_value"),
                }

            else:
                component_extra_data = {
                    "category": params.get("category"),
                    "kind": params.get("kind"),
                    "predicate_value": params.get("predicate_value"),
                }

            if params.get("service_name"):
                component_extra_data["service_name"] = params["service_name"]

            for key, value in component_extra_data.items():
                add_data[f"component_{key}"] = value

            for i in origin_data:
                i.update(add_data)
                i.update({"_is_service": False})

            topo_key = params["service_name"].rsplit("-", 1)[0]
            nodes = api.apm_api.query_topo_node(
                bk_biz_id=params["bk_biz_id"], app_name=params["app_name"], topo_key=topo_key
            )

        elif params.get("service_name"):
            # 服务接口/错误页面
            nodes = api.apm_api.query_topo_node(
                bk_biz_id=params["bk_biz_id"], app_name=params["app_name"], topo_key=params["service_name"]
            )
        else:
            # 应用接口 / 错误页面
            nodes = api.apm_api.query_topo_node(bk_biz_id=params["bk_biz_id"], app_name=params["app_name"])
        service_name_mapping = group_by(nodes, operator.itemgetter("topo_key"))

        for i in origin_data:
            service_info = service_name_mapping.get(i["service"])
            if service_info:
                i.update(
                    {
                        "service_category": service_info[0].get("extra_data", {}).get("category"),
                        "service_kind": service_info[0].get("extra_data", {}).get("kind"),
                        "service_predicate_value": service_info[0].get("extra_data", {}).get("predicate_value"),
                        "service_name": i["service"],
                    }
                )

        return super(ServiceAndComponentCompatibleResource, self).get_pagination_data(origin_data, params, column_type)
