"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import time
from collections import defaultdict
from typing import TYPE_CHECKING

from django.conf import settings
from django.utils.functional import cached_property

from alarm_backends import constants
from alarm_backends.service.access import base
from bkmonitor.utils.common_utils import count_md5, number_format
from constants.strategy import (
    SYSTEM_PROC_PORT_DYNAMIC_DIMENSIONS,
    SYSTEM_PROC_PORT_METRIC_ID,
)

if TYPE_CHECKING:
    from alarm_backends.core.control.item import Item

logger = logging.getLogger("access.data")


def _is_proc_port_value_exist(value) -> bool:
    """
    判断进程端口值是否存在
    """
    if isinstance(value, str):
        if not value or not value[1:-1]:
            return False
    return True


def calculate_record_id(raw_data: dict, item: "Item") -> tuple[str, int]:
    """
    根据原始数据计算 record_id

    Args:
        raw_data: 原始数据 dict
        item: Item 对象，用于获取维度信息

    Returns:
        tuple[str, int]: (record_id, time)
    """
    # 获取时间
    record_time = raw_data.get("_time_") or raw_data.get("time")

    # 提取原始维度
    dimensions = {}
    if item.query.dimensions is None:
        for k, value in raw_data.items():
            if k not in ["_time_", "_result_"] and not k.startswith("bk_task_index_"):
                dimensions[k] = value
    else:
        for field in item.query.dimensions:
            field_value = raw_data.get(field)
            if field in SYSTEM_PROC_PORT_DYNAMIC_DIMENSIONS:
                if not _is_proc_port_value_exist(field_value):
                    continue
            dimensions[field] = field_value

    # 处理进程端口特殊情况
    if SYSTEM_PROC_PORT_METRIC_ID in item.metric_ids:
        dimensions = {
            field: value
            for field, value in list(dimensions.items())
            if field not in SYSTEM_PROC_PORT_DYNAMIC_DIMENSIONS
        }

    # 计算 MD5
    md5_dimension = count_md5(dimensions)
    record_id = f"{md5_dimension}.{record_time}"

    return record_id, record_time


def get_value_from_raw_data(raw_data: dict, item: "Item"):
    """
    从原始数据中获取 value

    Args:
        raw_data: 原始数据 dict
        item: Item 对象

    Returns:
        value 或 None
    """
    if item.query.metrics[0].get("method", "").upper() == "REAL_TIME":
        return raw_data.get(item.query.metrics[0]["field"])
    else:
        return raw_data.get("_result_")


