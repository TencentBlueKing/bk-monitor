"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import datetime
from abc import ABC

import arrow
from arrow.parser import ParserError
from django.utils.translation import gettext_lazy as _lazy

from apm_web.constants import DataStatusColumnEnum
from core.unit import load_unit


class DefaultTableFormat(ABC):
    value_map = {True: "on", False: "off"}

    def get_map_value(self, value):
        return self.value_map.get(value, value)

    def get_filter_key(self, row):
        """获取筛选的键"""
        return {"text": "", "value": ""}

    def get_sort_key(self, row, reverse=False):
        """获取排序的键"""
        return "", reverse

    def get_value(self, row):
        """获取值"""
        return ""


class TableFormat(DefaultTableFormat):
    column_type = None

    def __init__(
        self,
        id: str,
        name: str,
        sortable: bool = False,
        disabled: bool = False,
        checked: bool = True,
        width: int = None,
        min_width: int = None,
        tips_format: str = "",
        filterable: bool = False,
        filter_list: list = None,
        action_id: str = None,
        overview_calculator=None,
        overview_calculate_handler=None,
        asyncable: bool = False,
        props: dict = None,
        display_handler=None,
    ):
        self.id = id
        self.name = name
        self.sortable = sortable
        self.disabled = disabled
        self.checked = checked
        self.width = width
        self.min_width = min_width
        self.tips_format = tips_format
        self.filterable = filterable
        self.filter_list = filter_list if isinstance(filter_list, list) else []
        self.action_id = action_id
        self.overview_calculator = overview_calculator
        self.asyncable = asyncable
        self.props = props or {}

        self.overview_calculate_handler = overview_calculate_handler
        # display_handler 为觉得此列是否需要展示的 handler
        self.display_handler = display_handler

    def get_filter_key(self, row):
        """获取筛选的键"""
        default_key = row.get(self.id, "--")
        default_value = self.get_map_value(default_key)
        return {"text": default_key, "value": default_value}

    def get_sort_key(self, row, reverse=False):
        """获取排序的键"""
        key = row.get(self.id, 0)
        return key, reverse

    def get_filter_value(self, row_data) -> str:
        return str(row_data)

    def get_value(self, row):
        """获取值"""
        value = row.get(self.id, "")
        return self.get_map_value(value)

    def format(self, row: dict) -> any:
        pass

    def column(self):
        return {
            "id": self.id,
            "name": self.name,
            "sortable": "custom" if self.sortable else False,
            "disabled": self.disabled,
            "checked": self.checked,
            "type": self.column_type,
            "width": self.width,
            "min_width": self.min_width,
            "filterable": self.filterable,
            "filter_list": self.filter_list,
            "actionId": self.action_id,
            "asyncable": self.asyncable,
            "props": self.props,
        }

    def display(self, request_data) -> bool:
        """
        决定是否展示这一列
        @param request_data 接口请求参数
        """
        if self.display_handler:
            return self.display_handler(request_data)

        return True


