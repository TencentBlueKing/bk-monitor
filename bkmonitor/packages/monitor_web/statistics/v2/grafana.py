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
from collections import defaultdict
import json
from typing import List, Dict, Tuple

from django.utils.functional import cached_property
from django.conf import settings

from core.drf_resource import api, resource
from core.statistics.metric import Metric, register
from monitor_web.statistics.v2.base import BaseCollector
from bk_dataview.models import Org, DataSource, Dashboard, Star


class GrafanaCollector(BaseCollector):
    """
    仪表盘
    """

    @cached_property
    def organizations(self) -> List:
        if settings.ENABLE_GRAFANA_API:
            organizations = api.grafana.get_all_organization()["data"]
        else:
            organizations = Org.objects.all()
        new_organizations = []
        for org in organizations:
            if settings.ENABLE_GRAFANA_API:
                org_name = org["name"]
            else:
                org_name = org.name
            # 兼容业务id 为负数的情况
            try:
                if int(org_name) not in self.biz_info:
                    continue
            except (ValueError, TypeError):
                continue

            new_organizations.append(org)
        return new_organizations

    @cached_property
    def org_ids(self) -> List:
        org_ids = []
        for org in self.organizations:
            org_ids.append(org.id)
        return org_ids

    @cached_property
    def org_id_mapping_name(self) -> Dict[int, str]:
        org_id_mapping_name = {}
        for org in self.organizations:
            org_id_mapping_name[org.id] = org.name
        return org_id_mapping_name

    def get_org_id_mapping_dashboards(self, org_ids: List) -> Tuple[Dict[int, List[Dashboard]], List[int]]:
        """
        获取org_id对应的所有dashboard
        """
        dashboard_query = Dashboard.objects.filter(org_id__in=org_ids, is_folder__exact=0)
        org_id_mapping_dashboards = defaultdict(list)
        dashboard_ids = []
        for dashboard in dashboard_query:
            org_id_mapping_dashboards[dashboard.org_id].append(dashboard)
            dashboard_ids.append(dashboard.id)
        return org_id_mapping_dashboards, dashboard_ids

    @register(labelnames=("bk_biz_id", "bk_biz_name", "type"))
    def grafana_datasource_count(self, metric: Metric):
        """
        Grafana数据源实例数
        """
        if settings.ENABLE_GRAFANA_API:
            for org in self.organizations:
                org_name = org["name"]
                datasources = api.grafana.get_all_data_source(org_id=org["id"])["data"]
                if not datasources:
                    continue
                for datasource in datasources:
                    metric.labels(
                        bk_biz_id=int(org_name), bk_biz_name=self.get_biz_name(org_name), type=datasource["type"]
                    ).inc()
        else:
            org_ids = self.org_ids
            datasources = DataSource.objects.filter(org_id__in=org_ids)
            org_id_mapping_datasources = defaultdict(list)
            for datasource in datasources:
                org_id_mapping_datasources[datasource.org_id].append(datasource)

            org_id_mapping_name = self.org_id_mapping_name
            for org_id in org_ids:
                for datasource in org_id_mapping_datasources[org_id]:
                    metric.labels(
                        bk_biz_id=int(org_id_mapping_name[org_id]),
                        bk_biz_name=self.get_biz_name(org_id_mapping_name[org_id]), type=datasource.type
                    ).inc()

    @register(labelnames=("bk_biz_id", "bk_biz_name"))
    def grafana_dashboard_count(self, metric: Metric):
        """
        仪表盘数
        """
        if settings.ENABLE_GRAFANA_API:
            for org in self.organizations:
                org_name = org["name"]
                dashboards = api.grafana.search_folder_or_dashboard(type="dash-db", org_id=org["id"])["data"]
                metric.labels(bk_biz_id=int(org_name), bk_biz_name=self.get_biz_name(org_name)).set(len(dashboards))
        else:
            org_ids = self.org_ids
            org_id_mapping_dashboards = self.get_org_id_mapping_dashboards(org_ids)[0]
            org_id_mapping_name = self.org_id_mapping_name
            for org_id in org_ids:
                dashboards = org_id_mapping_dashboards[org_id]
                metric.labels(bk_biz_id=int(org_id_mapping_name[org_id]),
                              bk_biz_name=self.get_biz_name(org_id_mapping_name[org_id])).set(len(dashboards))

    @register(labelnames=("bk_biz_id", "bk_biz_name"))
    def grafana_dashboard_panel_count(self, metric: Metric):
        """
        仪表盘面板数
        """
        if settings.ENABLE_GRAFANA_API:
            for org in self.organizations:
                org_name = org["name"]
                dashboards = api.grafana.search_folder_or_dashboard(type="dash-db", org_id=org["id"])["data"]
                for dashboard in dashboards:
                    dashboard_info = api.grafana.get_dashboard_by_uid(uid=dashboard["uid"], org_id=org["id"])[
                        "data"].get(
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
        else:
            org_ids = self.org_ids
            org_id_mapping_dashboards = self.get_org_id_mapping_dashboards(org_ids)[0]
            for org_id in org_ids:
                panels = []
                for dashboard in org_id_mapping_dashboards[org_id]:
                    panels.extend(json.loads(dashboard.data)["panels"])
                for panel in panels:
                    if "type" not in panel:
                        continue
                    if panel["type"] == "row":
                        # 如果是行类型，需要统计嵌套数量
                        num = len(panel.get("panels", []))
                    else:
                        num = 1
                    metric.labels(bk_biz_id=int(self.org_id_mapping_name[org_id]),
                                  bk_biz_name=self.get_biz_name(self.org_id_mapping_name[org_id])).inc(num)

    @register(labelnames=("bk_biz_id", "bk_biz_name"))
    def grafana_dashboard_favorite_count(self, metric: Metric):
        """
        仪表盘收藏数
        """
        if settings.ENABLE_GRAFANA_API:
            for org in self.organizations:
                org_name = org["name"]
                dashboards = resource.grafana.get_dashboard_list(bk_biz_id=org_name, is_starred=True)
                metric.labels(bk_biz_id=int(org_name), bk_biz_name=self.get_biz_name(org_name)).set(len(dashboards))
        else:
            org_ids = self.org_ids
            org_id_mapping_dashboards, dashboard_ids = self.get_org_id_mapping_dashboards(org_ids)
            starred_dashboards = Star.objects.filter(dashboard_id__in=dashboard_ids)
            dashboard_mapping_starred_dashboards = defaultdict(list)
            for starred_dashboard in starred_dashboards:
                dashboard_mapping_starred_dashboards[starred_dashboard.dashboard_id].append(starred_dashboard)

            org_id_mapping_star_dashboards = defaultdict(list)
            for org_id, dashboards in org_id_mapping_dashboards.items():
                starred_dashboard_set = set()
                for dashboard in dashboards:
                    starred_dashboard_set.update(dashboard_mapping_starred_dashboards[dashboard.id])
                org_id_mapping_star_dashboards[org_id].extend(list(starred_dashboard_set))

            for org_id in org_ids:
                starred_dashboards = org_id_mapping_star_dashboards[org_id]
                metric.labels(bk_biz_id=int(self.org_id_mapping_name[org_id]),
                              bk_biz_name=self.get_biz_name(self.org_id_mapping_name[org_id]))\
                    .set(len(starred_dashboards))