class DataRecord(base.BaseRecord):
    """
    raw_data:
    {
        "bk_target_ip":"127.0.0.1",
        "load5":1.38,
        "bk_target_cloud_id":"0",
        "time":1569246480
    }

    output_standard_data:
    {
        "record_id":"f7659f5811a0e187c71d119c7d625f23",
        "value":1.38,
        "values":{
            "timestamp":1569246480,
            "load5":1.38
        },
        "dimensions":{
            "bk_target_ip":"127.0.0.1",
            "bk_target_cloud_id":"0"
        },
        "time":1569246480
    }
    """

    items: list["Item"]
    _item: "Item"

    def __init__(self, item_or_items: "Item | list[Item]", raw_data: dict):
        """
        :param item_or_items: 具有相同查询条件的item集合
        :param raw_data: 原始数据记录
        """
        super().__init__(raw_data)

        # 一个Record可以属于多个items，后续不能再使用record身上的item，需要使用items
        if not isinstance(item_or_items, list | tuple):
            self.items = [item_or_items]
            self._item = item_or_items
        else:
            self.items = item_or_items
            self._item = self.items[0]
        self.scenario = (
            self._item.strategy.scenario
        )  # 监控对象，相同查询条件的items，监控场景一定是相同的，由rt的label决定

        self.is_retains = defaultdict(lambda: True)  # 保留记录，记录当前record经过filter之后是否仍然保留下来
        self.is_duplicate = False  # 是否重复记录，记录当前record是否是重复记录
        self.inhibitions = defaultdict(bool)  # 抑制记录，记录当前record是否被抑制

    @cached_property
    def bk_tenant_id(self) -> str:
        return self._item.bk_tenant_id

    @cached_property
    def time(self):
        # DataSource的时间字段标准为_time_，time为了兼容实时监控
        return self.raw_data.get("_time_") or self.raw_data["time"]

    @cached_property
    def value(self):
        """
        1. 单位转换
        2. 四舍五入，保留两位
        """
        # 判断是否实时告警
        if self._item.query.metrics[0].get("method", "").upper() == "REAL_TIME":
            value = self.raw_data.get(self._item.query.metrics[0]["field"])
        else:
            value = self.raw_data.get("_result_")
        if value is None:
            return
        return self._convert(value)

    @cached_property
    def values(self):
        values = {}
        for metric in self._item.query.metrics:
            value = None
            metric_field = ""
            if metric.get("alias"):
                value = self.raw_data.get(metric["alias"])
                metric_field = metric["alias"]

            if value is None:
                value = self.raw_data.get(metric["field"])
                metric_field = metric["field"]

            values[metric_field] = self._convert(value)

        for data_source in self._item.data_sources:
            values[data_source.time_field] = self.time

        return values

    @cached_property
    def dimensions(self):
        """
        第一次返回原始维度，经过维度补充后，有可能获取到补充的维度数据。
        """
        return self._origin_dimension()

    @cached_property
    def record_id(self):
        """
        记录ID=维度+时间(使用原始数据维度，计算MD5)
        """
        record_id, _ = calculate_record_id(self.raw_data, self._item)
        return record_id

    def clean(self):
        """
        数据格式化
        """

        def clean_default_method():
            return ""

        standard_prop = {}
        for prop in constants.StandardDataFields:
            clean_method_name = f"clean_{prop}"
            clean_value = getattr(self, clean_method_name, clean_default_method)()
            standard_prop[prop] = clean_value
        self.data.update(standard_prop)

        # SLI(access) - 记录当前处理时间，用于 SLI 统计各模块间处理延迟场景
        self.data["access_time"] = time.time()
        return self

    def clean_dimension_fields(self) -> list[str]:
        # 动态维度，不参与后续detect之后的唯一性判定。
        # dimension_fields 在trigger模块中， 参与生成event的 tags，用以标识事件唯一性。
        fields = self._origin_dimension().keys()
        if SYSTEM_PROC_PORT_METRIC_ID in self._item.metric_ids:
            return [field for field in fields if field not in SYSTEM_PROC_PORT_DYNAMIC_DIMENSIONS]
        return list(fields)

    def clean_record_id(self):
        return self.record_id

    def clean_time(self):
        return self.time

    def clean_value(self):
        return self.value

    def clean_values(self):
        return self.values

    def clean_dimensions(self):
        return self.dimensions

    ###################
    # PRIVATE METHODS #
    ###################
    def _convert(self, value):
        value = number_format(value)
        if value and not isinstance(value, str):
            return round(value, settings.POINT_PRECISION)
        else:
            return value

    def _origin_dimension(self):
        """
        获取原始数据的维度
        """
        dimensions = {}
        if self._item.query.dimensions is None:
            for key, value in self.raw_data.items():
                if key not in ["_time_", "_result_"] and not key.startswith("bk_task_index_"):
                    dimensions[key] = value
        else:
            for field in self._item.query.dimensions:
                field_value = self.raw_data.get(field)
                if field in SYSTEM_PROC_PORT_DYNAMIC_DIMENSIONS:
                    if not self._is_proc_port_value_exist(field_value):
                        continue
                dimensions[field] = field_value
        return dimensions

    @staticmethod
    def _is_proc_port_value_exist(value):
        exist = True
        if isinstance(value, str):
            if not value or not value[1:-1]:
                exist = False
        return exist
