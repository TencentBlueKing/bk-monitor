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
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, List, Tuple, Type, Union

import arrow
from django.conf import settings
from django.utils.translation import gettext as _lazy

from alarm_backends.constants import STD_LOG_DT_FORMAT
from alarm_backends.core.cache import key
from alarm_backends.core.cache.key import CHECK_RESULT_CACHE_KEY
from alarm_backends.core.control.mixins.detect import load_detector_cls
from alarm_backends.core.control.mixins.double_check import DoubleCheckStrategy
from alarm_backends.core.detect_result import ANOMALY_LABEL
from alarm_backends.service.access.data.records import DataRecord
from alarm_backends.service.detect.strategy import (
    BasicAlgorithmsCollection,
    HistoryPointFetcher,
    RangeRatioAlgorithmsCollection,
)
from constants.data_source import DataSourceLabel, DataTypeLabel

if TYPE_CHECKING:
    from alarm_backends.core.control.item import Item
    from alarm_backends.service.detect import DataPoint  # noqa

logger = logging.getLogger(__name__)


def make_sure_strategy_ids_type(strategy_ids: Union[str, List[str], List[int]]) -> List[int]:
    """保证策略ID列表类型"""
    # "1,2,3,4"
    if isinstance(strategy_ids, str):
        parts = strategy_ids.split(",")
        return [int(x) for x in parts if x]

    return [int(x) for x in strategy_ids]


def get_default_strategy_ids():
    """从 settings 中获取默认的策略ID白名单"""
    return make_sure_strategy_ids_type(settings.DOUBLE_CHECK_SUM_STRATEGY_IDS)


