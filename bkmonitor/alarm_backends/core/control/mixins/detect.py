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
from collections import OrderedDict, defaultdict
from typing import TYPE_CHECKING

from django.utils.module_loading import import_string
from django.utils.translation import gettext as _

from alarm_backends.constants import LATEST_POINT_WITH_ALL_KEY
from alarm_backends.core.cache.key import LAST_CHECKPOINTS_CACHE_KEY
from alarm_backends.core.detect_result import ANOMALY_LABEL, CheckResult
from bkmonitor.utils.common_utils import chunks
from bkmonitor.utils.text import camel_to_underscore
from constants.data_source import DataTypeLabel

logger = logging.getLogger("core.control")

# 算法额外控制参数白名单
# 这些参数会从算法配置中提取并传递给算法实例
# 用于控制算法行为（如灰度开关、服务名称等）
EXTRA_CONFIG_KEYS = [
    "grey_to_bkfara",  # 灰度开关：是否使用新的 BKFara 服务
    "service_name",  # 服务名称：用于指定特定服务
    # 后续可在此添加更多控制参数
]

if TYPE_CHECKING:
    from alarm_backends.service.detect.strategy import BasicAlgorithmsCollection  # noqa


def load_detector_cls(_type) -> type["BasicAlgorithmsCollection"]:
    algorithms_target = camel_to_underscore(_type)
    package_name = "alarm_backends.service.detect"
    cls_target = f"{package_name}.strategy.{algorithms_target}.{_type}"
    try:
        cls = import_string(cls_target)
    except ImportError:
        logger.error(f"detector load error: {cls_target}")
        cls = None
    return cls


