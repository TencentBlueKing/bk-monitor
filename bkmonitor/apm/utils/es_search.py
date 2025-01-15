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
import time
from functools import wraps
from threading import Semaphore

from elasticsearch.helpers.errors import ScanError
from elasticsearch_dsl import Search
from elasticsearch_dsl.connections import get_connection

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


class EsSearch(Search):
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
