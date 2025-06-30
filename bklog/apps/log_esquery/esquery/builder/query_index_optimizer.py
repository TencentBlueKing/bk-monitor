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

from typing import Any

import arrow
from apps.log_esquery.constants import INDICES_LENGTH
from apps.log_esquery.type_constants import type_index_set_list, type_index_set_string
from apps.log_search.models import Scenario
from apps.utils.function import map_if
from dateutil import tz
from dateutil.rrule import DAILY, MONTHLY, rrule


class QueryIndexOptimizer:
    def __init__(
        self,
        indices: type_index_set_string,
        scenario_id: str,
        start_time: arrow.Arrow = None,
        end_time: arrow.Arrow = None,
        time_zone: str = None,
        use_time_range: bool = True,
    ):
        self._index: str = ""
        if not indices:
            return

        indices = indices.replace(" ", "")
        result_table_id_list: list[str] = map_if(indices.split(","))
        # 根据查询场景优化index
        if scenario_id in [Scenario.BKDATA, Scenario.LOG]:
            # 日志采集使用0时区区分index入库,数据平台使用服务器所在时区
            time_zone = "GMT" if scenario_id == Scenario.LOG else tz.gettz()
            result_table_id_list = self.index_filter(result_table_id_list, start_time, end_time, time_zone)

        if not use_time_range:
            result_table_id_list = []

        self._index = ",".join(result_table_id_list)

        if not self._index:
            map_func_map = {
                Scenario.LOG: lambda x: f"{x}_*",
                Scenario.BKDATA: lambda x: f"{x}_*",
                Scenario.ES: lambda x: f"{x}",
            }
            result_table_id_list: list[str] = map_if(indices.split(","), map_func_map.get(scenario_id))

            self._index = ",".join(result_table_id_list)
        if scenario_id in [Scenario.LOG]:
            self._index = self._index.replace(".", "_")

    @property
    def index(self):
        return self._index

    def index_filter(
        self, result_table_id_list: type_index_set_list, start_time: arrow.Arrow, end_time: arrow.Arrow, time_zone: str
    ) -> list[str]:
        # BkData索引集优化
        date_format = ""
        while True:
            final_index_list: list = []
            for x in result_table_id_list:
                a_index_list, date_format = self.index_time_filter(x, start_time, end_time, time_zone, date_format)
                final_index_list = final_index_list + a_index_list
            date_format = "%".join(date_format.split("%")[:-1])
            if len(",".join(final_index_list)) < INDICES_LENGTH or not date_format:
                break
        return final_index_list

    def index_time_filter(
        self, index: str, date_start: arrow.Arrow, date_end: arrow.Arrow, time_zone: str, date_format: str
    ):
        date_start = date_start.to(time_zone)
        date_end = date_end.to(time_zone)
        now = arrow.now(time_zone)

        if date_end > now:
            date_end = now

        date_day_list: list[Any] = list(
            rrule(DAILY, interval=1, dtstart=date_start.floor("day").datetime, until=date_end.ceil("day").datetime)
        )

        date_month_list: list[Any] = list(
            rrule(
                MONTHLY, interval=1, dtstart=date_start.floor("month").datetime, until=date_end.ceil("month").datetime
            )
        )

        filter_list, date_format = self._generate_filter_list(index, date_day_list, date_month_list, date_format)
        return list(set(filter_list)), date_format

    def _generate_filter_list(self, index, date_day_list, date_month_list, date_format):
        filter_list: type_index_set_list = []
        if len(date_day_list) == 1:
            date_format = date_format or "%Y%m%d"
            for x in date_day_list:
                filter_list.append(f"{index}_{x.strftime(date_format)}*")
        elif len(date_day_list) > 1 and len(date_month_list) == 1:
            if len(date_day_list) > 14:
                date_format = date_format or "%Y%m"
                for x in date_month_list:
                    filter_list.append(f"{index}_{x.strftime(date_format)}*")
            else:
                date_format = date_format or "%Y%m%d"
                for x in date_day_list:
                    filter_list.append(f"{index}_{x.strftime(date_format)}*")
        elif len(date_day_list) > 1 and len(date_month_list) > 1:
            date_format = date_format or "%Y%m"
            if len(date_month_list) <= 6:
                for x in date_month_list:
                    filter_list.append(f"{index}_{x.strftime(date_format)}*")
            else:
                for x in date_month_list[-6::1]:
                    filter_list.append(f"{index}_{x.strftime(date_format)}*")
        return filter_list, date_format
