"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import datetime
from typing import Any

import arrow
from django.conf import settings

from apps.api import TransferApi
from apps.log_search.constants import TimeFieldTypeEnum, TimeFieldUnitEnum
from apps.log_search.exceptions import SearchUnKnowTimeFieldType
from apps.log_search.models import Scenario
from apps.utils.cache import cache_ten_minute
from apps.utils.log import logger


class QueryTimeBuilder:
    TIME_FIELD_UNIT_RATE_MAP = {
        TimeFieldUnitEnum.SECOND.value: 1,
        TimeFieldUnitEnum.MILLISECOND.value: 1000,
        TimeFieldUnitEnum.MICROSECOND.value: 1000000,
    }

    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"

    def __init__(
        self,
        time_field: str = "",
        start_time: datetime = "",
        end_time: datetime = "",
        time_field_type: str = TimeFieldTypeEnum.DATE.value,
        time_field_unit: str = TimeFieldUnitEnum.SECOND.value,
        include_start_time: bool = True,
        include_end_time: bool = True,
        indices: str = "",
        scenario_id: str = "",
    ):
        self.time_field: str = time_field
        self.start_time: int | datetime
        self.end_time: int | datetime
        self.time_field_type = time_field_type
        self.time_field_unit = time_field_unit
        self.indices = indices
        self.scenario_id = scenario_id

        self._time_range_dict: dict = {}

        self.start_time, self.end_time = self.time_serilizer(start_time, end_time)

        self.start_time_filter = self._start_time_filter(include_start_time)
        self.end_time_filter = self._end_time_filter(include_end_time)

    @property
    def time_range_dict(self):
        # 返回构建dsl的时间字典
        if self.time_field_type in ["date", "date_nanos", "conflict"]:
            self._time_range_dict.update(
                {
                    self.time_field: {
                        self.start_time_filter: int(self.start_time * 1000),
                        self.end_time_filter: int(self.end_time * 1000),
                        "format": "epoch_millis",
                    }
                }
            )
            return self._time_range_dict
        if self.time_field_type in ["long"]:
            time_field_unit_rate = self.TIME_FIELD_UNIT_RATE_MAP.get(self.time_field_unit)
            if time_field_unit_rate is not None:
                self._time_range_dict.update(
                    {
                        self.time_field: {
                            self.start_time_filter: int(self.start_time * time_field_unit_rate),
                            self.end_time_filter: int(self.end_time * time_field_unit_rate),
                        }
                    }
                )
            return self._time_range_dict

        raise SearchUnKnowTimeFieldType()

    def time_serilizer(self, start_time: Any, end_time: Any) -> tuple[Any | int, Any | int]:
        if settings.DEAL_RETENTION_TIME:
            start_time, end_time = self._deal_time(start_time, end_time)
        # 序列化接口能够识别的时间格式
        return start_time.timestamp(), end_time.timestamp()

    def _start_time_filter(self, include_start_time):
        if include_start_time:
            return self.GTE
        return self.GT

    def _end_time_filter(self, include_end_time):
        if include_end_time:
            return self.LTE
        return self.LT

    @cache_ten_minute("retention_time_{indices}_{scenario_id}", need_md5=True)
    def get_storage_retention_time(self, indices, scenario_id):
        # 仅自有采集类型索引支持获取结果表，非自有采集类型不做处理
        # 一个索引集包含有多个结果表的情况，不处理
        if scenario_id == Scenario.LOG:
            try:
                if "," in indices:
                    return None

                storage = TransferApi.get_result_table_storage(
                    params={"result_table_list": indices, "storage_type": "elasticsearch"}
                )[indices]
                retention = int(storage["storage_config"]["retention"])
                return retention
            except Exception as e:
                # 接口获取异常/retention不存在，跳过过期时间处理
                logger.exception("get_result_table_storage_error: indices: %s, reason: %s", indices, e)
        return None

    def _deal_time(self, start_time, end_time):
        retention = self.get_storage_retention_time(indices=self.indices, scenario_id=self.scenario_id)
        # retention为0或None，不做处理
        if retention:
            current_time = arrow.now(start_time.tzinfo)
            retention_time = current_time.shift(days=-int(retention))
            # 向下取整
            retention_time = retention_time.floor("minute")
            # 开始时间限制在过期时间前，结束时间则不做处理
            # 所以会出现结束时间小于开始时间的情况
            if start_time < retention_time:
                start_time = retention_time
        return start_time, end_time
