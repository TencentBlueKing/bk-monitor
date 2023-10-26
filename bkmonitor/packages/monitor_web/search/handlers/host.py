# -*- coding: utf-8 -*-
from typing import List

from django.utils.translation import ugettext as _

from api.cmdb.define import Host
from bkmonitor.iam import ActionEnum
from core.drf_resource import api
from monitor_web.search.handlers.base import BaseSearchHandler, SearchScope, SearchResultItem


class HostSearchHandler(BaseSearchHandler):

    SCENE = "host"

    def search(self, query: str, limit: int = 10) -> List[SearchResultItem]:
        params = {
            # 使用CMDB搜索时，需要将 . 替换为 \. 否则会被识别为通配符
            "ip": query.replace(".", "\\.").replace("*", ".*"),
            "limit": 500,
        }

        if self.scope == SearchScope.BIZ:
            params["bk_biz_id"] = self.bk_biz_id

        hosts: Host = api.cmdb.get_host_without_biz(params)["hosts"]

        search_results = []

        for host in hosts:
            search_results.append(
                SearchResultItem(
                    bk_biz_id=host.bk_biz_id,
                    title=_("{bk_cloud_id}:{ip}").format(bk_cloud_id=host.bk_cloud_id, ip=host.ip),
                    view="performance-detail",
                    view_args={"params": {"id": f"{host.ip}-{host.bk_cloud_id}"}},
                )
            )

        search_results = self.collect_results_by_biz(
            search_results,
            limit=limit,
            collect_func=lambda bk_biz_id, items: SearchResultItem(
                bk_biz_id=bk_biz_id,
                title=_("搜索到 {count} 主机").format(count=len(items)),
                view="performance",
                view_args={"query": {"queryString": query}},
                is_collected=True,
            ),
        )

        self.add_permission_for_results(results=search_results, action=ActionEnum.VIEW_HOST)

        return search_results
