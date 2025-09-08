# -*- coding: utf-8 -*-
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
from datetime import datetime, timedelta

from django.utils.translation import gettext as _
from rest_framework import serializers

from bkmonitor.aiops.alert.utils import AIOPSManager
from bkmonitor.documents import ActionInstanceDocument, AlertDocument
from bkmonitor.models import ActionInstance
from bkmonitor.utils.time_tools import hms_string, utc2localtime
from constants.alert import EventStatus, EventTargetType
from constants.shield import ShieldType
from core.drf_resource import api, resource
from core.errors.weixin.event import AlertCollectNotFound
from fta_web.alert.handlers.base import AlertDimensionFormatter
from fta_web.alert.resources import (
    AlertDetailResource,
    AlertPermissionResource,
    AlertRelatedInfoResource,
)

logger = logging.getLogger(__name__)


class EventTargetMixin(object):
    @classmethod
    def get_target_display(cls, alert, topo_links=None):
        """
        目标展示
        """
        event = alert.event_document
        if not event.target:
            return ""

        if event.target_type == EventTargetType.HOST:
            for dimension in alert.dimensions:
                dimension = dimension.to_dict()
                if "ip" == dimension.get("key"):
                    return dimension["display_value"]
            return event.ip
        elif event.target_type == EventTargetType.SERVICE:
            for dimension in alert.dimensions:
                dimension = dimension.to_dict()
                if "bk_service_instance_id" == dimension.get("key") and dimension.get("display_value"):
                    return dimension["display_value"]
            return event.bk_service_instance_id
        elif event.target_type == EventTargetType.TOPO:
            topo_node = ""
            for dimension in alert.dimensions:
                dimension = dimension.to_dict()
                if "bk_topo_node" == dimension.get("key"):
                    topo_node = dimension
                    break

            if not topo_node.get("value"):
                return ""

            node_id = topo_node.get("value").split("|")
            if len(node_id) != 2:
                return ""

            bk_obj_id, bk_inst_id = node_id

            # 尝试获取拓扑信息
            if not topo_links:
                topo_tree = api.cmdb.get_topo_tree(bk_biz_id=event.bk_biz_id)
                topo_links = topo_tree.convert_to_topo_link()

            for topo_link in topo_links.values():
                for index, topo in enumerate(topo_link):
                    if topo.bk_inst_id != bk_inst_id or topo.bk_obj_id != bk_obj_id:
                        continue

                    return "/".join(topo.bk_inst_name for topo in topo_link[index:])

            # 如果没有拓扑链，则直接展示
            return "{}({})".format(
                topo_node.get("display_key", bk_obj_id),
                topo_node.get("display_value", bk_inst_id),
            )

        return ""


class GetAlarmDetail(AlertPermissionResource, EventTargetMixin):
    """
    根据汇总ID展示告警信息及事件列表
    """

    class RequestSerializer(serializers.Serializer):
        alert_collect_id = serializers.IntegerField()
        bk_biz_id = serializers.IntegerField()

    def perform_request(self, params):
        try:
            action = ActionInstance.objects.get(id=str(params["alert_collect_id"])[10:])
        except ActionInstance.DoesNotExist:
            action = ActionInstanceDocument.get(id=str(params["alert_collect_id"]))
        except Exception:
            raise AlertCollectNotFound(alert_collect_id=params["alert_collect_id"])

        # 获取业务名
        business = api.cmdb.get_business(bk_biz_ids=[params["bk_biz_id"]])
        if business:
            bk_biz_name = business[0].bk_biz_name
        else:
            bk_biz_name = str(params["bk_biz_id"])

        result = {
            "collect_time": action.end_time if isinstance(action, ActionInstance) else utc2localtime(action.end_time),
            "message": action.outputs.get("message", "") if action.outputs else "",
            "bk_biz_id": params["bk_biz_id"],
            "bk_biz_name": bk_biz_name,
            "events": [],
        }

        # 查询关联事件
        alerts = AlertDocument.mget(action.alerts)

        topo_links = None
        for alert in alerts:
            event = alert.event_document
            # 获取事件目标，如果有目标则展示目标，否则展示维度
            if event.target:
                # 避免重复请求拓扑链
                if event.target_type == EventTargetType.TOPO and not topo_links:
                    topo_tree = api.cmdb.get_topo_tree(bk_biz_id=event.bk_biz_id)
                    topo_links = topo_tree.convert_to_topo_link()

                title = self.get_target_display(alert, topo_links)
            else:
                dimensions = [dimension.to_dict() for dimension in alert.dimensions]

                title = " ".join(
                    "{}={}".format(dimension["display_key"], dimension["display_value"]) for dimension in dimensions
                )

            try:
                data_type_label = alert.strategy["items"][0]["query_configs"][0]["data_type_label"]
            except Exception:
                data_type_label = ""

            result["events"].append(
                {
                    "id": alert.id,
                    "event_id": alert.id,
                    "first_anomaly_time": utc2localtime(alert.first_anomaly_time),
                    "latest_anomaly_time": utc2localtime(alert.latest_time),
                    "status": alert.status,
                    "is_shielded": alert.is_shielded,
                    "shield_type": ShieldType.SAAS_CONFIG if alert.is_shielded else "",
                    "is_ack": alert.is_ack,
                    "duration": hms_string(alert.duration),
                    "strategy_name": event.alert_name,
                    "dimension_message": AlertDimensionFormatter.get_dimensions_str(alert.dimensions),
                    "title": title,
                    "level": alert.severity,
                    "data_type_label": data_type_label,
                }
            )
        return result


