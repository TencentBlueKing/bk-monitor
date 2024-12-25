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
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Set, Tuple

from django.conf import settings

from alarm_backends.core.cache import key
from alarm_backends.core.control.item import Item
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.core.lock.service_lock import (
    check_lock_updated,
    refresh_service_lock,
)
from alarm_backends.service.preparation.base import BasePreparationProcess
from bkmonitor.models import AlgorithmModel
from bkmonitor.models.strategy import QueryConfigModel
from bkmonitor.strategy.new_strategy import QueryConfig
from bkmonitor.utils.time_tools import (
    parse_time_compare_abbreviation,
    timestamp2datetime,
)
from constants.aiops import (
    DEPEND_DATA_MAX_FETCH_COUNT,
    DEPEND_DATA_MAX_FETCH_TIME_RANGE,
    DEPEND_DATA_MIN_FETCH_TIME_RANGE,
    SDKDetectStatus,
)
from core.drf_resource import api

logger = logging.getLogger("preparation.aiops")


INIT_DEPEND_MAPPINGS = {
    AlgorithmModel.AlgorithmChoices.TimeSeriesForecasting: api.aiops_sdk.tf_init_depend,
    AlgorithmModel.AlgorithmChoices.IntelligentDetect: api.aiops_sdk.kpi_init_depend,
}


