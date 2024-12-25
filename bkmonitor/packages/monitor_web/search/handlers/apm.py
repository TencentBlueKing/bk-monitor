# -*- coding: utf-8 -*-
from typing import List

from django.db.models import Q
from django.utils.translation import gettext as _

from apm.models import ApmApplication, TopoNode
from bkmonitor.iam import ActionEnum
from monitor_web.search.handlers.base import (
    BaseSearchHandler,
    SearchResultItem,
    SearchScope,
)


class ApmSearchHandler(BaseSearchHandler):
    SCENE = "apm"

    def search_application(self, query: str, limit: int = 10) -> List[SearchResultItem]:
        # 搜索应用
        apm_application_qs = ApmApplication.objects.filter(Q(app_name__contains=query) | Q(app_alias__contains=query))
        if self.scope == SearchScope.BIZ:
            apm_application_qs = apm_application_qs.filter(bk_biz_id=self.bk_biz_id)

        search_results = []

        for application in apm_application_qs.values("bk_biz_id", "app_name"):
            search_results.append(
                SearchResultItem(
                    bk_biz_id=application["bk_biz_id"],
                    title=application["app_name"],
                    view="apm-application",
                    view_args={"query": {"filter-app_name": application["app_name"]}},
                )
            )

        search_results = self.collect_results_by_biz(
            search_results,
            limit=limit,
            collect_func=lambda bk_biz_id, items: SearchResultItem(
                bk_biz_id=bk_biz_id,
                title=_("搜索到 {count} APM 应用").format(count=len(items)),
                view="apm-home",
                view_args={"query": {"queryString": query}},
                is_collected=True,
            ),
        )

        return search_results

    def search_service(self, query: str, limit: int = 10) -> List[SearchResultItem]:
        # 搜索服务
        service_qs = TopoNode.objects.filter(topo_key__contains=query)
        if self.scope == SearchScope.BIZ:
            service_qs = service_qs.filter(bk_biz_id=self.bk_biz_id)

        search_results = []

        for service in service_qs.values("bk_biz_id", "topo_key", "app_name"):
            search_results.append(
                SearchResultItem(
                    bk_biz_id=service["bk_biz_id"],
                    title=service["topo_key"],
                    view="apm-service",
                    view_args={
                        "query": {"filter-service_name": service["topo_key"], "filter-app_name": service["app_name"]}
                    },
                )
            )

        search_results = self.collect_results_by_biz(
            search_results,
            limit=limit,
            collect_func=lambda bk_biz_id, items: SearchResultItem(
                bk_biz_id=bk_biz_id,
                title=_("搜索到 {count} APM 服务").format(count=len(items)),
                view="apm-application",
                view_args={
                    "query": {
                        "dashboardId": "service",
                        "filter-app_name": service_qs[0]["app_name"],
                        "queryString": query,
                    }
                },
                is_collected=True,
            ),
        )

        return search_results

    def search(self, query: str, limit: int = 10) -> List[SearchResultItem]:
        search_results = self.search_application(query, limit) + self.search_service(query, limit)
        self.add_permission_for_results(results=search_results, action=ActionEnum.VIEW_APM_APPLICATION)
        return search_results