class GetEventDetail(AlertPermissionResource, EventTargetMixin):
    """
    事件详情
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        event_id = serializers.IntegerField(label="事件ID")

    def perform_request(self, params):
        alert = AlertDocument.get(params["event_id"])
        event = alert.event_document

        # 获取关联信息
        related_info = ""
        try:
            related_info += (
                AlertRelatedInfoResource.get_cmdb_related_info([alert]).get(alert.id, {}).get("topo_info", "")
            )
            related_info += AlertDetailResource.get_relation_info(alert)
        except Exception as e:
            logger.exception(e)

        # 获取事件标题
        if event.target_type:
            title = self.get_target_display(alert)
        else:
            title = AlertDimensionFormatter.get_dimensions_str(alert.dimensions)

        try:
            current_value = event.extra_info.origin_alarm.data.value
        except Exception:
            current_value = None

        try:
            data_type_label = alert.strategy["items"][0]["query_configs"][0]["data_type_label"]
        except Exception:
            data_type_label = ""

        result = {
            "id": alert.id,
            "strategy_name": event.alert_name,
            "username": ",".join(alert.assignee),
            "first_anomaly_time": utc2localtime(alert.first_anomaly_time),
            "latest_anomaly_time": utc2localtime(alert.latest_time),
            "create_time": utc2localtime(alert.create_time),
            "level_name": alert.severity_display,
            "level": alert.severity,
            "status": alert.status,
            "notice_status": "SUCCESS",  # TODO: 此处需要实现获取逻辑
            "current_value": current_value,
            "anomaly_message": event.description,
            "duration": hms_string(alert.duration),
            "dimensions": AlertDimensionFormatter.get_dimensions(alert.dimensions),
            "dimension_message": AlertDimensionFormatter.get_dimensions_str(alert.dimensions),
            "related_info": related_info,
            "target_type": event.target_type.lower() if event.target_type else "",
            "target_message": self.get_target_display(alert),
            "title": title,
            "is_shield": alert.is_shielded,
            "shield_type": ShieldType.SAAS_CONFIG if alert.is_shielded else "",
            "data_type_label": data_type_label,
        }

        return result


class GetEventGraphView(AlertPermissionResource):
    """
    查询事件视图
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        event_id = serializers.IntegerField(label="事件ID", required=True)
        start_time = serializers.IntegerField(required=False, label="开始时间")
        end_time = serializers.IntegerField(required=False, label="结束时间")
        time_compare = serializers.IntegerField(
            label="时间对比(小时)",
            required=False,
        )

    def perform_request(self, params):
        current_params = {"bk_biz_id": params["bk_biz_id"], "id": params["event_id"]}
        if "start_time" in params and "end_time" in params:
            current_params["start_time"] = params["start_time"]
            current_params["end_time"] = params["end_time"]

        alert = AlertDocument.get(params["event_id"])

        graph_panel = AIOPSManager.get_graph_panel(alert)
        query_params = graph_panel["targets"][0]["data"]
        query_params.update(current_params)
        time_compare = params.get("time_compare")

        query_params["function"] = {}
        if len(query_params["query_configs"][0]["metrics"]) > 1:
            # 如果有多个指标数据，暂时不对曲线做降采样。  待支持：底层需要支持多个指标的降采样点需保持一致
            query_params["function"].update({"max_point_number": 0})

        compare_series_name = ""
        if time_compare:
            query_params["function"].update({"time_compare": ["{}h".format(time_compare)]})
            compare_series_name = hms_string(timedelta(hours=time_compare).total_seconds())
        result = resource.alert.alert_graph_query(**query_params)

        # 计算statistics数据
        current_time = None
        for series in result["series"]:
            datapoints = series["datapoints"]
            points = [point[0] for point in datapoints if point[0] is not None]

            # 移动端图例名称精简
            if time_compare:
                series["target"] = _("当前") if series.get("time_offset") == "current" else compare_series_name
            else:
                series["target"] = _("当前")

            # 获取当前值，取最新的点，历史数据取对应时间的点
            current = ""
            if current_time is None:
                # 查找最新的值不为None的点
                for point in reversed(datapoints):
                    if point[0] is None:
                        continue
                    # 记录该点的时间
                    current_time = point[1]
                    current = "{:g}".format(point[0])
                    break
                else:
                    current_time = 0
            elif current_time:
                # 查找对应时间的点
                for point in datapoints:
                    if point[1] == current_time and point[0] is not None:
                        current = "{:g}".format(point[0])

            series["statistics"] = {
                "min": "{:g}".format(min(points)) if points else "",
                "max": "{:g}".format(max(points)) if points else "",
                "avg": "{:g}".format(sum(points) / len(points)) if points else "",
                "current": current,
                "total": "{:g}".format(sum(points)),
            }

        return result["series"]


