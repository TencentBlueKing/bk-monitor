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
import os

from django.utils.translation import gettext as _

from alarm_backends.core.alert import Alert
from alarm_backends.core.cache.cmdb import (
    HostManager,
    ServiceInstanceManager,
    TopoManager,
)
from alarm_backends.core.cache.models.uptimecheck import UptimecheckCacheManager
from alarm_backends.service.alert.enricher import (
    BaseAlertEnricher,
    BaseEventEnricher,
    Event,
)
from alarm_backends.service.alert.enricher.translator import TranslatorFactory
from constants.alert import EventTargetType

logger = logging.getLogger("alert.enricher")


class PreEventEnricher(BaseEventEnricher):
    """
    alert.builder模块，预处理trigger推送的事件
    """

    # drop event where uptime check task_id not exists
    # 可以通过配置bk-monitor-alarm-alert-worker 的 env 来注入环境变量 DISABLE_DROP_UP_EVENT
    DISABLE_DROP_UP_EVENT = os.getenv("DISABLE_DROP_UP_EVENT", False)

    def enrich_event(self, event) -> Event:
        if event.is_dropped():
            return event
        # pass
        event = self.uptime_check_task_exist(event)
        return event

    @classmethod
    def uptime_check_task_exist(self, event):
        def enabled():
            # 默认开启丢弃判定
            if self.DISABLE_DROP_UP_EVENT:
                return False
            if "tags.task_id" in event.dedupe_keys and event.category == "uptimecheck":
                return event.metric and "uptimecheck." in event.metric[0]
            return False

        def enrich():
            # 拨测任务id 已经不存在的告警，直接丢弃记录日志
            task_id = None
            for tag in event.tags:
                if tag["key"] == "task_id":
                    task_id = tag["value"]
                    break
            if task_id is not None:
                if not UptimecheckCacheManager.get_task(task_id):
                    event.drop()
                    logger.warning("[enrich event] strategy(%s) task id(%s) not exists", event.strategy_id, task_id)

        if enabled():
            enrich()
        return event


class DimensionOrderEnricher(BaseAlertEnricher):
    """
    维度按照aggs设置顺序排序
    """

    @classmethod
    def get_dimension(cls, dimension_key, all_dimensions):
        if dimension_key in ["ip", "bk_target_ip"]:
            return all_dimensions.pop("ip", None) or all_dimensions.pop("bk_target_ip", None)
        if dimension_key in ["bk_cloud_id", "bk_target_cloud_id"]:
            return all_dimensions.pop("bk_cloud_id", None) or all_dimensions.pop("bk_target_cloud_id", None)
        if dimension_key in ["bk_service_instance_id", "bk_target_service_instance_id"]:
            return all_dimensions.pop("bk_service_instance_id", None) or all_dimensions.pop(
                "bk_target_service_instance_id", None
            )
        return all_dimensions.pop(dimension_key, None)

    def enrich_alert(self, alert: Alert):
        all_dimensions = {d["key"][5:] if "tags." in d["key"] else d["key"]: d for d in alert.dimensions}
        ordered_dimensions = []
        for dimension_key in alert.agg_dimensions:
            dimension = self.get_dimension(dimension_key, all_dimensions)
            if not dimension:
                continue
            ordered_dimensions.append(dimension)
        if all_dimensions:
            # 不在设置的维度范围内的，直接添加在最后
            ordered_dimensions.extend(all_dimensions.values())
        alert.set_dimensions(ordered_dimensions)
        return alert


class MonitorTranslateEnricher(BaseAlertEnricher):
    """
    监控专用维度翻译
    """

    def enrich_alert(self, alert: Alert):
        strategy = alert.get_extra_info("strategy")

        if not strategy:
            return alert

        origin_alarm = alert.get_extra_info("origin_alarm") or {}
        dimensions = origin_alarm.get("data", {}).get("dimensions", {})
        translator = TranslatorFactory(strategy)
        dimension_translation = translator.translate(dimensions)

        for dimension in alert.dimensions:
            if not dimension["key"].startswith("tags."):
                continue
            key = dimension["key"][5:]
            if key not in dimension_translation:
                continue
            dimension["display_key"] = _(dimension_translation[key]["display_name"])
            dimension["display_value"] = dimension_translation[key]["display_value"]
            dimension["value"] = dimension_translation[key]["value"]

        origin_alarm["dimension_translation"] = dimension_translation

        return alert


class StandardTranslateEnricher(BaseAlertEnricher):
    """
    标准字段翻译
    """

    def enrich_alert(self, alert: Alert) -> Alert:
        target_type = alert.top_event.get("target_type")

        if target_type == EventTargetType.HOST:
            return self.enrich_host(alert)

        if target_type == EventTargetType.SERVICE:
            return self.enrich_service(alert)

        if target_type == EventTargetType.TOPO:
            return self.enrich_topo(alert)

        return self.enrich_custom(alert)

    def enrich_custom(self, alert: Alert):
        """
        自定义目标类型，只要直接将目标类型和目标注入到维度即可，无需额外处理
        """
        target_type = alert.top_event.get("target_type")
        target = alert.top_event.get("target")

        if target_type:
            alert.add_dimension(key="target_type", value=target_type, display_key=_("目标类型"))

        if target:
            alert.add_dimension(key="target", value=target, display_key=_("目标"))

        return alert

    def enrich_host(self, alert: Alert):
        try:
            dimension_fields = set(alert.top_event["extra_info"]["origin_alarm"]["data"]["dimension_fields"])
        except KeyError:
            # 第三方告警不存在origin_alarm，所以默认为ip或者bk_target_ip
            dimension_fields = {"bk_target_ip", "ip"}

        if alert.top_event.get("bk_host_id") and "bk_host_id" in dimension_fields:
            bk_host_id = alert.top_event["bk_host_id"]
            host = HostManager.get_by_id(bk_host_id)
            if host:
                display_name = _("主机")
                display_value = host.display_name
            else:
                display_name = _("主机ID")
                display_value = bk_host_id

            alert.add_dimension(
                key="bk_host_id",
                value=alert.top_event["bk_host_id"],
                display_key=display_name,
                display_value=display_value,
            )

        if alert.top_event.get("ip") and bool({"bk_target_ip", "ip"} & dimension_fields):
            alert.add_dimension(key="ip", value=alert.top_event["ip"], display_key=_("目标IP"))
            alert.add_dimension(key="bk_cloud_id", value=alert.top_event["bk_cloud_id"], display_key=_("云区域ID"))

        return alert

    def enrich_service(self, alert: Alert):
        bk_service_instance_id = alert.top_event["target"]
        instance = ServiceInstanceManager.get(bk_service_instance_id)
        if not instance:
            alert.add_dimension(key="bk_service_instance_id", value=bk_service_instance_id, display_key=_("服务实例ID"))
        else:
            alert.add_dimension(
                key="bk_service_instance_id",
                value=bk_service_instance_id,
                display_key=_("服务实例名称"),
                display_value=instance.name,
            )
        return alert

    def enrich_topo(self, alert: Alert):
        bk_obj_id, bk_inst_id = alert.top_event["target"].split("|")
        node_info = TopoManager.get(bk_obj_id, bk_inst_id)
        if not node_info:
            alert.add_dimension(key="bk_topo_node", value=alert.top_event["target"], display_key=_("拓扑节点"))
        else:
            alert.add_dimension(
                key="bk_topo_node",
                value=alert.top_event["target"],
                display_key=node_info.bk_obj_name,
                display_value=node_info.bk_inst_name,
            )
        return alert
