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
import time

from alarm_backends.core.cache import key
from alarm_backends.core.cache.key import (
    MD5_TO_DIMENSION_CACHE_KEY,
    OLD_MD5_TO_DIMENSION_CACHE_KEY,
)
from alarm_backends.core.control.strategy import Strategy, StrategyCacheManager
from alarm_backends.core.detect_result import CONST_MAX_LEN_CHECK_RESULT

DUMMY_DIMENSIONS_MD5 = "dummy_dimensions_md5"
CLEAN_EXPIRED_ARROW_REPLACE_TIME = {"hours": -5}

logger = logging.getLogger("core.detect_result")


class CleanResult(object):
    @staticmethod
    def clean_expired_detect_result(strategy_range=None):
        """
        清理检测结果及最近拉取结果的缓存
        """
        strategy_ids = StrategyCacheManager.get_strategy_ids()
        # 分片处理
        if strategy_range is not None:
            strategy_ids = [s_id for s_id in strategy_ids if s_id in range(*strategy_range)]

        strategies = StrategyCacheManager.get_strategy_by_ids(strategy_ids)

        client = key.LAST_CHECKPOINTS_CACHE_KEY.client
        pipeline = client.pipeline()
        total = len(strategies)
        step = int(total / 100)
        if step < 5:
            wait_signals = []
        else:
            wait_signals = list(range(step, total, step))
        last_sleep_time = time.time()
        for s_id, strategy in enumerate(strategies):
            # 按照策略的检测与恢复周期配置，决定保留多少个周期的检测结果
            point_remain = detect_result_point_required(strategy)

            for item in strategy["items"]:
                # 获取监控项下所有的维度与级别组合
                last_checkpoints_cache_key = key.LAST_CHECKPOINTS_CACHE_KEY.get_key(
                    strategy_id=strategy["id"], item_id=item["id"]
                )
                all_hkeys = client.hkeys(last_checkpoints_cache_key)
                if not all_hkeys:
                    continue

                # 计算所有的检测结果缓存key
                check_result_cache_keys = []
                for index, hkey in enumerate(all_hkeys):
                    *_, dimension_md5, level = hkey.split(".")
                    check_result_cache_keys.append(
                        key.CHECK_RESULT_CACHE_KEY.get_key(
                            strategy_id=strategy["id"], item_id=item["id"], dimensions_md5=dimension_md5, level=level
                        )
                    )

                # 按保留点数清理检测结果缓存
                for index, check_result_cache_key in enumerate(check_result_cache_keys):
                    pipeline.zremrangebyrank(check_result_cache_key, 0, -point_remain)
                    # 一次最多清理5000个维度的检测结果
                    if index % 5000 == 4999:
                        pipeline.execute()
                pipeline.execute()

                # 批量获取检测结果缓存是否被清理
                check_result_lengths = []
                for index, check_result_cache_key in enumerate(check_result_cache_keys):
                    pipeline.zcard(check_result_cache_key)
                    if index % 5000 == 4999:
                        check_result_lengths.extend(pipeline.execute())
                check_result_lengths.extend(pipeline.execute())

                # 如果检测结果缓存被清理，同步清理last checkpoint
                index = 0
                for check_result_cache_key, check_result_length in zip(check_result_cache_keys, check_result_lengths):
                    if check_result_length > 0:
                        continue
                    *_, dimension_md5, level = check_result_cache_key.split(".")
                    last_checkpoints_cache_field = key.LAST_CHECKPOINTS_CACHE_KEY.get_field(
                        dimensions_md5=dimension_md5, level=level
                    )
                    pipeline.hdel(last_checkpoints_cache_key, last_checkpoints_cache_field)
                    if index % 5000 == 4999:
                        pipeline.execute()
                    index += 1
                pipeline.execute()

            # redis 性能缓冲, 避免清理任务占满redis cpu
            if s_id in wait_signals:
                now = time.time()
                clean_duration = now - last_sleep_time
                if clean_duration > 1:
                    time.sleep(clean_duration)
                    last_sleep_time = now

    @staticmethod
    def clean_md5_to_dimension_cache():
        """
        清理无数据历史维度
        """
        # 清理旧的历史维度字段
        MD5_TO_DIMENSION_CACHE_KEY.client.delete(OLD_MD5_TO_DIMENSION_CACHE_KEY.get_key())

        strategy_ids = StrategyCacheManager.get_strategy_ids()
        strategies = StrategyCacheManager.get_strategy_by_ids(strategy_ids)

        pipeline = MD5_TO_DIMENSION_CACHE_KEY.client.pipeline()
        index = 0
        for strategy in strategies:
            for item in strategy["items"]:
                # 如果没有配置无数据告警，则不处理
                no_data_config = item.get("no_data_config", {})
                if not no_data_config.get("is_enabled", False):
                    continue

                md5_key = MD5_TO_DIMENSION_CACHE_KEY.get_key(
                    service_type="nodata", strategy_id=strategy["id"], item_id=item["id"]
                )
                pipeline.delete(md5_key)
                index += 1

                # 一次最多清理5000个维度的检测结果
                if index % 5000 == 4999:
                    pipeline.execute()
        pipeline.execute()


def detect_result_point_required(strategy) -> int:
    """
    检测结果需要保留多少个检测结果点
    """
    # 计算恢复窗口时间偏移量
    recovery_configs = Strategy.get_recovery_configs(strategy)
    trigger_configs = Strategy.get_trigger_configs(strategy)

    point_remind = CONST_MAX_LEN_CHECK_RESULT
    for level in trigger_configs:
        trigger_window_size = trigger_configs[level].get("check_window_size", 5)
        recovery_window_size = recovery_configs[level].get("check_window_size", 5)
        point_remind = max([point_remind, (trigger_window_size + recovery_window_size) * 2])
    return point_remind