class GetEventList(AlertPermissionResource, EventTargetMixin):
    """
    获取未恢复事件列表
    """

    class RequestSerializer(serializers.Serializer):
        level = serializers.IntegerField(label="告警级别", required=False)
        bk_biz_id = serializers.IntegerField(label="业务ID")
        type = serializers.ChoiceField(label="分组类型", default="strategy", choices=("strategy", "target", "shield"))
        only_count = serializers.BooleanField(label="只看统计数量", default=False)

    def group_by_strategy(self, alerts):
        """
        按策略分组展示
        """
        result = {}

        topo_links = None
        for alert in alerts:
            event = alert.event_document

            key = "{}|{}".format(alert.strategy_id, alert.severity)
            # 如果不存在分组则初始化
            if key not in result:
                result[key] = {
                    "strategy_id": alert.strategy_id,
                    "level": alert.severity,
                    "name": alert.event_document.alert_name,
                    "events": [],
                }

            # 获取事件目标，如果有目标则展示目标，否则展示维度
            if event.target:
                # 避免重复请求拓扑链
                if event.target_type == EventTargetType.TOPO and not topo_links:
                    topo_tree = api.cmdb.get_topo_tree(bk_biz_id=event.bk_biz_id)
                    topo_links = topo_tree.convert_to_topo_link()

                title = self.get_target_display(alert, topo_links)
            else:
                dimensions = [dimension.to_dict() for dimension in alert.dimensions]
                title = " ".join(
                    "{}={}".format(dimension["display_key"], dimension["display_value"]) for dimension in dimensions
                )

            result[key]["events"].append(
                {
                    "event_id": alert.id,
                    "target": title,
                    "duration": hms_string(alert.duration or 0),
                    "dimension_message": AlertDimensionFormatter.get_dimensions_str(alert.dimensions),
                }
            )

        return list(result.values())

    def group_by_target(self, alerts):
        """
        按监控目标分组展示
        """
        result = {}

        for alert in alerts:
            if not alert.event_document.target:
                continue

            # 如果不存在分组则初始化
            key = self.get_target_display(alert)
            if key not in result:
                result[key] = {"target": key, "events": []}

            result[key]["events"].append(
                {
                    "event_id": alert.id,
                    "level": alert.severity,
                    "strategy_name": alert.event_document.alert_name,
                    "dimension_message": AlertDimensionFormatter.get_dimensions_str(alert.dimensions),
                }
            )

        return list(result.values())

    def perform_request(self, params):
        # 没有业务权限，使用接收人权限

        search = (
            AlertDocument.search(all_indices=True)
            .filter("term", status=EventStatus.ABNORMAL)
            .filter(
                "term",
                **{"event.bk_biz_id": params["bk_biz_id"]},
            )
        )

        if "receiver" in params:
            search = search.filter("term", assignee=params["receiver"])

        search.aggs.bucket("strategy", "filter", {"term": {"is_shielded": False}}).bucket(
            "target", "filter", {"exists": {"field": "event.target"}}
        )

        search.aggs.bucket("shield", "filter", {"term": {"is_shielded": True}})

        if params["only_count"]:
            groups = []
        else:
            group_search = search.filter("term", is_shielded=params["type"] == "shield")

            # 是否按告警级别过滤
            if "level" in params:
                group_search = group_search.filter("term", severity=params["level"])

            # 是否有告警目标
            if params["type"] == "target":
                group_search = group_search.filter("exists", field="event.target")

            alerts = [AlertDocument(**hit.to_dict()) for hit in group_search.scan()]

            if params["type"] == "target":
                groups = list(self.group_by_target(alerts))
            else:
                groups = list(self.group_by_strategy(alerts))

        search_result = search.execute()

        return {
            "count": {
                "strategy": search_result.aggs.strategy.doc_count if search_result.aggs else 0,
                "target": search_result.aggs.strategy.target.doc_count if search_result.aggs else 0,
                "shield": search_result.aggs.shield.doc_count if search_result.aggs else 0,
            },
            "groups": groups,
        }


