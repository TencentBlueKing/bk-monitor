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

from django.utils.translation import gettext as _

from alarm_backends.constants import NO_DATA_TAG_DIMENSION
from alarm_backends.core.cache.key import CHECK_RESULT_CACHE_KEY
from alarm_backends.core.control.record_parser import RecordParser
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.core.detect_result import ANOMALY_LABEL
from alarm_backends.core.storage.redis_cluster import routed_client

logger = logging.getLogger("trigger")


class AnomalyChecker:
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
        self.levels = [str(level) for level in sorted(map(int, self.anomaly_ids))]
        self.first_window = None
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
        event_record = self.gen_event_record(anomaly_level, anomaly_timestamps)

        result_message = _(
            "[trigger 处理结果] ({result}) record({record_id}), strategy({strategy_id}), item({item_id})"
        ).format(
            strategy_id=self.strategy_id,
            item_id=self.item_id,
            record_id=self.point["data"]["record_id"],
            result=bool(event_record),
        )
        if event_record:
            result_message = f"{result_message}, anomaly({self.anomaly_ids[str(anomaly_level)]})"
        logger.info(result_message)

        return event_record

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
                    f"{self.dimensions_md5}.{timestamp}.{self.strategy_id}.{self.item_id}.{anomaly_level}"
                    for timestamp in anomaly_timestamps
                ],
            },
        }
        return event_info

    def check_anomaly(self):
        """
        异常检测
        :return 触发告警的告警级别，如果都没触发告警，则返回 -1
        """
        anomaly_timestamps = []
        for level in self.levels:
            is_triggered, anomaly_timestamps = self._check_anomaly_by_level(level)
            if is_triggered:
                return int(level), anomaly_timestamps
        return -1, anomaly_timestamps

    def _check_anomaly_by_level(self, level):
        """
        检测某个级别的异常点是否满足触发条件
        :param str level: 告警级别
        :return: 二元组：是否被触发，异常次数
        """
        config = self._trigger_config(level)
        if config is None:
            logger.error(
                "strategy(%s), item(%s) level(%s) trigger config not exists", self.strategy_id, self.item_id, level
            )
            return False, []
        if level == self.levels[0] and self.first_window is not None:
            check_results, self.first_window = self.first_window, None
        else:
            check_results = self._read_window(CHECK_RESULT_CACHE_KEY.client, level, config)
        # 统计包含异常标记的key的数量，并与trigger_count进行比较
        anomaly_timestamps = []
        for label, score in check_results:
            if label.endswith(ANOMALY_LABEL):
                anomaly_timestamps.append(int(score))

        anomaly_times = len(anomaly_timestamps)
        is_triggered = anomaly_times >= config["trigger_count"]
        if anomaly_times >= 2 and not is_triggered and self.is_no_data_point(self.point):
            # 无数据判定补充：
            # 1. 所有检测记录均为异常点
            # 2. 异常点间时间差异符合无数据配置的周期
            start, end = anomaly_timestamps[0], anomaly_timestamps[-1]
            always_nodata = anomaly_times == len(check_results)
            is_triggered = always_nodata and ((end - start) >= (config["trigger_count"] - 1) * self.check_window_unit)

        return is_triggered, anomaly_timestamps

    def _trigger_config(self, level):
        # 旧策略可能缺少对应级别的配置，沿用第一个触发配置。
        if level in self.trigger_configs:
            return self.trigger_configs[level]
        return next(iter(self.trigger_configs.values()), None)

    def _window_key(self, level):
        return CHECK_RESULT_CACHE_KEY.get_key(
            strategy_id=self.strategy_id, item_id=self.item_id, dimensions_md5=self.dimensions_md5, level=level
        )

    def _read_window(self, client, level, config):
        offset = config["check_window_size"] * self.check_window_unit - 1
        return client.zrangebyscore(
            self._window_key(level), self.source_time - offset, self.source_time, withscores=True
        )

    @staticmethod
    def prefetch_first_windows(checkers):
        """同一策略批读每个点必查的最高优先级窗口，后续级别仅在未触发时查询。"""
        if len(checkers) < 2:
            return
        first = checkers[0]
        try:
            with routed_client(CHECK_RESULT_CACHE_KEY.client, first._window_key(first.levels[0])) as client:
                with client.pipeline(transaction=False) as pipe:
                    pending = []
                    for checker in checkers:
                        level = checker.levels[0]
                        config = checker._trigger_config(level)
                        if config is not None and checker.strategy_id == first.strategy_id:
                            checker._read_window(pipe, level, config)
                            pending.append(checker)
                    results = pipe.execute(raise_on_error=False)
        except Exception:
            # 点已出队。批读失败时让原有逐点读取和错误隔离继续处理。
            logger.exception(
                "prefetch trigger windows failed for strategy(%s), item(%s)", first.strategy_id, first.item_id
            )
            return
        for checker, result in zip(pending, results):
            if not isinstance(result, Exception):
                checker.first_window = result
