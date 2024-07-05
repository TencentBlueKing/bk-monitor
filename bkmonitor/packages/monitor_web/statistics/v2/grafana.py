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
from collections import defaultdict
from typing import Dict, List

from django.conf import settings
from django.utils.functional import cached_property

from bk_dataview.models import Dashboard, DataSource, Org, Star
from core.drf_resource import api
from core.statistics.metric import Metric, register
from monitor_web.statistics.v2.base import BaseCollector


class GrafanaCollector(BaseCollector):
    """
    仪表盘
    """

    CHUNK_SIZE = 500

    def __init__(self):
        super().__init__()
        self._dashboard_data = []

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
    def org_id_mapping_biz_id(self) -> Dict[int, int]:
        org_id_mapping_biz_id = {}
        for org in self.organizations:
            org_id_mapping_biz_id[org.id] = int(org.name)
        return org_id_mapping_biz_id

    def get_dashboard_data(self) -> List[Dict]:
        """
        获取仪表盘数据
        """
        if self._dashboard_data is None:
            if settings.ENABLE_GRAFANA_API:
                self._dashboard_data = api.grafana.get_all_dashboard()["data"]
            else:
                self._dashboard_data = list(Dashboard.objects.filter(is_folder=0).values("id", "uid", "org_id", "data"))
                for dashboard in self._dashboard_data:
                    try:
                        dashboard["data"] = json.loads(dashboard["data"])
                    except json.JSONDecodeError:
                        dashboard["data"] = {}

        return self._dashboard_data

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
            for chunk in self.chunked_list(org_ids, self.CHUNK_SIZE):
                datasources = DataSource.objects.filter(org_id__in=chunk).values_list("org_id", "type")

            org_id_mapping_biz_id = self.org_id_mapping_biz_id
            for org_id in org_ids:
                for org_id_, datasource_type in datasources:
                    if org_id_ == org_id:
                        metric.labels(
                            bk_biz_id=org_id_mapping_biz_id[org_id],
                            bk_biz_name=self.get_biz_name(org_id_mapping_biz_id[org_id]),
                            type=datasource_type,
                        ).inc()

    @register(labelnames=("bk_biz_id", "bk_biz_name"))
    def grafana_dashboard_count(self, metric: Metric):
        """
        仪表盘数
        """
        org_id_mapping_biz_id = self.org_id_mapping_biz_id

        org_metrics = defaultdict(lambda: 0)
        for dashboard in self.get_dashboard_data():
            org_metrics[dashboard["org_id"]] += 1

        for org_id, value in org_metrics:
            metric.labels(
                bk_biz_id=org_id_mapping_biz_id[org_id], bk_biz_name=self.get_biz_name(org_id_mapping_biz_id[org_id])
            ).set(value)

    @register(labelnames=("bk_biz_id", "bk_biz_name"))
    def grafana_dashboard_panel_count(self, metric: Metric):
        """
        仪表盘面板数
        """
        org_id_mapping_biz_id = self.org_id_mapping_biz_id
        dashboards = self.get_dashboard_data()

        org_metrics = defaultdict(lambda: 0)
        for dashboard in dashboards:
            org_id = dashboard["org_id"]

            # 仪表盘面板数量
            dashboard_data = json.loads(dashboard["data"])
            panels = dashboard_data.get("panels", [])
            for panel in panels:
                if panel.get("type") == "row":
                    org_metrics[org_id]["panel"] += len(panel.get("panels", []))
                else:
                    org_metrics[org_id]["panel"] += 1

        for org_id, value in org_metrics.items():
            metric.labels(
                bk_biz_id=org_id_mapping_biz_id[org_id], bk_biz_name=self.get_biz_name(org_id_mapping_biz_id[org_id])
            ).set(value)

    @register(labelnames=("bk_biz_id", "bk_biz_name"))
    def grafana_dashboard_favorite_count(self, metric: Metric):
        """
        仪表盘收藏数
        """
        org_id_mapping_biz_id = self.org_id_mapping_biz_id
        dashboards = self.get_dashboard_data()
        stars = {s["dashboard_id"] for s in Star.objects.all().values("dashboard_id").distinct()}

        org_metrics = defaultdict(lambda: 0)
        for dashboard in dashboards:
            org_id = dashboard["org_id"]
            if dashboard["id"] in stars:
                org_metrics[org_id] += 1

        for org_id, value in org_metrics.items():
            metric.labels(
                bk_biz_id=org_id_mapping_biz_id[org_id], bk_biz_name=self.get_biz_name(org_id_mapping_biz_id[org_id])
            ).set(value)
