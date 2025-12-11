"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import json
import time as time_mod
from typing import Any

from django.conf import settings
from django.utils.translation import gettext as _

from alarm_backends.core.cluster import get_cluster
from alarm_backends.core.control.mixins.double_check import DoubleCheckStrategy
from alarm_backends.core.control.record_parser import EventIDParser
from alarm_backends.core.storage.kafka import KafkaQueue
from bkmonitor.models import NO_DATA_TAG_DIMENSION, BCSPod
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from constants.alert import APMTargetType, EventStatus, EventTargetType, K8STargetType
from constants.apm import ApmAlertHelper, CommonMetricTag
from constants.data_source import DataSourceLabel, DataTypeLabel


class MonitorEventAdapter:
    """
    监控老版本事件适配器
    """

    SPECIAL_ALERT_TAG_KEY_WHITELIST = [DoubleCheckStrategy.DOUBLE_CHECK_CONTEXT_KEY]

    @classmethod
    def push_to_kafka(cls, events: list[dict]):
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
        kafka_queue.put(value=messages)

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

        # event.tags 主要用于页面检索
        additional_dimensions = data_dimensions.pop("__additional_dimensions", {})
        tags = [{"key": key, "value": value} for key, value in data_dimensions.items()]
        if additional_dimensions:
            tags += [{"key": key, "value": value} for key, value in additional_dimensions.items()]

        for k, v in self.record.get("context", {}).items():
            if k not in self.SPECIAL_ALERT_TAG_KEY_WHITELIST:
                continue

            tags.append({"key": k, "value": v})
        metric = [conf["metric_id"] for item in self.strategy["items"] for conf in item.get("query_configs", [])]
        metric += [item["name"] for item in self.strategy["items"]]
        metric += [
            conf["promql"]
            for item in self.strategy["items"]
            for conf in item.get("query_configs", [])
            if conf.get("promql")
        ]
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
            "metric": list(dict.fromkeys(metric)),
            "category": self.strategy["scenario"],
            "data_type": self.strategy["items"][0]["query_configs"][0]["data_type_label"],
            # 基于事件维度，生成唯一告警指纹。 实例化 Event内存对象，执行 clean 会补充默认字段: DEFAULT_DEDUPE_FIELDS
            # 这里事件维度的 key 统一补充 tags. 前缀
            "dedupe_keys": [f"tags.{key}" for key in data_dimensions.keys()],
            "time": time or self.record["data"]["time"],
            "anomaly_time": EventIDParser(self.record["trigger"]["anomaly_ids"][0]).source_time,
            "bk_ingest_time": now_time,
            "bk_clean_time": now_time,
            "bk_biz_id": self.strategy["bk_biz_id"],
            "bk_tenant_id": bk_biz_id_to_bk_tenant_id(self.strategy["bk_biz_id"]),
            "extra_info": {
                "additional_dimensions": additional_dimensions,
                "origin_alarm": {
                    "trigger_time": now_time,
                    "data": self.record["data"],
                    "trigger": self.record.get("trigger", {}),
                    "anomaly": self.record.get("anomaly", {}),
                    "dimension_translation": {},
                    "strategy_snapshot_key": self.record["strategy_snapshot_key"],
                },
            },
        }
        return event

    @classmethod
    def extract_target(cls, strategy: dict, dimensions: dict, dimension_fields: list[str] = None):
        """
        解析事件的 target，将对应的维度pop出去
        返回 target_type, target, data_dimensions
        如果有补充维度， 则补充到 data_dimensions下的 __additional_dimensions
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
        # 将维度中的 tags. 前缀去掉（后续 duplicate_keys 中会统一将维度加上 tags.的前缀）
        to_be_pop = []
        for key in data_dimensions:
            if key.startswith("tags."):
                to_be_pop.append(key)

        for key in to_be_pop:
            data_dimensions[key[5:]] = data_dimensions.pop(key)

        try:
            if data_dimensions.get("bk_host_id"):
                bk_host_id = data_dimensions.pop("bk_host_id")
                return EventTargetType.HOST, str(bk_host_id), data_dimensions
            elif "bk_target_ip" in agg_dimensions:
                bk_target_ip = data_dimensions.pop("bk_target_ip")
                # 兼容 云区域配置 bk_cloud_id 的情况, 采集器和采集目标的云区域都是一致的
                # 优先获取 bk_target_cloud_id，如果不存在则尝试获取 bk_cloud_id 作为备选
                # 注意：使用 is None 判断而不是 or 运算符，确保云区域ID为0时能正确处理
                # 云区域ID为0通常表示直连区域，是一个有效值，不应被当作无效值处理
                bk_target_cloud_id = data_dimensions.pop("bk_target_cloud_id", None)
                if bk_target_cloud_id is None:
                    bk_target_cloud_id = data_dimensions.pop("bk_cloud_id", None)
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
            elif "bcs_cluster_id" in data_dimensions:
                # 容器场景目标解析
                # K8S-POD, K8S-NODE, K8S-SERVICE, K8S-WORKLOAD
                return cls.get_k8s_target(data_dimensions, strategy["bk_biz_id"])
            # 从告警维度或告警策略标签中获取到 service_name 即为 APM 场景 (注：使用海象运算符，为后续其他场景留出扩展点)
            elif (target := ApmAlertHelper.get_target(strategy, data_dimensions)) and target.get("service_name"):
                return cls.get_apm_target(data_dimensions, target)

        except KeyError:
            return EventTargetType.EMPTY, None, data_dimensions
        return EventTargetType.EMPTY, None, data_dimensions

    @classmethod
    def get_k8s_target(cls, dimensions: dict, bk_biz_id: int):
        """
        获取容器场景的目标
        注意：此方法会修改传入的 dimensions 字典，补充相关维度信息
        """
        bcs_cluster_id = dimensions.get("bcs_cluster_id")
        pod = dimensions.get("pod") or dimensions.get("pod_name")
        namespace = dimensions.get("namespace")

        if pod:
            # pod 对象, 数据维度有pod 信息，直接查出 workload 和 namespace
            pod_instance = BCSPod.get_instance_with_cache(name=pod, bcs_cluster_id=bcs_cluster_id, namespace=namespace)
            if pod_instance:
                additional_dimensions = {}
                # 补充维度信息
                if "workload_kind" not in dimensions:
                    additional_dimensions["workload_kind"] = pod_instance.workload_type
                if "workload_name" not in dimensions:
                    additional_dimensions["workload_name"] = pod_instance.workload_name
                if "namespace" not in dimensions:
                    additional_dimensions["namespace"] = pod_instance.namespace
                # 将丰富的维度信息补充到 event 的 extra_info 中，后续 alert 丰富使用
                if additional_dimensions:
                    dimensions["__additional_dimensions"] = additional_dimensions
                return K8STargetType.POD, pod, dimensions
            else:
                # Pod 存在但查询不到实例，仍然按 Pod 处理，避免错误分类
                # 检查 namespace 是否存在，Pod 是命名空间级别的资源
                if namespace is None:
                    return EventTargetType.EMPTY, None, dimensions
                return K8STargetType.POD, pod, dimensions

        workload_kind = dimensions.get("workload_kind")
        workload_name = dimensions.get("workload_name")
        if workload_kind and workload_name:
            # workload 对象，需要 namespace
            if namespace is None:
                return EventTargetType.EMPTY, None, dimensions
            return K8STargetType.WORKLOAD, f"{workload_kind}:{workload_name}", dimensions

        node = dimensions.get("node") or dimensions.get("node_name")
        if node:
            # node 对象，Node 是集群级别资源，不需要 namespace
            return K8STargetType.NODE, node, dimensions

        service = dimensions.get("service") or dimensions.get("service_name")
        if service:
            # service 对象，需要 namespace
            if namespace is None:
                return EventTargetType.EMPTY, None, dimensions
            return K8STargetType.SERVICE, service, dimensions

        return EventTargetType.EMPTY, None, dimensions

    @classmethod
    def get_apm_target(
        cls, dimensions: dict[str, Any], apm_target: dict[str, str | None]
    ) -> tuple[str, str | None, dict]:
        """
        获取 APM 场景的目标信息

        :param dimensions: 维度字典
        :param apm_target: APM 目标信息字典，包含 app_name 和 service_name
        :return: 返回元组 (target_type, target, dimensions)
                 - target_type: "APM-SERVICE" 或 空字符串
                 - target: {app_name}:{service_name}格式化后的值 或 None
                 - dimensions: 处理后的维度字典
        """
        app_name_tag: str = CommonMetricTag.APP_NAME.value
        service_name_tag: str = CommonMetricTag.SERVICE_NAME.value
        app_name: str | None = apm_target.get(app_name_tag)
        service_name: str | None = apm_target.get(service_name_tag)

        if not app_name or not service_name:
            return EventTargetType.EMPTY, None, dimensions

        dimensions["__additional_dimensions"] = dict()
        # 补充后续可用被丰富的 app_name 和 service_name 维度字段
        if app_name_tag not in dimensions:
            dimensions["__additional_dimensions"].update({app_name_tag: app_name})
        if service_name_tag not in dimensions:
            dimensions["__additional_dimensions"].update({service_name_tag: service_name})

        return APMTargetType.SERVICE, f"{app_name}:{service_name}", dimensions