class AckEvent(AlertPermissionResource):
    """
    基于告警汇总对事件进行批量确认
    """

    class RequestSerializer(serializers.Serializer):
        alert_collect_id = serializers.IntegerField(label="告警汇总ID")
        bk_biz_id = serializers.IntegerField(label="业务ID")

    def perform_request(self, params):
        action = ActionInstance.objects.get(id=str(params["alert_collect_id"])[10:])
        return resource.alert.ack_alert(ids=action.alerts, message=_("移动端确认"))


class QuickShield(AlertPermissionResource):
    """
    快速屏蔽事件
    """

    class RequestSerializer(serializers.Serializer):
        type = serializers.ChoiceField(label="屏蔽类型", choices=["scope", "strategy", "event"])
        event_id = serializers.IntegerField(label="事件ID")
        bk_biz_id = serializers.IntegerField(label="业务ID")
        end_time = serializers.DateTimeField(label="屏蔽结束时间", input_formats=["%Y-%m-%d %H:%M:%S"])
        description = serializers.CharField(label="屏蔽描述", allow_blank=True, default="")
        dimension_keys = serializers.ListField(label="维度键名列表", child=serializers.CharField(), default=None)

    @staticmethod
    def handle_scope(alert):
        """
        根据事件生成目标范围屏蔽参数
        """
        params = {
            "category": "scope",
        }

        event = alert.event_document

        if event.target_type == EventTargetType.HOST:
            params["dimension_config"] = {
                "scope_type": "ip",
                "target": [{"ip": event.ip, "bk_cloud_id": event.bk_cloud_id}],
            }
        elif event.target_type == EventTargetType.SERVICE:
            params["dimension_config"] = {
                "scope_type": "instance",
                "target": [event.bk_service_instance_id],
            }
        elif event.target_type == EventTargetType.TOPO:
            bk_obj_id, bk_inst_id = event.target.split("|")[1:]
            params["dimension_config"] = {
                "scope_type": "topo",
                "target": [{"bk_obj_id": bk_obj_id, "bk_inst_id": bk_inst_id}],
            }
        return params

    @staticmethod
    def handle_strategy(alert):
        """
        根据事件生成策略屏蔽参数
        """
        return {"category": "strategy", "dimension_config": {"id": [alert.strategy_id]}}

    @staticmethod
    def handle_event(alert):
        """
        根据事件生成事件屏蔽参数
        """
        return {"category": "alert", "dimension_config": {"alert_id": alert.id}}

    def handle(self, params, alert):
        """
        根据事件及屏蔽类型生成屏蔽参数
        """
        method_map = {
            "scope": self.handle_scope,
            "event": self.handle_event,
            "strategy": self.handle_strategy,
        }

        shield_params = {
            "end_time": params["end_time"].strftime("%Y-%m-%d %H:%M:%S"),
            "begin_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "description": params["description"],
            "bk_biz_id": params["bk_biz_id"],
            "shield_notice": False,
            "cycle_config": {"begin_time": "", "type": 1, "end_time": ""},
            "is_quick": True,
        }
        if params["dimension_keys"] is not None:
            shield_params["dimension_keys"] = params["dimension_keys"]

        shield_params.update(method_map[params["type"]](alert))
        return shield_params

    def perform_request(self, params):
        alert = AlertDocument.get(id=params["event_id"])
        return resource.shield.add_shield(self.handle(params, alert))