class StringTableFormat(TableFormat):
    column_type = "string"

    def __init__(self, *args, show_over_flow_tool_tip=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.show_over_flow_tool_tip = show_over_flow_tool_tip

    def format(self, row: dict) -> str:
        return row[self.id]

    def column(self):
        res = super().column()
        return {**res, "showOverflowTooltip": self.show_over_flow_tool_tip}


class StringLabelTableFormat(StringTableFormat):
    """具有filter映射功能的string列"""

    column_type = "string"

    def __init__(self, *args, label_getter, icon_getter=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.label_getter = label_getter
        self.icon_getter = icon_getter

    def format(self, row: dict):
        if not self.icon_getter:
            return {"text": self.label_getter.from_value(row[self.id]).label, "type": row[self.id]}

        return {
            "text": self.label_getter.from_value(row[self.id]).label,
            "type": row[self.id],
            "icon": self.icon_getter(row),
        }

    def column(self):
        res = super(StringTableFormat, self).column()
        return {**res, "showOverflowTooltip": self.show_over_flow_tool_tip}

    def get_filter_key(self, row):
        default_key = row.get(self.id, "--")
        return {"value": default_key, "text": self.label_getter.from_value(default_key).label}


class TimestampTableFormat(TableFormat):
    column_type = "timestamp"

    def __init__(self, *args, digits=1000000, **kwargs):
        super().__init__(*args, **kwargs)
        self.digits = digits

    def format(self, row: dict) -> str:
        content = row[self.id]
        try:
            return datetime.datetime.fromtimestamp(int(content) // self.digits).strftime("%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError):
            try:
                return arrow.get(content).format("YYYY-MM-DD HH:mm:ss")
            except ParserError:
                return ""


class TimeTableFormat(TableFormat):
    """时间戳列格式类。

    直接返回时间戳（秒级）
    """

    column_type = "time"

    def format(self, row: dict) -> int:
        """格式化时间戳数据。

        :param row: 行数据字典
        :return: 时间戳（秒级），如果数据无效则返回 0
        """
        content = row.get(self.id)
        try:
            return int(content)
        except (TypeError, ValueError):
            return 0


class LinkTableFormat(TableFormat):
    column_type = "link"

    def __init__(
        self, url_format: str = "", target: str = "self", event_key="", icon_get=lambda x: "", *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.url_format = url_format
        self.target = target
        self.event_key = event_key
        self.icon_get = icon_get

    def format(self, row):
        return {
            "target": self.target,
            "value": row[self.id],
            "url": self.url_format.format(**row),
            "key": self.event_key,
            "icon": self.icon_get(row),
        }


class ServiceComponentAdaptLinkFormat(LinkTableFormat):
    def format(self, row):
        if row.get("_is_service", True):
            return {
                "target": "event",
                "value": row[self.id],
                "url": self.url_format.format(**row),
                "key": self.event_key,
                "icon": self.icon_get(row),
            }
        else:
            url_format = f"/?bizId={row['bk_biz_id']}#/apm{self.url_format}"
            return {
                "target": "blank",
                "value": row[self.id],
                "url": url_format.format(**row),
                "key": self.event_key,
                "icon": self.icon_get(row),
            }


class SyncTimeLinkTableFormat(LinkTableFormat):
    def __init__(self, *args, sync_time=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.sync_time = sync_time

    def format(self, row):
        data = super().format(row)
        return {**data, "syncTime": self.sync_time}


class ScopedSlotsFormat(LinkTableFormat):
    # 前端slot列类型
    column_type = "scoped_slots"


class AliasMappingTableFormat(TableFormat):
    """
    别名映射列
    """

    column_type = "alias_string"

    def __init__(self, mappings, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mappings = mappings

    def format(self, row: dict) -> dict:
        return {"value": row[self.id], "alias": self.mappings.get(row[self.id])}

    def get_value(self, row):
        value = row[self.id]
        return self.mappings.get(value)


class LinkListTableFormat(TableFormat):
    column_type = "link_list"

    def __init__(self, links: list[LinkTableFormat], link_handler=None, *args, **kwargs):
        """
        @param links: 链接项
        @param link_handler: 决定是否展示链接项
        """
        super().__init__(*args, **kwargs)
        self.links = links
        self.link_handler = link_handler

    def format(self, row: dict) -> any:
        row_data = {}
        row_data.update(row)
        row_data.update(row[self.id])

        if not self.link_handler or self.link_handler(row):
            return [link.format(row_data) for link in self.links]

        return []


class ProgressTableFormat(TableFormat):
    column_type = "progress"

    def __init__(self, *args, clear_if_not_sorted=False, color_getter=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.clear_if_not_sorted = clear_if_not_sorted
        self.color_getter = color_getter

    def format(self, row):
        data = row[self.id]
        if data is None:
            return {"value": None, "label": None, "status": None}

        if self.color_getter:
            color = self.color_getter(data)
        else:
            if data == 0:
                color = "SUCCESS"
            elif 0 < data < 30:
                color = "NORMAL"
            else:
                color = "FAILED"

        return {"value": data, "label": f"{round(data, 2)}%", "status": color}


class CustomProgressTableFormat(TableFormat):
    """
    自定义进度条列
    要求列数据格式为:
    {
        "value": 16,
        "percent": "23.1%"
    }
    """

    column_type = "progress"

    def __init__(
        self,
        color_getter=None,
        label_calculator=None,
        max_if_overview=False,
        clear_if_not_sorted=False,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.color_getter = color_getter
        self.label_calculator = label_calculator
        self.max_if_overview = max_if_overview
        self.clear_if_not_sorted = clear_if_not_sorted

    def format(self, row):
        value = row[self.id]
        if not isinstance(value, dict):
            # 兼容概览列数据格式
            return {
                "value": (value if not self.max_if_overview else 100) if value else None,
                "label": self.label_calculator(value) if self.label_calculator else value,
                "status": self.color_getter(value) if self.color_getter else None,
            }
        if self.color_getter:
            color = self.color_getter(value["label"])
        else:
            # 默认颜色
            if value["value"] == 0:
                color = "SUCCESS"
            elif 0 < value["value"] < 30:
                color = "NORMAL"
            else:
                color = "FAILED"

        return {
            "value": value["value"],
            "label": self.label_calculator(value["label"]) if self.label_calculator else value["label"],
            "status": color,
        }


class CustomStringTableFormat(TableFormat):
    """
    自定义format的string列
    """

    column_type = "string"

    def __init__(self, formatter, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.formatter = formatter

    def format(self, row):
        return self.formatter(row)


class NumberTableFormat(TableFormat):
    column_type = "number"

    def __init__(self, unit: str = "short", decimal=5, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.unit = unit
        self.decimal = decimal

    def format(self, row):
        v = row[self.id]
        if v is None:
            return {"value": "--", "unit": ""}

        value, unit = load_unit(self.unit).auto_convert(v, decimal=self.decimal)
        return {
            "value": value,
            "unit": unit,
        }


class ColorNumberTableFormat(NumberTableFormat):
    """变色数字列"""

    def __init__(self, color_handler, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.color_handler = color_handler

    def format(self, row):
        res = super().format(row)
        color = self.color_handler(res)
        if color:
            return {**res, "color": color}

        return res


class StatusTableFormat(TableFormat):
    column_type = "status"

    def __init__(self, status_map_cls, show_tips=lambda x: False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.status_map_cls = status_map_cls
        self.show_tips = show_tips

    def get_filter_key(self, row):
        status = self.status_map_cls.from_value(row.get(self.id, "")).status
        text = status.get("text", "")
        value = self.get_map_value(status.get("type", ""))
        return {"text": text, "value": value}

    def get_value(self, row):
        status = self.status_map_cls.from_value(row.get(self.id, "")).status
        type_value = status.get("type", "")
        return self.get_map_value(type_value)

    def format(self, row):
        status = self.status_map_cls.from_value(row[self.id]).status
        if self.tips_format and self.show_tips(row[self.id]):
            status["tips"] = self.tips_format.format(**row)
        return status


class DataStatusTableFormat(TableFormat):
    """
    数据状态列 用于显示功能的数据状态
    1. 绿色勾: 开启了功能并且此功能有数据
    2. 红色感叹号: 开启了功能但是功能无数据
    3. 灰色叉叉: 未开启功能
    """

    column_type = "data_status"

    def get_filter_key(self, row):
        text = DataStatusColumnEnum.from_value(row.get(self.id)).label
        return {"text": text, "value": row.get(self.id)}

    def format(self, row):
        return {"icon": row.get(self.id)}


class DataPointsTableFormat(TableFormat):
    """
    趋势图列
    会在表格上显示趋势图
    """

    column_type = "datapoints"

    def __init__(self, unit: str = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.unit = unit

    def format(self, row: dict) -> any:
        series = row.get(self.id)
        return {"datapoints": series, "unit": self.unit}


class CollectTableFormat(TableFormat):
    column_type = "collect"
    collect_map = {True: _lazy("已收藏"), False: _lazy("未收藏")}

    def __init__(self, api: str = "", params_get=lambda item: {}, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.api = api
        self.params = params_get

    def get_filter_key(self, row):
        is_collect = row.get(self.id, False)
        text = self.collect_map.get(is_collect, _lazy("未收藏"))
        value = self.get_map_value(is_collect)
        return {"text": text, "value": value}

    def format(self, row):
        return {
            "is_collect": row[self.id],
            "api": self.api,
            "params": self.params(row),
        }


class DictSearchColumnTableFormat(TableFormat):
    def __init__(self, column_type, get_filter_value, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.column_type = column_type
        self.get_filter_value = get_filter_value

    def get_filter_value(self, row_data) -> str:
        return self.get_filter_value(row_data)

    def format(self, row):
        return row[self.id]


class OverviewDataTableFormat(StringTableFormat):
    """概览列"""

    column_type = "link"

    def __init__(self, *args, title, max_width=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = title
        self.max_width = max_width

    def column(self):
        data = super().column()
        return {**data, "max_width": self.max_width}

    def format(self, row: dict):
        return {
            # 前端概览列固定值(data内为switch_scenes_type, overview_data里面key为switch_to_overview)
            "key": "",
            "icon": "",
            "target": "null_event",
            "url": "",
            "value": super().format(row),
        }


class StackLinkTableFormat(TableFormat):
    """错误堆栈信息列"""

    column_type = "stack_link"

    def __init__(
        self, url_format: str = "", target: str = "self", event_key="", icon_get=lambda x: "", *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.url_format = url_format
        self.target = target
        self.event_key = event_key
        self.icon_get = icon_get

    def format(self, row):
        return {
            "target": self.target,
            "value": row[self.id]["title"],
            "subtitle": row[self.id]["subtitle"],
            "is_stack": True if row[self.id]["is_stack"] == _lazy("有Stack") else False,
            "url": self.url_format.format(**row),
            "key": self.event_key,
            "icon": self.icon_get(row),
        }

    def get_filter_value(self, row_data) -> str:
        return row_data["title"]


class StackLinkOverviewDataTableFormat(OverviewDataTableFormat):
    """
    嵌套概览列
    适用于value为嵌套字典的情况，将会打平返回
    """

    column_type = "stack_link"

    def format(self, row: dict):
        return {
            # 前端概览列固定值
            "key": "",
            "icon": "",
            "target": "null_event",
            "url": "",
            "value": row[self.id]["title"],
            "subtitle": row[self.id]["subtitle"],
            "is_stack": True if row[self.id]["is_stack"] == _lazy("有Stack") else False,
        }


class EndpointListTableFormat(TableFormat):
    """接口列表列格式类。

    用于 endpoint_name 列，支持 suffix_icon 类型，包含接口名称和操作链接（如调用链）。
    """

    column_type = "suffix_icon"

    def __init__(
        self,
        *args,
        title: str,
        max_width: int | None = None,
        links: list[LinkTableFormat] | None = None,
        show_over_flow_tool_tip: bool = True,
        **kwargs,
    ):
        """初始化接口列表列格式。

        :param title: 概览行显示的标题
        :param max_width: 列最大宽度
        :param links: 操作链接列表
        :param show_over_flow_tool_tip: 是否显示溢出提示
        """
        super().__init__(*args, **kwargs)
        self.title = title
        self.max_width = max_width
        self.links = links or []
        self.show_over_flow_tool_tip = show_over_flow_tool_tip

    def column(self) -> dict:
        """生成列配置"""
        return {
            **super().column(),
            "showOverflowTooltip": self.show_over_flow_tool_tip,
            "max_width": self.max_width,
        }

    def format(self, row: dict) -> list[dict]:
        """格式化单行数据。

        将接口名称和操作链接合并为列表格式。

        :param row: 行数据字典
        :return: 链接列表
        """
        result = [{"key": "", "icon": "", "target": "null_event", "url": "", "value": row[self.id]}]
        for link in self.links:
            try:
                # 不能调用 link.format(row)（会触发 row[link.id] 的 KeyError），需单独构造 url
                url = link.url_format.format(**row)
            except KeyError:
                url = ""
            result.append(
                {
                    "icon": link.icon_get(row),
                    "target": link.target,
                    "url": url,
                    "key": link.event_key,
                    "value": link.name,
                }
            )
        return result
