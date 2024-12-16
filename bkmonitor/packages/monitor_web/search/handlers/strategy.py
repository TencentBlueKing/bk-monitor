# -*- coding: utf-8 -*-
from typing import List

from django.utils.translation import gettext as _

from bkmonitor.iam import ActionEnum
from bkmonitor.models import StrategyModel
from monitor_web.search.handlers.base import (
    BaseSearchHandler,
    SearchResultItem,
    SearchScope,
)


class StrategySearchHandler(BaseSearchHandler):
    SCENE = "strategy"

    def search(self, query: str, limit: int = 10) -> List[SearchResultItem]:
        strategies = StrategyModel.objects.filter(name__icontains=query).values("id", "bk_biz_id", "name")

        if self.scope == SearchScope.BIZ:
            strategies = strategies.filter(bk_biz_id=self.bk_biz_id)

        search_results = []

        for strategy in strategies:
            search_results.append(
                SearchResultItem(
                    bk_biz_id=strategy["bk_biz_id"],
                    title=strategy["name"],
                    view="strategy-config-detail",
                    view_args={"params": {"id": strategy["id"]}},
                )
            )

        search_results = self.collect_results_by_biz(
            search_results,
            limit=limit,
            collect_func=lambda bk_biz_id, items: SearchResultItem(
                bk_biz_id=bk_biz_id,
                title=_("搜索到 {count} 告警策略").format(count=len(items)),
                view="strategy-config",
                view_args={"query": {"queryString": query}},
                is_collected=True,
            ),
        )

        self.add_permission_for_results(results=search_results, action=ActionEnum.VIEW_RULE)
        return search_results
