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
from django.utils.functional import cached_property

from core.drf_resource import api, resource
from core.statistics.metric import Metric, register
from monitor_web.statistics.v2.base import BaseCollector


class GrafanaCollector(BaseCollector):
    """
    仪表盘
    """

    @cached_property
    def organizations(self):
        organizatios = api.grafana.get_all_organization()["data"]
        new_organizatios = []
        for org in organizatios:
            org_name = org["name"]
            # 兼容业务id 为负数的情况
            try:
                if int(org_name) not in self.biz_info:
                    continue
            except (ValueError, TypeError):
                continue

            new_organizatios.append(org)
        return new_organizatios

    @register(labelnames=("bk_biz_id", "bk_biz_name", "type"))
    def grafana_datasource_count(self, metric: Metric):
        """
        Grafana数据源实例数
        """
        for org in self.organizations:
            org_name = org["name"]
            datasources = api.grafana.get_all_data_source(org_id=org["id"])["data"]
            if not datasources:
                continue
            for datasource in datasources:
                metric.labels(
                    bk_biz_id=int(org_name), bk_biz_name=self.get_biz_name(org_name), type=datasource["type"]
                ).inc()

    @register(labelnames=("bk_biz_id", "bk_biz_name"))
    def grafana_dashboard_count(self, metric: Metric):
        """
        仪表盘数
        """
        for org in self.organizations:
            org_name = org["name"]
            dashboards = api.grafana.search_folder_or_dashboard(type="dash-db", org_id=org["id"])["data"]
            metric.labels(bk_biz_id=int(org_name), bk_biz_name=self.get_biz_name(org_name)).set(len(dashboards))

    @register(labelnames=("bk_biz_id", "bk_biz_name"))
    def grafana_dashboard_panel_count(self, metric: Metric):
        """
        仪表盘面板数
        """
        for org in self.organizations:
            org_name = org["name"]
            dashboards = api.grafana.search_folder_or_dashboard(type="dash-db", org_id=org["id"])["data"]
            for dashboard in dashboards:
                dashboard_info = api.grafana.get_dashboard_by_uid(uid=dashboard["uid"], org_id=org["id"])["data"].get(
                    "dashboard", {}
                )
                for panel in dashboard_info.get("panels", []):
                    if "type" not in panel:
                        continue
                    if panel["type"] == "row":
                        # 如果是行类型，需要统计嵌套数量
                        num = len(panel.get("panels", []))
                    else:
                        num = 1
                    metric.labels(bk_biz_id=int(org_name), bk_biz_name=self.get_biz_name(org_name)).inc(num)

    @register(labelnames=("bk_biz_id", "bk_biz_name"))
    def grafana_dashboard_favorite_count(self, metric: Metric):
        """
        仪表盘收藏数
        """
        for org in self.organizations:
            org_name = org["name"]
            dashboards = resource.grafana.get_dashboard_list(bk_biz_id=org_name, is_starred=True)
            metric.labels(bk_biz_id=int(org_name), bk_biz_name=self.get_biz_name(org_name)).set(len(dashboards))