class TsDependPreparationProcess(BasePreparationProcess):
    def __init__(self, *args, **kwargs) -> None:
        super(TsDependPreparationProcess, self).__init__()
        self.prepare_key = key.SERVICE_LOCK_PREPARATION

    def process(self, strategy_id: int, update_time: int = None, force: bool = False) -> None:
        logger.info(f"Start to refresh depend data for strategy({strategy_id})")

        processed_dimensions = set()
        with refresh_service_lock(self.prepare_key, update_time, strategy_id=strategy_id):
            strategy = Strategy(strategy_id)
            query_config = strategy.config["items"][0]["query_configs"][0]
            # 只有使用SDK进行检测的智能监控策略才进行历史依赖数据的初始化
            if query_config.get("intelligent_detect") and query_config["intelligent_detect"].get("use_sdk", False):
                # 历史依赖准备就绪才开始检测
                if force or query_config["intelligent_detect"]["status"] == SDKDetectStatus.PREPARING:
                    self.refresh_strategy_depend_data(strategy, processed_dimensions, update_time)
                    query_config = QueryConfig.from_models(QueryConfigModel.objects.filter(id=query_config["id"]))[0]
                    query_config.intelligent_detect["status"] = SDKDetectStatus.READY
                    query_config.save()
                    logger.info(
                        f"Finish to refresh depend data for strategy({strategy_id}),"
                        f"total dimensions: {len(processed_dimensions)}"
                    )

    def refresh_strategy_depend_data(
        self, strategy: Strategy, processed_dimensions: Set, update_time: int = None
    ) -> None:
        """根据同步信息，从Cache中获取策略的配置，并调用SDK初始化历史依赖数据.

        :param strategy: 策略
        """
        logger.info("Start to init depend data for intelligent strategy({})".format(strategy.id))
        item: Item = strategy.items[0]

        for algorithm in item.algorithms:
            algorithm_type = algorithm["type"]
            if algorithm_type not in AlgorithmModel.AIOPS_ALGORITHMS:
                continue

            init_depend_api_func = INIT_DEPEND_MAPPINGS.get(algorithm_type)
            if not init_depend_api_func:
                logger.warning("Not supported init depend data for '{}' type algorithm".format(algorithm_type))
                continue

            start_time, end_time = self.generate_depend_time_range(item)

            self.init_depend_data(
                strategy, init_depend_api_func, start_time, end_time, processed_dimensions, update_time
            )

            # 如果初始化完历史依赖后发现当前时间过长，则再添补刷新过程中的时间范围（如果超过12小时）
            latest_end_time = int(time.time())
            if latest_end_time - end_time >= 86400:
                raise Exception(f"Init strategy({strategy.id}) depend data too long")
            if latest_end_time - end_time >= 3600:
                self.init_depend_data(
                    strategy, init_depend_api_func, latest_end_time, end_time, processed_dimensions, update_time
                )

    def generate_depend_time_range(self, item: Item) -> Tuple[int, int]:
        """根据配置生成历史依赖的开始时间和结束时间."""
        ts_depend = item.algorithms[0].get("ts_depend", "2d")
        ts_depend_offset = parse_time_compare_abbreviation(ts_depend)
        end_time = int(time.time())
        start_time = end_time + ts_depend_offset
        return start_time, end_time

    def init_depend_data(
        self,
        strategy: Strategy,
        init_depend_api_func: callable,
        start_time: int,
        end_time: int,
        processed_dimensions: Set,
        update_time: int = None,
    ) -> None:
        item: Item = strategy.items[0]

        # 先查询5min估算大概数据量
        minute_step = 5
        step_end_time = end_time

        # 直到当前取数据的末尾时间超过实际时间，一直按照上一次数据量调整每次取数据的时间范围，根据上一次取数据的量
        # 1. 每次至少取5分钟的数据(DEPEND_DATA_MIN_FETCH_TIME_RANGE)
        # 2. 每次最多取30分钟的数据(DEPEND_DATA_MAX_FETCH_TIME_RANGE)
        # 3. 尽量保证每次取的数据不超过100万(DEPEND_DATA_MAX_FETCH_COUNT)，如果5分钟数据超过100万，则继续取5分钟的，
        #    （一般很少这种情况，如果出现，则该策略至少是一个超大维度组合的数据，这么配置告警策略其实也没法用）
        while start_time < step_end_time:
            # 如果历史依赖数据准备超过prepare key的ttl（默认一小时），也中断初始化任务
            if check_lock_updated(self.prepare_key, update_time, strategy_id=strategy.id):
                logger.warning("New event for update strategy({strategy.id}), interrupt current task now.")
                break

            step_start_time = max(step_end_time - minute_step * 60, start_time)
            logger.info(
                "Start to init depend data for intelligent strategy({}) with time range({} - {})".format(
                    strategy.id, timestamp2datetime(step_start_time), timestamp2datetime(step_end_time)
                )
            )

            item_records = item.query_record(step_start_time, step_end_time)
            step_end_time = step_start_time
            if len(item_records) == 0:
                minute_step = DEPEND_DATA_MAX_FETCH_TIME_RANGE
                continue

            self.init_depend_data_by_records(strategy, init_depend_api_func, item_records, processed_dimensions)

            # 根据实际数据量调整每次查询的时间范围
            minute_step = max(
                DEPEND_DATA_MIN_FETCH_TIME_RANGE, int(DEPEND_DATA_MAX_FETCH_COUNT / (len(item_records) / minute_step))
            )
            minute_step = min(minute_step, DEPEND_DATA_MAX_FETCH_TIME_RANGE)

    def init_depend_data_by_records(
        self,
        strategy: Strategy,
        init_depend_api_func: callable,
        strategy_records: List[Dict],
        processed_dimensions: Set,
    ) -> None:
        item: Item = strategy.items[0]

        depend_data_by_dimensions = {}
        for item_record in strategy_records:
            try:
                dimensions_key = tuple(item_record[dim] for dim in item.query_configs[0]["agg_dimension"])
            except KeyError:
                # 如果缺少维度，则认为数据无效，跳过
                continue
            if dimensions_key not in depend_data_by_dimensions:
                dimensions = {dim: item_record[dim] for dim in item.query_configs[0]["agg_dimension"]}
                depend_data_by_dimensions[dimensions_key] = {
                    "dimensions": dimensions,
                    "data": [],
                }
            depend_data_by_dimensions[dimensions_key]["data"].append(
                {
                    "timestamp": item_record["_time_"] * 1000,
                    "value": item_record["_result_"],
                }
            )

        replace_data = []
        append_data = []
        for dimensions_key, series_info in depend_data_by_dimensions.items():
            series_info["dimensions"]["strategy_id"] = strategy.id

            if dimensions_key not in processed_dimensions:
                replace_data.append(
                    {
                        "data": series_info["data"],
                        "dimensions": series_info["dimensions"],
                    }
                )
            else:
                append_data.append(
                    {
                        "data": series_info["data"],
                        "dimensions": series_info["dimensions"],
                    }
                )

            processed_dimensions.add(dimensions_key)

        tasks = []
        with ThreadPoolExecutor(max_workers=settings.AIOPS_SDK_INIT_CONCURRENCY) as executor:
            # 第一次刷新某个维度的时候使用覆盖式刷新，后面时间段刷新时在进行增量刷新
            if replace_data:
                executor.submit(init_depend_api_func, replace=True, dependency_data=replace_data)

            if append_data:
                executor.submit(init_depend_api_func, replace=False, dependency_data=append_data)

        as_completed(tasks)
