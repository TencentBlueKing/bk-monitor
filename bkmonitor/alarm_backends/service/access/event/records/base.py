"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
from collections import defaultdict

import arrow
from django.utils.functional import cached_property

from alarm_backends import constants
from alarm_backends.service.access.base import Filterer
from bkmonitor.utils.common_utils import count_md5

logger = logging.getLogger("access.event")


class EventRecord(Filterer):
    """
    A EventRecord instance represents an event being handled.

    You should inherit this class and implement the clean_xxxx method
    """

    def __init__(self, raw_data):
        super().__init__()
        self.raw_data = raw_data
        self.data = {}

        self.is_retains = defaultdict(lambda: True)  # 保留记录，记录当前record经过filter之后是否仍然保留下来
        self.inhibitions = defaultdict(bool)  # 抑制记录，记录当前record是否被抑制

    def __str__(self):
        return json.dumps(self.__dict__)

    def to_str(self):
        return json.dumps(self.data)

    def check(self):
        """Check if origin data is valid, (default: return True)"""
        return True

    def flat(self):
        """Flatten into multi EventRecord, (default: return self)"""
        return [self]

    def full(self):
        """Add some other property to data, (default: do nothing)"""
        return [self]

    ######################
    #      PROPERTY      #
    ######################
    @cached_property
    def dimensions(self):
        return self.raw_data["dimensions"]

    @cached_property
    def event_time(self):
        return arrow.get(self.raw_data["_time_"]).timestamp

    @cached_property
    def md5_dimension(self):
        return count_md5(self.dimensions)

    @cached_property
    def _strategy_id(self):
        return self.raw_data["strategy"].id

    @cached_property
    def bk_tenant_id(self) -> str:
        return self.raw_data["strategy"].bk_tenant_id

    @cached_property
    def _item_id(self):
        if self._item:
            return self._item.id

    @cached_property
    def _item(self):
        items = self.raw_data["strategy"].items
        return items[0] if items else None

    @cached_property
    def scenario(self):
        return self.raw_data["strategy"].scenario

    @cached_property
    def strategy(self):
        return self.raw_data["strategy"]

    @cached_property
    def items(self):
        """
        事件类只有一个item，故这里直接返回一个list，包装self._item
        """
        return [self._item]

    @cached_property
    def bk_biz_id(self):
        return self.raw_data["strategy"].bk_biz_id

    @cached_property
    def level(self):
        item_list = self.raw_data["strategy"].items
        if item_list:
            return item_list[0].algorithms[0]["level"]
        return -1

    #########################
    #         CLEAN         #
    #########################

    def clean(self):
        def clean_default_method():
            return ""

        for prop in constants.StandardEventFields:
            clean_method_name = f"clean_{prop}"
            clean_value = getattr(self, clean_method_name, clean_default_method)()
            self.data[prop] = clean_value

    def clean_data(self):
        standard_data_field = {}
        for field in constants.StandardDataFields:
            clean_method_name = f"clean_{field}"
            clean_value = getattr(self, clean_method_name, lambda: "")()
            standard_data_field[field] = clean_value
        return standard_data_field

    def clean_anomaly(self):
        standard_anomaly_field = {}
        for field in constants.StandardAnomalyFields:
            clean_method_name = f"clean_{field}"
            clean_value = getattr(self, clean_method_name, lambda: "")()
            standard_anomaly_field[field] = clean_value
        return {self.level: standard_anomaly_field}

    def clean_strategy_snapshot_key(self):
        return self.raw_data["strategy"].gen_strategy_snapshot()

    @property
    def filter_dimensions(self) -> dict:
        return {}

    def clean_dimension_fields(self):
        if "agent_version" in self.dimensions:
            return ["bk_target_ip", "bk_target_cloud_id", "agent_version"]
        return ["bk_target_ip", "bk_target_cloud_id"]
