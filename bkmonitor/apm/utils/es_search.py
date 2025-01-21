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
import re
import time
from functools import wraps
from threading import Semaphore
from typing import Any, List

import arrow
from dateutil.rrule import DAILY, MONTHLY, rrule
from elasticsearch.helpers.errors import ScanError
from elasticsearch_dsl import Search
from elasticsearch_dsl.connections import get_connection
from elasticsearch_dsl.search import ProxyDescriptor, QueryProxy

from common.log import logger


def _scan(
    client,
    query=None,
    scroll="5m",
    raise_on_error=True,
    preserve_order=False,
    size=1000,
    request_timeout=None,
    clear_scroll=True,
    scroll_kwargs=None,
    **kwargs
):
    scroll_kwargs = scroll_kwargs or {}
    if not preserve_order:
        query = query.copy() if query else {}
        query["sort"] = "_doc"

    # initial search
    resp = client.search(body=query, scroll=scroll, size=size, request_timeout=request_timeout, **kwargs)
    scroll_id = resp.get("_scroll_id")

    try:
        while scroll_id and resp["hits"]["hits"]:
            for hit in resp["hits"]["hits"]:
                yield hit

            # Default to 0 if the value isn't included in the response
            shards_successful = resp["_shards"].get("successful", 0)
            shards_skipped = resp["_shards"].get("skipped", 0)
            shards_total = resp["_shards"].get("total", 0)

            # check if we have any errors
            if (shards_successful + shards_skipped) < shards_total:
                shards_message = "Scroll request has only succeeded on %d (+%d skipped) shards out of %d."
                logger.warning(
                    shards_message,
                    shards_successful,
                    shards_skipped,
                    shards_total,
                )
                if raise_on_error:
                    raise ScanError(
                        scroll_id,
                        shards_message
                        % (
                            shards_successful,
                            shards_skipped,
                            shards_total,
                        ),
                    )
            resp = client.scroll(body={"scroll_id": scroll_id, "scroll": scroll}, **scroll_kwargs)
            scroll_id = resp.get("_scroll_id")

    finally:
        if scroll_id and clear_scroll:
            client.clear_scroll(
                body={"scroll_id": [scroll_id]},
                ignore=(404,),
            )


class EsQueryProxy(QueryProxy):
    """
    Es查询代理, 用于注入query条件对查询索引的优化操作
    """

    def __call__(self, *args, **kwargs):
        filters = kwargs.get("filter", [])
        if filters:
            for _filter in filters:
                if hasattr(_filter, "end_time"):
                    gt_time = getattr(_filter.end_time, "gt", None) or getattr(_filter.end_time, "gte", None)
                    lt_time = getattr(_filter.end_time, "lt", None) or getattr(_filter.end_time, "lte", None)
                    optimizer = QueryIndexOptimizer(
                        indices=self._search._index,
                        start_timestamp=gt_time,
                        end_timestamp=lt_time,
                        use_time_range=bool(gt_time),
                    )
                    self._search.fix_index(optimizer.index)
                    break
        s = super().__call__(*args, **kwargs)
        return s


class EsSearch(Search):
    """
    重写es的search类，增加es查询索引优化
    """

    query = ProxyDescriptor("es_query")
    post_filter = ProxyDescriptor("es_post_filter")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._es_query_proxy = EsQueryProxy(self, "query")
        self._es_post_filter_proxy = EsQueryProxy(self, "post_filter")

    def fix_index(self, indices: List[str]):
        """调整查询的目标索引列表"""

        if indices:
            self._index = indices

    def scan(self):
        es = get_connection(self._using)

        for hit in _scan(es, query=self.to_dict(), index=self._index, **self._params):
            yield self._get_result(hit)


class RateLimiter:
    def __init__(self, calls, period):
        self.calls = calls
        self.period = period
        self.semaphore = Semaphore(calls)
        self.start_time = time.time()

    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_time = time.time()
            elapsed = current_time - self.start_time

            if elapsed > self.period:
                self.start_time = current_time
                self.semaphore = Semaphore(self.calls)

            self.semaphore.acquire()
            try:
                return func(*args, **kwargs)
            finally:
                self.semaphore.release()

        return wrapper


def limits(calls, period):
    return RateLimiter(calls, period)


