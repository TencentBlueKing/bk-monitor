# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


import logging

from django.utils.translation import gettext as _

from alarm_backends.constants import NO_DATA_TAG_DIMENSION
from alarm_backends.core.cache.key import CHECK_RESULT_CACHE_KEY
from alarm_backends.core.control.record_parser import RecordParser
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.core.detect_result import ANOMALY_LABEL
from bkmonitor.models import AnomalyRecord

logger = logging.getLogger("trigger")


class AnomalyChecker(object):
    """
    异常检测逻辑
    """

    # 检测窗口单位(默认1min)
    DEFAULT_CHECK_WINDOW_UNIT = 60

    def __init__(self, point, strategy, item_id):
        self.item = Strategy.get_item_in_strategy(strategy, item_id)
        self.strategy = strategy
        self.strategy_id = strategy["id"]
        self.item_id = item_id
        self.point = point
        if self.is_no_data_point(point):
            no_data_configs = Strategy.get_no_data_configs(self.item)
            no_data_level = no_data_configs.pop("level")
            self.trigger_configs = {str(no_data_level): no_data_configs}
        else:
            self.trigger_configs = Strategy.get_trigger_configs(self.strategy)

        self.check_window_unit = Strategy.get_check_window_unit(self.item, self.DEFAULT_CHECK_WINDOW_UNIT)

        self.anomaly_ids = {
            level: anomaly_info["anomaly_id"] for level, anomaly_info in list(self.point["anomaly"].items())
        }
        self.record_parser = RecordParser(point)
        # shortcut
        self.dimensions_md5 = self.record_parser.dimensions_md5
        self.source_time = self.record_parser.source_time

    @staticmethod
    def is_no_data_point(point):
        """
        :summary: 判断是否是无数据告警生成的异常点
        :param point:
        :return:
        """
        dimensions = point["data"]["dimensions"]
        if NO_DATA_TAG_DIMENSION in dimensions:
            return True
        return False

    def check(self):
        """
        异常点事件触发检测
        :return:
        """

        anomaly_level, anomaly_timestamps = self.check_anomaly()
        anomaly_records = self.gen_anomaly_records()
        event_record = self.gen_event_record(anomaly_level, anomaly_timestamps)

        result_message = _(
            "[trigger 处理结果] ({result}) record({record_id}), " "strategy({strategy_id}), item({item_id})"
        ).format(
            strategy_id=self.strategy_id,
            item_id=self.item_id,
            record_id=self.point["data"]["record_id"],
            result=bool(event_record),
        )
        if event_record:
            result_message = "{}, anomaly({})".format(result_message, self.anomaly_ids[str(anomaly_level)])
        logger.info(result_message)

        return anomaly_records, event_record

    def gen_event_record(self, anomaly_level, anomaly_timestamps):
        """
        生成事件记录，用于推送给event
        :param anomaly_level: 异常级别
        :param anomaly_timestamps: 异常字符串
        """
        if anomaly_level == -1:
            return None
        event_info = {
            "data": self.point["data"],
            "anomaly": self.point["anomaly"],
            "strategy_snapshot_key": self.point["strategy_snapshot_key"],
            "context": self.point.get("context", {}),
            "trigger": {
                "level": str(anomaly_level),
                "anomaly_ids": [
                    "{dimensions_md5}.{timestamp}.{strategy_id}.{item_id}.{level}".format(
                        dimensions_md5=self.dimensions_md5,
                        timestamp=timestamp,
                        strategy_id=self.strategy_id,
                        item_id=self.item_id,
                        level=anomaly_level,
                    )
                    for timestamp in anomaly_timestamps
                ],
            },
        }
        return event_info

    def gen_anomaly_records(self):
        """
        创建异常记录
        :rtype: list[AnomalyRecord]
        """
        origin_alarm = {
            "data": self.point["data"],
            "anomaly": self.point["anomaly"],
        }
        records = []
        for level, anomaly_info in list(self.point["anomaly"].items()):
            anomaly_record = AnomalyRecord(
                anomaly_id=anomaly_info["anomaly_id"],
                source_time=self.record_parser.mysql_time,
                strategy_id=self.strategy_id,
                origin_alarm=origin_alarm,
                event_id="",
            )
            records.append(anomaly_record)
        return records

    def check_anomaly(self):
        """
        异常检测
        :return 触发告警的告警级别，如果都没触发告警，则返回 -1
        """
        levels = sorted([int(level) for level in list(self.point["anomaly"].keys())])
        # 按照算法级别从高到低判断，如果高级别算法已经触发了，则无需判断低级别
        anomaly_level = -1
        anomaly_timestamps = []
        for level in levels:
            if anomaly_level != -1:
                logger.debug(
                    "anomaly record ({anomaly_id}) skip trigger because"
                    "high level anomaly record (level: {level}) has been trigger.".format(
                        anomaly_id=self.anomaly_ids[str(level)], level=anomaly_level
                    )
                )
                continue
            is_triggered, anomaly_timestamps = self._check_anomaly_by_level(str(level))
            if is_triggered:
                # 高级别算法满足触发条件
                anomaly_level = level
        return anomaly_level, anomaly_timestamps

    def _check_anomaly_by_level(self, level):
        """
        检测某个级别的异常点是否满足触发条件
        :param str level: 告警级别
        :return: 二元组：是否被触发，异常次数
        """
        try:
            trigger_config = self.trigger_configs[level]
        except KeyError:
            trigger_configs = self.trigger_configs.values()
            if not trigger_configs:
                # 如果该等级没有在策略中配置，则不检测
                logger.error(
                    "strategy({}), item({}) level({}) trigger config not exists".format(
                        self.strategy_id, self.item_id, level
                    )
                )
                return False, []

            # 默认兜底，trigger 配置当前所有告警级别默认一致
            trigger_config = list(trigger_configs)[0]

        check_cache_key = CHECK_RESULT_CACHE_KEY.get_key(
            strategy_id=self.strategy_id,
            item_id=self.item_id,
            dimensions_md5=self.dimensions_md5,
            level=level,
        )
        # 在对应的打点队列中取出打点信息。时间范围为source_time前后的一个窗口偏移量
        check_window_offset = trigger_config["check_window_size"] * self.check_window_unit - 1
        check_results = CHECK_RESULT_CACHE_KEY.client.zrangebyscore(
            name=check_cache_key, min=self.source_time - check_window_offset, max=self.source_time, withscores=True
        )
        # 统计包含异常标记的key的数量，并与trigger_count进行比较
        anomaly_timestamps = []
        for label, score in check_results:
            if label.endswith(ANOMALY_LABEL):
                anomaly_timestamps.append(int(score))

        anomaly_times = len(anomaly_timestamps)
        is_triggered = anomaly_times >= trigger_config["trigger_count"]
        if anomaly_times >= 2 and not is_triggered and self.is_no_data_point(self.point):
            # 无数据判定补充：
            # 1. 所有检测记录均为异常点
            # 2. 异常点间时间差异符合无数据配置的周期
            start, end = anomaly_timestamps[0], anomaly_timestamps[-1]
            always_nodata = anomaly_times == len(check_results)
            is_triggered = always_nodata and (
                (end - start) >= (trigger_config["trigger_count"] - 1) * self.check_window_unit
            )

        return is_triggered, anomaly_timestamps
