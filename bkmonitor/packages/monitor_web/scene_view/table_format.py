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
import datetime
from abc import ABC
from typing import List

from django.utils.translation import gettext_lazy as _lazy

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
        super(StringTableFormat, self).__init__(*args, **kwargs)
        self.show_over_flow_tool_tip = show_over_flow_tool_tip

    def format(self, row: dict) -> str:
        return row[self.id]

    def column(self):
        res = super(StringTableFormat, self).column()
        return {**res, "showOverflowTooltip": self.show_over_flow_tool_tip}


class StringLabelTableFormat(StringTableFormat):
    """具有filter映射功能的string列"""

    column_type = "string"

    def __init__(self, *args, label_getter, icon_getter=None, **kwargs):
        super(StringLabelTableFormat, self).__init__(*args, **kwargs)
        self.label_getter = label_getter
        self.icon_getter = icon_getter

    def format(self, row: dict):
        if not self.icon_getter:
            return {"text": self.label_getter(row[self.id]), "type": row[self.id]}

        return {"text": self.label_getter(row[self.id]), "type": row[self.id], "icon": self.icon_getter(row)}

    def column(self):
        res = super(StringTableFormat, self).column()
        return {**res, "showOverflowTooltip": self.show_over_flow_tool_tip}

    def get_filter_key(self, row):
        default_key = row.get(self.id, "--")
        return {"value": default_key, "text": self.label_getter(default_key)}


class TimestampTableFormat(TableFormat):
    column_type = "timestamp"

    def __init__(self, *args, digits=1000000, **kwargs):
        super(TimestampTableFormat, self).__init__(*args, **kwargs)
        self.digits = digits

    def format(self, row: dict) -> str:
        return datetime.datetime.fromtimestamp(int(row[self.id]) // self.digits).strftime("%Y-%m-%d %H:%M:%S")


class LinkTableFormat(TableFormat):
    column_type = "link"

    def __init__(
        self, url_format: str = "", target: str = "self", event_key="", icon_get=lambda x: "", *args, **kwargs
    ):
        super(LinkTableFormat, self).__init__(*args, **kwargs)
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
        super(SyncTimeLinkTableFormat, self).__init__(*args, **kwargs)
        self.sync_time = sync_time

    def format(self, row):
        data = super(SyncTimeLinkTableFormat, self).format(row)
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
        super(AliasMappingTableFormat, self).__init__(*args, **kwargs)
        self.mappings = mappings

    def format(self, row: dict) -> dict:
        return {"value": row[self.id], "alias": self.mappings.get(row[self.id])}

    def get_value(self, row):
        value = row[self.id]
        return self.mappings.get(value)


class LinkListTableFormat(TableFormat):
    column_type = "link_list"

    def __init__(self, links: List[LinkTableFormat], link_handler=None, *args, **kwargs):
        """
        @param links: 链接项
        @param link_handler: 决定是否展示链接项
        """
        super(LinkListTableFormat, self).__init__(*args, **kwargs)
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
        super(ProgressTableFormat, self).__init__(*args, **kwargs)
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
        super(CustomProgressTableFormat, self).__init__(*args, **kwargs)
        self.color_getter = color_getter
        self.label_calculator = label_calculator
        self.max_if_overview = max_if_overview
        self.clear_if_not_sorted = clear_if_not_sorted

    def format(self, row):
        value = row[self.id]
        if not isinstance(value, dict):
            # 兼容概览列数据格式
            return {
                "value": value if not self.max_if_overview else 100,
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
        super(CustomStringTableFormat, self).__init__(*args, **kwargs)
        self.formatter = formatter

    def format(self, row):
        return self.formatter(row)


class NumberTableFormat(TableFormat):
    column_type = "number"

    def __init__(self, unit: str = "short", decimal=5, *args, **kwargs):
        super(NumberTableFormat, self).__init__(*args, **kwargs)
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
        super(ColorNumberTableFormat, self).__init__(*args, **kwargs)
        self.color_handler = color_handler

    def format(self, row):
        res = super(ColorNumberTableFormat, self).format(row)
        color = self.color_handler(res)
        if color:
            return {**res, "color": color}

        return res


class StatusTableFormat(TableFormat):
    column_type = "status"

    def __init__(self, status_map_cls, show_tips=lambda x: False, *args, **kwargs):
        super(StatusTableFormat, self).__init__(*args, **kwargs)
        self.status_map_cls = status_map_cls
        self.show_tips = show_tips

    def get_filter_key(self, row):
        status = self.status_map_cls.get_status_by_key(row.get(self.id, ""))
        text = status.get("text", "")
        value = self.get_map_value(status.get("type", ""))
        return {"text": text, "value": value}

    def get_value(self, row):
        status = self.status_map_cls.get_status_by_key(row.get(self.id, ""))
        type_value = status.get("type", "")
        return self.get_map_value(type_value)

    def format(self, row):
        status = self.status_map_cls.get_status_by_key(row[self.id])
        if self.tips_format and self.show_tips(row[self.id]):
            status["tips"] = self.tips_format.format(**row)
        return status


class CollectTableFormat(TableFormat):
    column_type = "collect"
    collect_map = {True: _lazy("已收藏"), False: _lazy("未收藏")}

    def __init__(self, api: str = "", params_get=lambda item: {}, *args, **kwargs):
        super(CollectTableFormat, self).__init__(*args, **kwargs)
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
        super(DictSearchColumnTableFormat, self).__init__(*args, **kwargs)
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
        super(OverviewDataTableFormat, self).__init__(*args, **kwargs)
        self.title = title
        self.max_width = max_width

    def column(self):
        data = super(OverviewDataTableFormat, self).column()
        return {**data, "max_width": self.max_width}

    def format(self, row: dict):
        return {
            # 前端概览列固定值(data内为switch_scenes_type, overview_data里面key为switch_to_overview)
            "key": "",
            "icon": "",
            "target": "null_event",
            "url": "",
            "value": super(OverviewDataTableFormat, self).format(row),
        }


class StackLinkTableFormat(TableFormat):
    """错误堆栈信息列"""

    column_type = "stack_link"

    def __init__(
        self, url_format: str = "", target: str = "self", event_key="", icon_get=lambda x: "", *args, **kwargs
    ):
        super(StackLinkTableFormat, self).__init__(*args, **kwargs)
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
