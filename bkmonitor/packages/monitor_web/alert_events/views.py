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

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import BusinessActionPermission
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class EventCenterViewSet(ResourceViewSet):
    def get_permissions(self):
        if self.action in ["list_index_by_host", "is_host_exists_index"]:
            return []
        return [BusinessActionPermission([ActionEnum.VIEW_EVENT])]

    resource_routes = [
        # 事件列表
        ResourceRoute("POST", resource.alert_events.list_event, endpoint="list_event"),
        # 策略配置快照详情
        ResourceRoute("GET", resource.alert_events.strategy_snapshot, endpoint="strategy_snapshot"),
        # 通知次数列表
        ResourceRoute("GET", resource.alert_events.list_alert_notice, endpoint="list_alert_notice"),
        # 通知详情
        ResourceRoute("GET", resource.alert_events.detail_alert_notice, endpoint="detail_alert_notice"),
        # 告警确认
        ResourceRoute("POST", resource.alert_events.ack_event, endpoint="ack_event"),
        # 获取处理建议
        ResourceRoute("GET", resource.alert_events.get_solution, endpoint="get_solution"),
        # 保存处理建议
        ResourceRoute("POST", resource.alert_events.save_solution, endpoint="save_solution"),
        # 获取流转记录
        ResourceRoute("POST", resource.alert_events.list_event_log, endpoint="event_log"),
        # 获取搜索列表
        ResourceRoute("POST", resource.alert_events.list_search_item, endpoint="list_search_item"),
        # 搜索收敛异常列表
        ResourceRoute("GET", resource.alert_events.list_converge_log, endpoint="list_converge_log"),
        # 趋势图
        ResourceRoute("POST", resource.alert_events.stacked_chart, endpoint="stacked_chart"),
        # 屏蔽配置快照
        ResourceRoute("GET", resource.alert_events.shield_snapshot, endpoint="shield_snapshot"),
        # 根据主机查询对应已下发的日志平台采集索引列表
        ResourceRoute("POST", resource.alert_events.list_index_by_host, endpoint="list_index_by_host"),
        # 判断当前主机下是否有采集项
        ResourceRoute("POST", resource.alert_events.is_host_exists_index, endpoint="is_host_exists_index"),
        # 折线图
        ResourceRoute("POST", resource.alert_events.graph_point, endpoint="graph_point"),
    ]
