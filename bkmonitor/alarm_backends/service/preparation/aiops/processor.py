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
import json
import logging
import time
from typing import Dict

from pika.adapters.blocking_connection import BlockingChannel
from pika.spec import Basic

from alarm_backends.core.control.item import Item
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.core.storage.rabbitmq import RabbitMQClient
from alarm_backends.service.preparation.base import BasePreparationProcess
from bkmonitor.models import AlgorithmModel
from bkmonitor.utils.time_tools import parse_time_compare_abbreviation
from constants.strategy import StrategySyncType
from core.drf_resource import api

logger = logging.getLogger("preparation.aiops")


INIT_DEPEND_MAPPINGS = {
    AlgorithmModel.AlgorithmChoices.TimeSeriesForecasting: api.aiops_sdk.tf_init_depend,
    AlgorithmModel.AlgorithmChoices.IntelligentDetect: api.aiops_sdk.kpi_init_depend,
}


class TsDependPreparationProcess(BasePreparationProcess):
    def __init__(self, *args, **kwargs) -> None:
        super(TsDependPreparationProcess, self).__init__()

    def process(self) -> None:
        pass

    def init_strategy_depend_data(self, strategy: Strategy) -> None:
        """根据同步信息，从Cache中获取策略的配置，并调用SDK初始化历史依赖数据.

        :param strategy: 策略
        """
        logger.info("Start to init depend data for intelligent strategy({})".format(strategy.id))
        item: Item = strategy.items[0]

        if item.algorithms:
            algorithm_type = item.algorithms[0]["type"]
            init_depend_api_func = INIT_DEPEND_MAPPINGS.get(algorithm_type)
            if not init_depend_api_func:
                logger.warning("Not supported init depend data for '{}' type algorithm".format(algorithm_type))
                return

            ts_depend = item.algorithms[0].get("ts_depend", "2d")
            ts_depend_offset = parse_time_compare_abbreviation(ts_depend)
            end_time = int(time.time())
            start_time = end_time + ts_depend_offset
            item_records = item.query_record(start_time, end_time)

            depend_data_by_dimensions = {}
            for item_record in item_records:
                dimensions_key = tuple(item_record[dim] for dim in item.query_configs[0]["agg_dimension"])
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

            for series_info in depend_data_by_dimensions.values():
                series_info["dimensions"]["strategy_id"] = strategy.id

                init_depend_api_func(
                    dependency_data=[
                        {
                            "data": series_info["data"],
                            "dimensions": series_info["dimensions"],
                        }
                    ]
                )

    def update_strategy_depend_data(self, strategy: Strategy) -> None:
        """根据同步信息，从Cache中获取策略的配置，并调用SDK更新历史依赖数据.

        :param strategy: 策略
        """
        # 目前更新逻辑跟初始化逻辑一致
        self.init_strategy_depend_data(strategy)


class TsDependEventPreparationProcess(TsDependPreparationProcess):
    def __init__(self, broker_url: str, queue_name: str) -> None:
        super(TsDependEventPreparationProcess, self).__init__()

        self.broker_url = broker_url
        self.queue_name = queue_name
        self.client = RabbitMQClient(broker_url=broker_url)
        self.client.ping()

    def process(self) -> None:
        def callback(ch: BlockingChannel, method: Basic.Deliver, properties: Dict, body: str):
            sync_info = json.loads(body)
            self.handle_sync_info(sync_info)
            ch.basic_ack(method.delivery_tag)

        self.client.start_consuming(self.queue_name, callback=callback)

    def handle_sync_info(self, sync_info: Dict) -> None:
        """处理rabbitmq中的内容.

        :param sync_info: 同步内容
        """
        strategy = Strategy(sync_info["strategy_id"])
        if sync_info["sync_type"] == StrategySyncType.CREATE.value:
            self.init_strategy_depend_data(strategy)
        elif sync_info["sync_type"] == StrategySyncType.UPDATE.value:
            self.update_strategy_depend_data(strategy)