class QueryIndexOptimizer(object):
    """es查询索引优化类"""

    def __init__(
        self,
        indices: list,
        start_timestamp: int = None,
        end_timestamp: int = None,
        time_zone: str = "GMT",
        use_time_range: bool = True,
    ):
        self._index: str = ""
        if not indices or use_time_range is False:
            return

        start_time = arrow.get(int(start_timestamp / 1000000)) if start_timestamp else None
        end_time = arrow.get(int(end_timestamp / 1000000)) if end_timestamp else None
        filtered_indices = self.index_filter(indices, start_time, end_time, time_zone)

        if filtered_indices:
            self._index = ",".join(filtered_indices)

    @property
    def index(self):
        return [self._index] if self._index else None

    def index_filter(self, indices, start_time: arrow.Arrow, end_time: arrow.Arrow, time_zone: str) -> List[str]:
        """根据时间query时间对索引进行过滤， 返回经过过滤后的索引列表"""

        indices_list = set()
        for indices_str in indices:
            for _index in indices_str.split(","):
                indices_list.add(_index)
        index_filters = self.index_time_filters(start_time, end_time, time_zone)
        final_index_list = [_index for _index in indices_list if self.check_index_date(_index, index_filters)]
        return final_index_list

    def index_time_filters(self, date_start: arrow.Arrow, date_end: arrow.Arrow, time_zone: str):
        """获取时间过滤器列表"""

        now = arrow.now(time_zone)
        date_start = date_start.to(time_zone)
        date_end = date_end.to(time_zone) if date_end else now
        if date_end > now:
            date_end = now

        # 根据输入query的事件参数，生成能覆盖查询条件的"day"级别日期类表
        date_day_list: List[Any] = list(
            rrule(DAILY, interval=1, dtstart=date_start.floor("day").datetime, until=date_end.ceil("day").datetime)
        )

        # 根据输入query的事件参数，生成能覆盖查询条件的"month"级别日期类表
        date_month_list: List[Any] = list(
            rrule(
                MONTHLY, interval=1, dtstart=date_start.floor("month").datetime, until=date_end.ceil("month").datetime
            )
        )

        # 根据日期类表和查询条件，生成索引的时间过滤器列表
        return self._generate_filter_list(date_day_list, date_month_list)

    @classmethod
    def _generate_filter_list(cls, date_day_list, date_month_list):
        """根据日期类表和查询条件，生成索引的时间过滤器列表"""

        date_filter_template = r"^.*_bkapm_trace_.+_{}_\d+$"
        month_filter_template = r"^.*_bkapm_trace_.+_{}.*_\d+$"

        # 用于索引过滤的正则pattern列表
        filter_mapping = {}
        # 一天范围内的查询
        if len(date_day_list) == 1:
            for x in date_day_list:
                pattern = date_filter_template.format(x.strftime("%Y%m%d"))
                if pattern not in filter_mapping:
                    filter_mapping[pattern] = re.compile(pattern)
        # 一个月范围内的多日查询
        elif len(date_day_list) > 1 and len(date_month_list) == 1:
            # 14天以上的查询
            if len(date_day_list) > 14:
                for x in date_month_list:
                    pattern = month_filter_template.format(x.strftime("%Y%m"))
                    if pattern not in filter_mapping:
                        filter_mapping[pattern] = re.compile(pattern)
            # 2-14天的查询
            else:
                for x in date_day_list:
                    pattern = date_filter_template.format(x.strftime("%Y%m%d"))
                    if pattern not in filter_mapping:
                        filter_mapping[pattern] = re.compile(pattern)
        # 跨月份的多日查询
        elif len(date_day_list) > 1 and len(date_month_list) > 1:
            # 6个月内的查询
            if len(date_month_list) <= 6:
                for x in date_month_list:
                    pattern = month_filter_template.format(x.strftime("%Y%m"))
                    if pattern not in filter_mapping:
                        filter_mapping[pattern] = re.compile(pattern)
            # 6个月以上的查询
            else:
                for x in date_month_list[-6::1]:
                    pattern = month_filter_template.format(x.strftime("%Y%m"))
                    if pattern not in filter_mapping:
                        filter_mapping[pattern] = re.compile(pattern)
        return list(filter_mapping.values())

    @classmethod
    def check_index_date(cls, index, index_filters):
        # 检查索引是否匹配时间过滤器

        for filter_pattern in index_filters:
            if filter_pattern.match(index):
                return True
        return False