class DetectMixin:
    def detect(self, data_points):
        if not data_points:
            return []

        algorithm_group = defaultdict(list)
        for _config in self.algorithms:
            level = int(_config["level"])
            algorithm_group[level].append(_config)

        levels = sorted(algorithm_group.keys())

        # 初始化检测结果
        detected_result_dict = OrderedDict()

        for level in levels:
            # 同级别算法连接符(and/or)
            algorithm_connector = self.algorithm_connectors[level]

            detector_list = []
            for detect_config in algorithm_group[level]:
                algorithm_type = detect_config["type"]
                algorithm_unit = detect_config.get("unit_prefix", "")
                algorithm_config = detect_config.get("config", {})
                detector_cls = load_detector_cls(algorithm_type)

                # 使用白名单方式提取控制参数
                # 只提取 EXTRA_CONFIG_KEYS 中定义的参数
                extra_config = {k: algorithm_config[k] for k in EXTRA_CONFIG_KEYS if k in algorithm_config}

                detector = detector_cls(algorithm_config, algorithm_unit, extra_config=extra_config)

                # 判断算法是否需要查询历史数据
                if hasattr(detector, "history_point_fetcher"):
                    detector.query_history_points(data_points)

                    # 如果是事件类数据，历史数据需要补充0值
                    if {DataTypeLabel.LOG, DataTypeLabel.EVENT} & self.data_type_labels:
                        detector.set_default(0)

                # 判断是否需要对使用SDK异常检测的策略进行分组预检测
                if hasattr(detector, "pre_detect"):
                    detector.pre_detect(data_points)

                detector_list.append(detector)

            if len(detector_list) == 1:
                anomaly_records = detector_list[0].detect_records(data_points, level)
            else:
                # 组合策略
                anomaly_records = []
                for data_point in data_points:
                    ap = None
                    prefix = suffix = ""
                    for d in detector_list:
                        try:
                            single_ret = d.detect(data_point)

                            # != "or" 兼容connector未配置或配错的情况，默认都使用and
                            if not single_ret:
                                if algorithm_connector != "or":
                                    ap = None
                                    break
                                else:
                                    continue

                            single_ap = d.gen_anomaly_point(data_point, single_ret, level, auto_format=False)
                            if not prefix:
                                prefix, suffix = d.anomaly_message_template_tuple(data_point)
                                # print(prefix, suffix)
                            if ap:
                                ap.anomaly_message += _(" 同时 ") + single_ap.anomaly_message
                            else:
                                ap = single_ap

                            # 如果算法为or，则只需要一个算法匹配即可立即退出
                            if algorithm_connector == "or":
                                break
                        except Exception:
                            if algorithm_connector != "or":
                                ap = None
                                break

                    if ap:
                        ap.anomaly_message = prefix + ap.anomaly_message + suffix
                        logger.info(
                            f"[detect] strategy({ap.data_point.item.strategy.id}) item({ap.data_point.item.id}) level[{level}] 发现异常点: {ap.__dict__}"
                        )
                        anomaly_records.append(ap)

            self._update_monitor_d_checkpoint(data_points, anomaly_records, level)

            for ar in anomaly_records:
                collection = detected_result_dict.setdefault(ar.data_point.record_id, {})
                collection.update(self._update_anomaly_info_with_point(ar, level, collection))

        return list(detected_result_dict.values())

    def _update_anomaly_info_with_point(self, anomaly_point, level, info_collection=None):
        info_collection = info_collection or {
            "data": anomaly_point.data_point.as_dict(),
            "anomaly": {},
            "strategy_snapshot_key": self.strategy.snapshot_key,
        }
        anomaly_info = {
            "anomaly_message": anomaly_point.anomaly_message,
            "anomaly_id": anomaly_point.anomaly_id,
            "anomaly_time": anomaly_point.anomaly_time,
        }

        if anomaly_point.context:
            anomaly_info["context"] = anomaly_point.context

        info_collection["anomaly"].update({str(level): anomaly_info})
        return info_collection

    def _update_monitor_d_checkpoint(self, records, anomaly_records, level):
        redis_pipeline = None
        last_checkpoints = {}
        anomaly_record_ids = {i.data_point.record_id for i in anomaly_records}
        latest_point_with_all = 0
        try:
            strategy_ttl = self.get_detect_result_expire_ttl()
        except Exception:
            strategy_ttl = None
        for d in records:
            # data_record 的record_id规则： {dimensions_md5}.{timestamp}
            dimensions_md5, timestamp = d.record_id.split(".")
            timestamp = int(timestamp)
            latest_point_with_all = max([latest_point_with_all, d.timestamp])

            check_result = CheckResult(self.strategy.id, self.id, dimensions_md5, level)
            if redis_pipeline is None:
                redis_pipeline = check_result.CHECK_RESULT

            if d.record_id in anomaly_record_ids:
                name = f"{timestamp}|{ANOMALY_LABEL}"
            else:
                name = f"{timestamp}|{str(d.value)}"

            try:
                # 1. 缓存数据(检测结果缓存) type:SortedSet
                kwargs = {name: timestamp}
                check_result.add_check_result_cache(ttl=strategy_ttl, **kwargs)

                # 2. 缓存最后checkpoint type:Hash，先放到内存里，最后再一次性写入redis
                last_point = last_checkpoints.setdefault(dimensions_md5, 0)
                if last_point < timestamp:
                    last_checkpoints[dimensions_md5] = timestamp

            except Exception as e:
                msg = f"set check result cache error:{e}"
                logger.exception(msg)

        if redis_pipeline:
            check_result.expire_key_to_dimension()
            redis_pipeline.execute()

        if latest_point_with_all:
            last_checkpoints[LATEST_POINT_WITH_ALL_KEY] = latest_point_with_all

        # 更新last_checkpoint
        last_checkpoint_cache_key = LAST_CHECKPOINTS_CACHE_KEY.get_key(strategy_id=self.strategy.id, item_id=self.id)

        for chunked_points in chunks(list(last_checkpoints.items()), 5000):
            set_mapping = {}
            for _dimensions_md5, point_timestamp in chunked_points:
                last_checkpoint_cache_field = LAST_CHECKPOINTS_CACHE_KEY.get_field(
                    dimensions_md5=_dimensions_md5,
                    level=level,
                )
                set_mapping[last_checkpoint_cache_field] = point_timestamp
            LAST_CHECKPOINTS_CACHE_KEY.client.hmset(last_checkpoint_cache_key, set_mapping)
        CheckResult.expire_last_checkpoint_cache(strategy_id=self.strategy.id, item_id=self.id)
