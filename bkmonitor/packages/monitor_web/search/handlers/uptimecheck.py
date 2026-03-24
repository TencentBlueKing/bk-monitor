from typing import cast

from bk_monitor_base.uptime_check import list_nodes, list_tasks
from django.utils.translation import gettext as _

from bkmonitor.iam import ActionEnum
from bkmonitor.utils.request import get_request_tenant_id
from monitor_web.search.handlers.base import BaseSearchHandler, SearchResultItem, SearchScope


class UptimecheckSearchHandler(BaseSearchHandler):
    SCENE = "uptimecheck"

    def search_node(self, query: str, limit: int = 10) -> list[SearchResultItem]:
        bk_tenant_id = cast(str, get_request_tenant_id())
        nodes = list_nodes(
            bk_tenant_id=bk_tenant_id,
            bk_biz_id=self.bk_biz_id if self.scope == SearchScope.BIZ else None,
            query={"name": query},
        )
        search_results = []
        for node in nodes:
            search_results.append(
                SearchResultItem(
                    bk_biz_id=node.bk_biz_id,
                    title=_("[拨测节点] {name}").format(name=node.name),
                    view="uptime-check-node-edit",
                    view_args={"params": {"id": node.id}},
                )
            )

        search_results = self.collect_results_by_biz(
            search_results,
            limit=limit,
            collect_func=lambda bk_biz_id, items: SearchResultItem(
                bk_biz_id=bk_biz_id,
                title=_("搜索到 {count} 拨测节点").format(count=len(items)),
                view="uptime-check",
                view_args={"query": {"dashboardId": "uptime-check-node", "queryString": query}},
                is_collected=True,
            ),
        )
        return search_results

    def search_task(self, query: str, limit: int = 10) -> list[SearchResultItem]:
        tasks = list_tasks(
            bk_biz_id=self.bk_biz_id if self.scope == SearchScope.BIZ else None,
            query={"name": query},
            fields=["id", "bk_biz_id", "name"],
        )
        search_results = []
        for task in tasks:
            search_results.append(
                SearchResultItem(
                    bk_biz_id=task.bk_biz_id,
                    title=_("[拨测任务] {name}").format(name=task.name),
                    view="uptime-check-task-detail",
                    view_args={"params": {"taskId": task.id}, "query": {"filter-task_id": task.id}},
                )
            )

        search_results = self.collect_results_by_biz(
            search_results,
            limit=limit,
            collect_func=lambda bk_biz_id, items: SearchResultItem(
                bk_biz_id=bk_biz_id,
                title=_("搜索到 {count} 拨测任务").format(count=len(items)),
                view="uptime-check",
                view_args={"query": {"dashboardId": "uptime-check-task", "queryString": query}},
                is_collected=True,
            ),
        )
        return search_results

    def search(self, query: str, limit: int = 10) -> list[SearchResultItem]:
        search_results = self.search_task(query, limit) + self.search_node(query, limit)
        self.add_permission_for_results(results=search_results, action=ActionEnum.VIEW_SYNTHETIC)
        return search_results
