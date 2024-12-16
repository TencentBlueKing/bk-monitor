# -*- coding: utf-8 -*-
from typing import List

from django.utils.translation import gettext as _

from bkmonitor.iam import ActionEnum
from core.drf_resource import api
from monitor_web.search.handlers.base import (
    BaseSearchHandler,
    SearchResultItem,
    SearchScope,
)


class DashboardSearchHandler(BaseSearchHandler):
    SCENE = "dashboard"

    def search(self, query: str, limit: int = 10) -> List[SearchResultItem]:
        all_organization = api.grafana.get_all_organization()["data"]

        orgs = {}
        for org in all_organization:
            org_name = org["name"]
            if not org_name.isdigit():
                continue
            if int(org_name) == self.bk_biz_id:
                orgs[int(org_name)] = org["id"]

        search_results = []
        for bk_biz_id, org_id in orgs.items():
            dashboards = api.grafana.search_folder_or_dashboard(query=query, type="dash-db", org_id=org_id)["data"]
            for dashboard in dashboards:
                search_results.append(
                    SearchResultItem(
                        bk_biz_id=bk_biz_id,
                        title=dashboard["title"],
                        view="favorite-dashboard",
                        view_args={"params": {"url": dashboard["uid"]}},
                    )
                )

        search_results = self.collect_results_by_biz(
            search_results,
            limit=limit,
            collect_func=lambda bk_biz_id, items: SearchResultItem(
                bk_biz_id=bk_biz_id,
                title=_("搜索到 {count} 仪表盘").format(count=len(items)),
                view="grafana",
                view_args={"params": {"queryString": query}},
                is_collected=True,
            ),
        )

        self.add_permission_for_results(results=search_results, action=ActionEnum.VIEW_SINGLE_DASHBOARD)
        return search_results
