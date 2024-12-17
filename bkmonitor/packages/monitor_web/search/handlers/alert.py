# -*- coding: utf-8 -*-
import time
from typing import List

from django.utils.translation import gettext as _

from bkmonitor.iam import ActionEnum
from fta_web.alert.handlers.alert import AlertQueryHandler
from monitor_web.search.handlers.base import (
    BaseSearchHandler,
    SearchResultItem,
    SearchScope,
)


class AlertSearchHandler(BaseSearchHandler):
    SCENE = "alert"
    QUERY_DAYS = 7

    def search(self, query: str, limit: int = 10) -> List[SearchResultItem]:
        end_time = int(time.time())
        start_time = end_time - self.QUERY_DAYS * 24 * 60 * 60

        bk_biz_ids = None
        if self.scope == SearchScope.BIZ:
            bk_biz_ids = [self.bk_biz_id]

        handler = AlertQueryHandler(bk_biz_ids=bk_biz_ids, start_time=start_time, end_time=end_time)
        base_search = handler.get_search_object()
        base_search = handler.add_query_string(base_search, query)

        search_obj = base_search[:1]
        search_obj.aggs.bucket("bk_biz_id", "terms", field="event.bk_biz_id", size=10000)

        agg_result = search_obj.execute().aggs

        search_results = []

        biz_to_search_detail = []

        if agg_result:
            for bucket in agg_result.bk_biz_id.buckets:
                if not bucket.key.isdigit():
                    continue
                if bucket.doc_count <= limit:
                    biz_to_search_detail.append(bucket.key)
                else:
                    search_results.append(
                        SearchResultItem(
                            bk_biz_id=int(bucket.key),
                            title=_("搜索到 {count} 告警事件").format(count=bucket.doc_count),
                            view="event-center",
                            view_args={"query": {"queryString": query, "from": f"now-{self.QUERY_DAYS}d", "to": "now"}},
                            is_collected=True,
                        )
                    )

        search_obj = base_search.filter("terms", **{"event.bk_biz_id": biz_to_search_detail}).source(
            fields=["id", "alert_name", "event.bk_biz_id"]
        )

        for alert in search_obj.scan():
            search_results.append(
                SearchResultItem(
                    bk_biz_id=alert.event.bk_biz_id,
                    title=alert.alert_name,
                    view="event-center-detail",
                    view_args={"params": {"id": alert.id}},
                )
            )

        self.add_permission_for_results(results=search_results, action=ActionEnum.VIEW_EVENT)
        return search_results