@dataclass
class DoubleCheckSumStrategy(DoubleCheckStrategy):
    """针对Sum聚合的二次确认策略"""

    match_strategy_ids: List[int] = field(default_factory=get_default_strategy_ids)

    name = "SUM"
    DOUBLE_CHECK_CONTEXT_VALUE = "SUSPECTED_MISSING_POINTS"

    data_scopes = [
        (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.CUSTOM, DataTypeLabel.TIME_SERIES),
        (DataSourceLabel.BK_DATA, DataTypeLabel.TIME_SERIES),
    ]

    match_agg_method = "SUM"
    match_algorithms_type_sequence = ["IntelligentDetect", "AdvancedRingRatio", "SimpleRingRatio", "Threshold"]

    # 支持多个周期对比, 目前仅对比前一个周期
    default_max_history_interval_count: ClassVar[int] = 1
    # 当前周期最多可比历史周期数据量缺失比例
    default_lacking_threshold: ClassVar[float] = 0.1

    @property
    def countable_item(self) -> "Item":
        """聚合方法为 COUNT 的 Item"""
        _strategy = self.item.strategy
        _item_config_copied = deepcopy(_strategy.config["items"][0])
        _item_config_copied["query_configs"][0]["agg_method"] = "COUNT"
        _item = self.item.__class__(_item_config_copied, _strategy)
        return _item

    @property
    def agg_interval(self) -> int:
        return self.item.query_configs[0]["agg_interval"]

    @property
    def type_algorithm_map(self) -> dict:
        return {x["type"]: x for x in self.item.algorithms}

    def check_extra(self) -> bool:
        # 仅关注单一指标的情况
        if len(self.item.query_configs) != 1:
            return False

        return True

    def get_offsets_by_algorithm(self, algorithm_type: str) -> Union[List[int], List[Tuple[int, int]]]:
        """通过检测算法来获取时间偏移量"""
        detector_cls = load_detector_cls(algorithm_type)
        if not issubclass(detector_cls, HistoryPointFetcher):
            logger.debug(
                "[二次确认] strategy(%s),item(%s) 当前检测算法 %s 没有历史数据拉取能力",
                self.item.strategy.id,
                self.item.id,
                detector_cls.__name__,
            )
            return [(i + 1) * self.agg_interval for i in range(self.default_max_history_interval_count)]

        detector_cls: Union[Type[HistoryPointFetcher], Type[BasicAlgorithmsCollection]]
        detector = detector_cls(self.type_algorithm_map.get(algorithm_type).get("config", {}), self.item.unit)
        logger.debug(
            "[二次确认] strategy(%s),item(%s) detector.get_history_offsets(self.item): %s",
            self.item.strategy.id,
            self.item.id,
            detector.get_history_offsets(self.item),
        )
        return detector.get_history_offsets(self.item)

    def double_check(self, outputs: List[dict]):
        """针对 SUM 聚合进行二次确认
        outputs 列表内单个数据示例：
            {'data': {'__debug__': True,
              'time': 1664530800,
              'value': 20000,
              'values': {'online': 0, '_result_': 20000, 'time': 1664530800},
              'dimensions': {'location': 'guangdong'},
              'record_id': '9a6cc8c6fff25fed722e2eb7f2ba0a00.1664530800',
              'access_time': 1664594538},
             'anomaly': {'1': {'anomaly_message': 'SUM(online)较前一时刻(60000)下降超过20.0%, 当前值20000',
               'anomaly_id': '9a6cc8c6fff25fed722e2eb7f2ba0a00.1664530800.62921.65596.1',
               'anomaly_time': '2022-10-01 03:22:18'}},
             'strategy_snapshot_key': 'bkmonitorv3.ieod.cache.strategy.snapshot.62921.1664530522'}
        """
        # outputs 数据点是逆序的, 这里需要做个排序
        anomaly_points = sorted(outputs, key=lambda p: p["data"]["time"])
        # 0. 按异常点先设定数据点计算时间范围（后续根据二次确认规则还会调整）
        # 数据查询时间范围 [from_timestamp, until_timestamp), 因此data_end_time 补一个周期
        data_start_time, data_end_time = (
            anomaly_points[0]["data"]["time"],
            anomaly_points[-1]["data"]["time"] + self.agg_interval,
        )

        # 1. 根据异常判定策略定义的周期偏移, 基于数据点时间范围, 计算需要检测的时间范围
        alert_level = list(anomaly_points[0]["anomaly"].keys())[0]
        algorithm_type = self.get_algorithm_type_by_level(alert_level)
        lacking_threshold = self.get_threshold(algorithm_type)

        from_timestamp, until_timestamp = data_start_time, data_end_time
        # 策略定义的偏移量
        offset_list = self.get_offsets_by_algorithm(algorithm_type)
        logger.info(
            "[二次检测] strategy({}),item({}) 策略定义的时间偏移量: {}".format(self.item.strategy.id, self.item.id, offset_list)
        )
        for offset in offset_list:
            if isinstance(offset, tuple):
                _, _max = offset
            else:
                _max = offset

            if from_timestamp > data_start_time - _max:
                logger.debug(
                    "[二次检测] strategy({}),item({}) from_timestamp changed: {}-> {}".format(
                        self.item.strategy.id, self.item.id, from_timestamp, data_start_time - _max
                    )
                )
                from_timestamp = data_start_time - _max
                # until_timestamp 基于历史数据的查询, 不会有负数offset, 因此 until_timestamp 就可以肯定一定是最新异常点的时间

        logger.debug(f"[二次检测]: 将拉取历史周期数据： {from_timestamp}->{until_timestamp}")
        if (until_timestamp - from_timestamp) // self.agg_interval > 30:
            # 限定最多查30个周期的数据(拍脑袋)
            logger.warning(
                f"[skip][二次检测] strategy({self.item.strategy.id}),item({self.item.id}) 策略偏移量过大, 超过最近30个周期, 二次确认跳过"
            )

        # 2. 查出数据点数（时间范围包含了异常点时刻+检测算法偏移时刻的全部点）
        counter_data = self.countable_item.query_record(start_time=from_timestamp, end_time=until_timestamp)
        counter_points = [DataRecord(self.item, raw_data) for raw_data in counter_data]
        # 维度md5 + str(时间戳) 作为索引key
        counter_point_map = {point.record_id: point.value for point in counter_points}
        # 原始检测数据: 在发现数据点未变化时, 发起查询.
        origin_points = None
        origin_point_map = {}
        # 3. 逐个异常点进行数据质量确认
        marked_total = 0
        for anomaly_point in anomaly_points:
            interval_list = []
            former_points = []
            now_point_record_id = anomaly_point["data"]["record_id"]
            dimension_md5, point_timestamp = now_point_record_id.split(".")
            now_points = [counter_point_map.get(now_point_record_id)]
            if not any(now_points):
                logger.info(f"counter_point_map: {counter_point_map}")
                logger.info(
                    f"[skip] [二次检测] strategy({self.item.strategy.id}),item({self.item.id}) "
                    f"异常点{anomaly_point}对应的数据量级未查询到, 跳过该异常点检测."
                )
                continue

            former_points_length_times = 0
            for offset_or_tuple in offset_list:
                if isinstance(offset_or_tuple, tuple):
                    start, end = offset_or_tuple
                else:
                    start = end = offset_or_tuple
                # 根据偏移量获取历史点
                for offset in range(start, end + self.agg_interval, self.agg_interval):
                    interval_list.append(offset // self.agg_interval)
                    target_timestamp = int(point_timestamp) - offset
                    target_point = counter_point_map.get(f"{dimension_md5}.{target_timestamp}")
                    former_points_length_times += 1
                    if target_point is not None:
                        former_points.append(target_point)

            logger.info(
                f"[二次检测] strategy({self.item.strategy.id}),item({self.item.id}) "
                f"策略项<{self.item.name}> 正在对比与 {interval_list} 个周期前的数据量: "
                f"当前周期({arrow.get(anomaly_point['data']['time']).strftime(STD_LOG_DT_FORMAT)}), "
                f"历史周期点数: <{former_points_length_times}>",
            )
            if not self.check_points_missing(now_points, former_points, former_points_length_times, lacking_threshold):
                logger.info(
                    "[二次检测] strategy(%s),item(%s) 与前%s周期对比不存在数据缺失, " "重新获取数据以确认异常数值是否变化",
                    self.item.strategy.id,
                    self.item.id,
                    interval_list,
                )
                # 二次检测发现数据量未缺失, 判定数据值是否改变, 如果改变则需要重新检测(重新推送detect队列)
                if origin_points is None:
                    origin_data = self.item.query_record(start_time=data_start_time, end_time=data_end_time)
                    origin_points = [DataRecord(self.item, raw_data).clean() for raw_data in origin_data]
                    origin_point_map = {point.record_id: point.value for point in origin_points}

                record_id = anomaly_point["data"]["record_id"]
                if record_id in origin_point_map and anomaly_point["data"]["value"] != origin_point_map[record_id]:
                    # 数据未缺失, 但数据结果变化,重新推送
                    logger.info(
                        "[二次检测] strategy(%s),item(%s) 检测数据值发生变化%s -> %s, 中断二次确认, 清空本轮检测异常点, 重新推送detect待检测队列",
                        self.item.strategy.id,
                        self.item.id,
                        anomaly_point["data"]["value"],
                        origin_point_map[record_id],
                    )
                    # 数值变更, 则二次确认中断, 重新推送最新数据重新检测
                    outputs.clear()
                    # 清理所有异常检测记录
                    for ap in anomaly_points:
                        now_point_record_id = ap["data"]["record_id"]
                        _dimension_md5, _point_timestamp = now_point_record_id.split(".")
                        check_cache_key = CHECK_RESULT_CACHE_KEY.get_key(
                            strategy_id=self.item.strategy.id,
                            item_id=self.item.id,
                            dimensions_md5=_dimension_md5,
                            alert=alert_level,
                        )
                        CHECK_RESULT_CACHE_KEY.client.zrem(
                            check_cache_key, "{}|{}".format(_point_timestamp, ANOMALY_LABEL)
                        )
                    if "__debug__" in anomaly_point["data"]:
                        for point in origin_points:
                            logger.info(f"[二次检测] new point: {point.__dict__}")
                            point.data.update({"__debug__": True})
                    return self.push_to_detect(origin_points)

                else:
                    logger.info(
                        "[二次检测] strategy(%s),item(%s) 检测数据值未发生变化%s -> %s",
                        self.item.strategy.id,
                        self.item.id,
                        anomaly_point["data"]["value"],
                        origin_point_map[record_id],
                    )

                continue
            marked_total += 1
            logger.info(
                f"[二次检测] strategy({self.item.strategy.id}),item({self.item.id}) " f"在前 {interval_list} 周期发现存在数据缺失"
            )
            context = anomaly_point.get("context", {})
            context.update({self.DOUBLE_CHECK_CONTEXT_KEY: self.DOUBLE_CHECK_CONTEXT_VALUE})
            anomaly_point["context"] = context
            for _, anomaly_info in anomaly_point["anomaly"].items():
                anomaly_info["anomaly_message"] += _lazy(" --- 经过二次确认后, 判定为疑似异常, 原因：对比 {} 秒前, 异常发生时存在数据缺失").format(
                    [i * self.agg_interval for i in interval_list]
                )

                logger.info(
                    "[二次检测] strategy({}),item({}) ({}): anomaly_message changed: {}".format(
                        self.item.strategy.id, self.item.id, anomaly_info['anomaly_id'], anomaly_info['anomaly_message']
                    )
                )

        if marked_total > 0:
            logger.info(
                "[success][二次检测] strategy(%s),item(%s) 当前存在 %s 个异常点疑似数据点缺失, 已增加特殊标记<%s>",
                self.item.strategy.id,
                self.item.id,
                marked_total,
                self.DOUBLE_CHECK_CONTEXT_KEY,
            )

    def check_points_missing(
        self,
        now_data_points: List[int],
        former_points: List[int],
        former_points_length_times: int,
        lacking_threshold: float,
    ) -> bool:
        """对比当前周期和历史周期的数据量"""
        now_data_count = sum(now_data_points)
        # 以历史周期长度取均值
        former_count = sum(former_points) / former_points_length_times
        logger.info(
            "[二次检测] strategy(%s),item(%s) 当前数据量 [%s] vs 历史数据量 [%s]",
            self.item.strategy.id,
            self.item.id,
            now_data_count,
            former_count,
        )

        # 当当前周期数据量比历史周期数据量大, 直接判断为无缺失
        if now_data_count >= former_count:
            return False

        # 当历史周期数据量为零, 直接判断为无缺失
        if former_count <= 0:
            return False

        count_ratio = (former_count - now_data_count) / former_count
        logger.debug(f"[二次检测] 数据量差异比较： {count_ratio} vs {lacking_threshold}")
        return count_ratio >= lacking_threshold

    def get_threshold(self, algorithm_type: str) -> float:
        """通过算法获取数据缺失比例阈值"""
        detector_cls = load_detector_cls(algorithm_type)
        if not issubclass(detector_cls, RangeRatioAlgorithmsCollection):
            logger.debug(
                "[二次检测] strategy(%s),item(%s) 检测算法 %s 不具备配置比例阈值的能力",
                self.item.strategy.id,
                self.item.id,
                detector_cls.__name__,
            )
            return self.default_lacking_threshold

        logger.debug(
            "[二次检测] strategy(%s),item(%s) type_algorithm_map: %s",
            self.item.strategy.id,
            self.item.id,
            self.type_algorithm_map,
        )
        detector: Union[HistoryPointFetcher, BasicAlgorithmsCollection] = detector_cls(
            self.type_algorithm_map.get(algorithm_type).get("config", {}), self.item.unit
        )
        logger.debug(
            "[二次检测] strategy(%s),item(%s) detector.config: %s", self.item.strategy.id, self.item.id, detector.config
        )
        if "floor" not in detector.config:
            return self.default_lacking_threshold

        return detector.config["floor"] / 100

    def push_to_detect(self, points):
        data_list_key = key.DATA_LIST_KEY
        point = points[0]
        output_key = data_list_key.get_key(strategy_id=self.item.strategy.strategy_id, item_id=self.item.id)
        if "__debug__" in point.data:
            logger.info(f"[二次检测] dummy push {point.data}")
        else:
            data_list_key.client.lpush(output_key, *[json.dumps(point.data) for point in points])
            key.DATA_SIGNAL_KEY.client.lpush(key.DATA_SIGNAL_KEY.get_key(), *[self.item.strategy.strategy_id])

        logger.info(
            "[二次检测] output_key({output_key}) "
            "strategy({strategy_id}), item({item_id}), "
            "push records({records_length}).".format(
                output_key=output_key,
                strategy_id=self.item.strategy.strategy_id,
                item_id=self.item.id,
                records_length=len(points),
            )
        )
