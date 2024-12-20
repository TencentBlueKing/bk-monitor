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

import json
import logging
import time
from typing import List

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.functional import cached_property

from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.service.access.data.processor import AccessDataProcess, DataRecord
from alarm_backends.service.detect import DataPoint
from alarm_backends.service.detect.process import DetectProcess

logger = logging.getLogger("access.data")


"""
# 用法:
workon bkmonitorv3-monitor

./bin/manage.sh strategy_check -s [strategy_id]\
--from=1653056040 --until=1653056280 \
--filter=bk_target_ip:127.0.0.1,time:1653056040


# -s 参数： 策略id
# from/until 参数： 数据拉取范围，不填默认当前最近5分钟
# filter 参数： 输入过滤数据条件格式： k:v,k1:v1
# filter参数注意： 暂不支持过滤值中带有逗号的情况

示例：
./bin/manage.sh strategy_check -s 123 --from=1653137100 --filter=pod_name:logstash-v3-app-logstash-0
"""

strategy_output = {}


def record_event(action: str, item_list: List, item_func=lambda item: item):
    def dumy_item_func(x):
        return ""

    total = len(item_list)
    if total:
        sample = item_list[0]
    else:
        sample = ""
        item_func = dumy_item_func
    print(f"---------[{action}] done! total: {total}, one of is {item_func(sample)}\n")


class DebugDetectProcess(DetectProcess):
    def debug_detect(self, access_output):
        item = self.strategy.items[0]
        self.inputs[item.id] = []
        inputs = [DataPoint(i.data, item) for i in access_output]
        self.pull_data(item, inputs=inputs)
        data_points = self.inputs[item.id]
        record_event("detect.pull", data_points, lambda i: i.as_dict())
        self.handle_data(item)
        data_points = self.outputs[item.id]
        record_event("detect.handle", data_points)
        if not data_points:
            print("[skip]double check: no anomaly_points")
            return
        if int(self.strategy.id) not in settings.DOUBLE_CHECK_SUM_STRATEGY_IDS:
            print(
                f"[skip]double check: strategy({self.strategy.id}) "
                f"not in grayscale list({settings.DOUBLE_CHECK_SUM_STRATEGY_IDS})"
            )
            return
        self.double_check(item)


class DebugAccessDataProcess(AccessDataProcess):
    debug_points_num = 10

    def __init__(self, strategy_group_key, *args, **kwargs):
        super(DebugAccessDataProcess, self).__init__(strategy_group_key, *args, **kwargs)
        self.strategy_id = int(kwargs.pop("strategy_id"))

    def __call__(self, from_timestamp, until_timestamp, **filters):
        if "time" in filters:
            filters["_time_"] = filters.pop("time")
        self.filter_dict = filters
        return self.debug_access(from_timestamp, until_timestamp)

    @cached_property
    def items(self):
        strategy = Strategy(self.strategy_id)
        return strategy.items

    def debug_access(self, from_timestamp, until_timestamp):
        # pull records
        first_item = self.items[0]
        item_records = first_item.query_record(from_timestamp, until_timestamp)
        records = []
        for i in reversed(item_records):
            for dimension_key, dimension_value in self.filter_dict.items():
                if dimension_key not in i or str(i[dimension_key]) != str(dimension_value):
                    break
            else:
                point = DataRecord(self.items, i)
                records.append(point)

        if len(records) <= self.debug_points_num:
            for point in records:
                point.data.update({"__debug__": True})
        else:
            print(f"\n[warning] access pull points is more than {self.debug_points_num}, detect debug disabled")
            filter_example = ",".join([f"{k}:{str(v)}" for k, v in records[0].dimensions.items()])
            filter_example += f",time:{records[0].time}"
            print(f"\tfor more detail debug info add filter params like this:\n\t\t--filter={filter_example}\n")
        record_event("access.pull", records, item_func=lambda i: i.raw_data)
        self.record_list = records
        # handle records
        # pop ExpireFilter
        expire_filter = None
        for f in self.filters:
            if f.__class__.__name__ == "ExpireFilter":
                expire_filter = f
        self.filters.remove(expire_filter)
        self.handle()
        output = [
            r for r in self.record_list if (r.is_retains[self.items[0].id] and not r.inhibitions[self.items[0].id])
        ]
        record_event("access.handle", output, item_func=lambda i: i.data)
        return output


class Command(BaseCommand):
    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument("-s", dest="strategy_id", help="strategy id", required=True)
        parser.add_argument("--from", type=int)
        parser.add_argument("--until", type=int)
        parser.add_argument("--max", type=int, default=10)
        parser.add_argument("--profile", type=bool, default=False)
        parser.add_argument(
            "--filter",
        )

    def handle(self, strategy_id, *args, **options):
        try:
            from pyinstrument import Profiler

            profile = options.pop("profile", False)
        except ImportError:
            profile = False

        if not profile:
            s_ids = [s_id.strip() for s_id in strategy_id.split(",")]
            for s_id in s_ids:
                self._handle(s_id, *args, **options)

            for _id, info in strategy_output.items():
                if not info[1]:
                    print(_id, *info)
            return

        profiler = Profiler()
        profiler.start()

        self._handle(strategy_id, *args, **options)

        profiler.stop()
        profiler.print()

    def _handle(self, strategy_id, *args, **options):
        # 不传时间参数默认最近3分钟
        from_timestamp = options.get("from") or int(time.time()) - 360
        until_timestamp = options.get("until") or int(time.time()) - 60
        DebugAccessDataProcess.debug_points_num = options.get("max")
        print(f"---------strategy({strategy_id}) to group_key----------")
        strategy = StrategyCacheManager.get_strategy_by_id(strategy_id)
        if not strategy:
            print("strategy({}) no config, please confirm that the strategy_id is correct.".format(strategy_id))
            return

        strategy_output[strategy_id] = [strategy["name"], 0]

        for item in strategy["items"]:
            if item.get("query_md5"):
                print(
                    "[info] strategy({}), item({}) strage_group_key({})".format(
                        strategy_id, item["id"], item["query_md5"]
                    )
                )
                group_key = item["query_md5"]
                break
        else:
            print(f"unsupported strategy_id: {strategy_id}, with strategy_config is: ")
            print(json.dumps(strategy, indent=4))
            return
        filters = options.get("filter")
        if filters:
            filters = dict([kv.strip().split(":", 1) for kv in filters.split(",")])
            print(f"[info] dimension filters is {filters}")
        run_check(strategy_id, group_key, from_timestamp, until_timestamp, **filters or {})


def run_check(strategy_id, group_key, from_timestamp, until_timestamp, **filters):
    # access
    try:
        access = DebugAccessDataProcess(group_key, strategy_id=strategy_id)
        output = access(from_timestamp, until_timestamp, **filters)
        strategy_output[strategy_id][1] += len(output)
    except Exception:
        strategy_output[strategy_id][1] = "error"

    print(strategy_id, *strategy_output[strategy_id])
