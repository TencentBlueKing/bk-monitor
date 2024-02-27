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
import copy
import json
import time as time_mod
from typing import Dict, List

from django.conf import settings
from django.utils.translation import gettext as _

from alarm_backends.core.cluster import get_cluster
from alarm_backends.core.control.mixins.double_check import DoubleCheckStrategy
from alarm_backends.core.control.record_parser import EventIDParser
from alarm_backends.core.storage.kafka import KafkaQueue
from bkmonitor.models import NO_DATA_TAG_DIMENSION
from constants.alert import EventStatus, EventTargetType
from constants.data_source import DataSourceLabel, DataTypeLabel


class MonitorEventAdapter:
    """
    监控老版本事件适配器
    """

    SPECIAL_ALERT_TAG_KEY_WHITELIST = [DoubleCheckStrategy.DOUBLE_CHECK_CONTEXT_KEY]

    @classmethod
    def push_to_kafka(cls, events: List[Dict]):
        """
        将事件推送到 Kafka，提供给故障自愈进行消费
        :param events: 从 Adapter 解析出来的事件对象
        """
        if not settings.PUSH_MONITOR_EVENT_TO_FTA:
            # 如果设置被禁用，则不推送
            return
        if not events:
            return
        messages = [json.dumps(event).encode("utf-8") for event in events]
        # 默认集群使用默认topic，其他集群使用集群名作为topic后缀
        if get_cluster().is_default():
            topic = settings.MONITOR_EVENT_KAFKA_TOPIC
        else:
            topic = f"{settings.MONITOR_EVENT_KAFKA_TOPIC}_{get_cluster().name}"
        # 使用专用kafka集群: ALERT_KAFKA_HOST  ALERT_KAFKA_PORT
        kafka_queue = KafkaQueue.get_alert_kafka_queue()
        kafka_queue.set_topic(topic)
        return kafka_queue.put(value=messages)

    def __init__(self, record: dict, strategy: dict):
        """
        :param record:
        example
        {
            "data": {
                "record_id": "55a76cf628e46c04a052f4e19bdb9dbf.1569246480",
                "value": 1.38,
                "values": {"timestamp": 1569246480, "load5": 1.38},
                "dimensions": {"ip": "127.0.0.1", "bk_cloud_id": "0"},
                "time": 1569246480,
            },
            "anomaly": {
                "1": {
                    "anomaly_message": "异常测试",
                    "anomaly_id": "55a76cf628e46c04a052f4e19bdb9dbf.1569246480.1111.11111.111111",
                    "anomaly_time": "2019-10-10 10:10:00",
                },
                "2": {
                    "anomaly_message": "异常测试",
                    "anomaly_id": "55a76cf628e46c04a052f4e19bdb9dbf.1569246480.11111.11111.111112",
                    "anomaly_time": "2019-10-10 10:10:00",
                },
                "3": {
                    "anomaly_message": "异常测试",
                    "anomaly_id": "55a76cf628e46c04a052f4e19bdb9dbf.1569246480.111111.1111.1113",
                    "anomaly_time": "2019-10-10 10:10:00",
                },
            },
            "strategy_snapshot_key": "xxx",
            "trigger": {
                "level": "2",
                "anomaly_ids": [
                    "55a76cf628e46c04a052f4e19bdb9dbf.1569246240.1111.1111.1112",
                    "55a76cf628e46c04a052f4e19bdb9dbf.1569246360.1111.1111.1112",
                    "55a76cf628e46c04a052f4e19bdb9dbf.1569246480.1111.1111.1112",
                ],
            },
        }
        :param strategy:
        """
        self.record = record
        self.strategy = strategy

    def adapt(self, status=None, description=None, time=None) -> dict:
        """
        将 Trigger 生产的数据适配为自愈事件
        """
        severity = self.record["trigger"]["level"]
        now_time = int(time_mod.time())
        target_type, target, data_dimensions = self.extract_target(
            self.strategy, self.record["data"]["dimensions"], self.record["data"].get("dimension_fields")
        )

        if NO_DATA_TAG_DIMENSION in data_dimensions:
            # 无数据告警的名称需要做特殊处理
            alert_name = _("[无数据] {alert_name}").format(alert_name=self.strategy["name"])
        else:
            alert_name = self.strategy["name"]

        tags = [{"key": key, "value": value} for key, value in data_dimensions.items()]
        for k, v in self.record.get("context", {}).items():
            if k not in self.SPECIAL_ALERT_TAG_KEY_WHITELIST:
                continue

            tags.append({"key": k, "value": v})

        event = {
            "event_id": self.record["anomaly"][str(severity)]["anomaly_id"],
            "plugin_id": settings.MONITOR_EVENT_PLUGIN_ID,  # 来源固定为监控
            "strategy_id": self.strategy["id"],
            "alert_name": alert_name,
            "description": description or self.record["anomaly"][str(severity)]["anomaly_message"],
            "severity": int(severity),
            "tags": tags,
            "target_type": target_type,
            "target": target,
            "status": status or EventStatus.ABNORMAL,
            "metric": [conf["metric_id"] for item in self.strategy["items"] for conf in item.get("query_configs", [])],
            "category": self.strategy["scenario"],
            "data_type": self.strategy["items"][0]["query_configs"][0]["data_type_label"],
            "dedupe_keys": [f"tags.{key}" for key in data_dimensions.keys()],
            "time": time or self.record["data"]["time"],
            "anomaly_time": EventIDParser(self.record["trigger"]["anomaly_ids"][0]).source_time,
            "bk_ingest_time": now_time,
            "bk_clean_time": now_time,
            "bk_biz_id": self.strategy["bk_biz_id"],
            "extra_info": {
                "origin_alarm": {
                    "trigger_time": now_time,
                    "data": self.record["data"],
                    "trigger": self.record.get("trigger", {}),
                    "anomaly": self.record.get("anomaly", {}),
                    "dimension_translation": {},
                    "strategy_snapshot_key": self.record["strategy_snapshot_key"],
                }
            },
        }
        return event

    @classmethod
    def extract_target(cls, strategy: Dict, dimensions: Dict, dimension_fields: List[str] = None):
        """
        解析事件的 target，将对应的维度pop出去
        返回 target_type, target, data_dimensions
        """
        item = strategy["items"][0]
        agg_dimensions = set()

        # 如果没有数据维度字段，则是用策略获取维度
        if dimension_fields is None:
            for query_config in item.get("query_configs"):
                agg_dimensions.update(query_config.get("agg_dimension", []))

                if (
                    query_config["data_type_label"] == DataTypeLabel.EVENT
                    and query_config["data_source_label"] == DataSourceLabel.BK_MONITOR_COLLECTOR
                ):
                    agg_dimensions.update(["bk_target_ip", "bk_target_cloud_id"])
        else:
            agg_dimensions = set(dimension_fields)

        data_dimensions = copy.deepcopy(dimensions)

        # 将真正用于去重的维度过滤出来
        data_dimensions = {
            key: value
            for key, value in data_dimensions.items()
            if key in agg_dimensions or key == NO_DATA_TAG_DIMENSION
        }

        try:
            if "bk_host_id" in agg_dimensions and data_dimensions.get("bk_host_id"):
                bk_host_id = data_dimensions.pop("bk_host_id")
                return EventTargetType.HOST, str(bk_host_id), data_dimensions
            elif "bk_target_ip" in agg_dimensions:
                bk_target_ip = data_dimensions.pop("bk_target_ip")
                bk_target_cloud_id = data_dimensions.pop("bk_target_cloud_id", None)
                if bk_target_cloud_id is None:
                    return EventTargetType.HOST, f"{bk_target_ip}", data_dimensions
                return EventTargetType.HOST, f"{bk_target_ip}|{bk_target_cloud_id}", data_dimensions
            elif "ip" in agg_dimensions:
                bk_target_ip = data_dimensions.pop("ip")
                bk_target_cloud_id = data_dimensions.pop("bk_cloud_id", None)
                if bk_target_cloud_id is None:
                    return EventTargetType.HOST, f"{bk_target_ip}", data_dimensions
                return EventTargetType.HOST, f"{bk_target_ip}|{bk_target_cloud_id}", data_dimensions
            elif "bk_target_service_instance_id" in agg_dimensions:
                bk_target_service_instance_id = data_dimensions.pop("bk_target_service_instance_id")
                return EventTargetType.SERVICE, bk_target_service_instance_id, data_dimensions
            elif "bk_service_instance_id" in agg_dimensions:
                bk_service_instance_id = data_dimensions.pop("bk_service_instance_id")
                return EventTargetType.SERVICE, bk_service_instance_id, data_dimensions
            elif "bk_obj_id" in data_dimensions and "bk_inst_id" in data_dimensions:
                bk_obj_id = data_dimensions.pop("bk_obj_id")
                bk_inst_id = data_dimensions.pop("bk_inst_id")
                return EventTargetType.TOPO, f"{bk_obj_id}|{bk_inst_id}", data_dimensions

        except KeyError:
            return EventTargetType.EMPTY, None, data_dimensions
        return EventTargetType.EMPTY, None, data_dimensions
