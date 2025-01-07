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
from datetime import datetime
from functools import wraps
from threading import Semaphore

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
    def __call__(self, *args, **kwargs):
        filters = kwargs.get("filter", [])
        if filters:
            for _filter in filters:
                if hasattr(_filter, "end_time"):
                    # 暂时只对大于或大于等于进行索引范围收缩
                    gt_time = getattr(_filter.end_time, "gt", None) or getattr(_filter.end_time, "gte", None)
                    self._search.fix_index(gt_time)
        s = super().__call__(*args, **kwargs)
        return s


class EsSearch(Search):
    INDEX_PATTERN = re.compile(r".*_bkapm_trace_.+_(\d{8})_\d+$")

    query = ProxyDescriptor("es_query")
    post_filter = ProxyDescriptor("es_post_filter")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._es_query_proxy = EsQueryProxy(self, "query")
        self._es_post_filter_proxy = EsQueryProxy(self, "post_filter")

    def fix_index(self, gt_time: int):
        fixed_index_list = []
        # es索引以utc0时区时间为准创建
        gt_date_str = datetime.utcfromtimestamp(gt_time / 1000000).strftime('%Y%m%d')
        if self._index and isinstance(self._index, list):
            for _index_parts in self._index:
                _index_list = _index_parts.split(",")
                for _index in _index_list:
                    if self.check_index_date(_index, gt_date_str):
                        fixed_index_list.append(_index)
        if fixed_index_list:
            self._index = [",".join(fixed_index_list)]

    @classmethod
    def check_index_date(cls, index, gt_date_str):
        # 从索引名称中提取日期部分
        match = cls.INDEX_PATTERN.search(index)
        date_str = match.group(1) if match else None
        if not date_str:
            return False
        return int(date_str) >= int(gt_date_str)

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
