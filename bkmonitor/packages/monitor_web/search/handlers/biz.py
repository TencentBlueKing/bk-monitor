# -*- coding: utf-8 -*-
from typing import List

from bkmonitor.iam import ActionEnum
from monitor_web.search.handlers.base import BaseSearchHandler, SearchResultItem


class BizSearchHandler(BaseSearchHandler):

    SCENE = "biz"

    def search(self, query: str, limit: int = 10) -> List[SearchResultItem]:

        matched_bizs = []

        for biz in self.all_business:
            matched = False
            if query.isdigit():
                if len(query) <= 3 and query == str(biz.bk_biz_id):
                    # 小于等于三位的业务ID，需要精确匹配
                    matched = True
                elif len(query) > 3 and query in str(biz.bk_biz_id):
                    # 大于等于三位的业务ID，可以模糊匹配
                    matched = True

            # 不管数字还是字符串，都支持业务名称的模糊匹配
            if query.lower() in biz.bk_biz_name.lower():
                matched = True

            if matched:
                matched_bizs.append(biz)

        search_results = [
            SearchResultItem(
                bk_biz_id=biz.bk_biz_id,
                title=f"[{biz.bk_biz_id}] {biz.bk_biz_name}",
                view="event-center",
                view_args={},
            )
            for biz in matched_bizs
        ]

        self.add_permission_for_results(results=search_results, action=ActionEnum.VIEW_EVENT)
        return search_results
