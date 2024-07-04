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
from django.core.paginator import Paginator

from core.drf_resource import api, resource
from core.statistics.metric import Metric, register
from monitor_web.statistics.v2.base import BaseCollector
from bk_dataview.models import Org, DataSource, Dashboard, Star


class GrafanaCollector(BaseCollector):
    """
    仪表盘
    """
    CHUNK_SIZE = 500

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

    @staticmethod
    def dashboard_data_iterator(fields: list, batch_size: int = 1000):
        dashboards_query = Dashboard.objects.filter(is_folder=0).values_list(*fields)
        paginator = Paginator(dashboards_query, batch_size)
        for page_number in range(1, paginator.num_pages + 1):
            page = paginator.page(page_number)
            for item in page.object_list:
                yield item

    def increment_panel_metric(self, panels, biz_id, metric: Metric):
        for panel in panels:
            if "type" not in panel:
                continue
            if panel["type"] == "row":
                # 如果是行类型，需要统计嵌套数量
                num = len(panel.get("panels", []))
            else:
                num = 1
            metric.labels(bk_biz_id=biz_id, bk_biz_name=self.get_biz_name(biz_id)).inc(num)

    @staticmethod
    def chunked_list(big_list, chunk_size):
        for i in range(0, len(big_list), chunk_size):
            yield big_list[i:i + chunk_size]

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
                            bk_biz_name=self.get_biz_name(org_id_mapping_biz_id[org_id]), type=datasource_type
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
            org_id_mapping_biz_id = self.org_id_mapping_biz_id
            for org_id in self.org_ids:
                num = 0
                for org_id_, in self.dashboard_data_iterator(fields=["org_id", ]):
                    if org_id_ == org_id:
                        num += 1
                metric.labels(bk_biz_id=org_id_mapping_biz_id[org_id],
                              bk_biz_name=self.get_biz_name(org_id_mapping_biz_id[org_id])).set(num)

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
                    self.increment_panel_metric(dashboard_info.get("panels", []), int(org_name), metric)
        else:
            org_id_mapping_biz_id = self.org_id_mapping_biz_id
            for org_id in self.org_ids:
                for org_id_, data in self.dashboard_data_iterator(fields=["org_id", "data"]):
                    if org_id_ == org_id:
                        panels = json.loads(data)["panels"]
                        biz_id = org_id_mapping_biz_id[org_id]
                        self.increment_panel_metric(panels, biz_id, metric)

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
            org_id_mapping_biz_id = self.org_id_mapping_biz_id
            for org_id in self.org_ids:
                dashboard_ids = []
                for org_id_, id in self.dashboard_data_iterator(fields=["org_id", "id"]):
                    if org_id_ == org_id:
                        dashboard_ids.append(id)
                num = 0
                for chunk in self.chunked_list(dashboard_ids, self.CHUNK_SIZE):
                    num += Star.objects.filter(dashboard_id__in=chunk).count()
                metric.labels(bk_biz_id=org_id_mapping_biz_id[org_id],
                              bk_biz_name=self.get_biz_name(org_id_mapping_biz_id[org_id]))\
                    .set(num)
