# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
import copy
import time

from apps.log_search.constants import CONTEXT_GSE_INDEX_SIZE
from apps.log_search.handlers.es.bk_mock_body import (
    BODY_DATA_FOR_CONTEXT,
    BODY_DATA_FOR_TAIL,
    BODY_DATA_FOR_TAIL_SCENARIO_ES,
    BODY_DATA_FOR_TAIL_SCENARIO_LOG,
)
from apps.log_search.utils import create_context_should_query


class DslCreateSearchContextBodyScenarioBkData(object):
    def __init__(self, **kwargs):
        """
        上下文查询构造请求参数
        sort_list, size, start, gse_index, iteration_idx,dt_event_time_stamp,
        path, ip, order, container_id=None, logfile=None
        """
        sort_list = kwargs.get("sort_list")
        size = kwargs.get("size")
        start = kwargs.get("start")
        gse_index = kwargs.get("gse_index")
        iteration_idx = kwargs.get("iteration_idx")
        dt_event_time_stamp = kwargs.get("dt_event_time_stamp")
        path = kwargs.get("path", "")
        ip = kwargs.get("ip", "")
        order = kwargs.get("order")
        container_id = kwargs.get("container_id", "")
        logfile = kwargs.get("logfile", "")
        bk_host_id = kwargs.get("bk_host_id", "")

        # 日志链路容器字段
        ext_container_id = kwargs.get("__ext", {}).get("container_id", "")

        self._body = None
        body_data = copy.deepcopy(BODY_DATA_FOR_CONTEXT)
        body_should_data = body_data["query"]["bool"]["should"]
        sort_fields = ["gseindex", "_iteration_idx", "dtEventTimeStamp"]
        sort_fields_value = [gse_index, iteration_idx, dt_event_time_stamp]
        order_use: str = "asc"

        # 根据排序方式构造查询语句
        if order == "-":
            order_use = "desc"
            create_context_should_query(order, body_should_data, sort_fields, sort_fields_value)
        if order == "+":
            create_context_should_query(order, body_should_data, sort_fields, sort_fields_value)

        sort = []
        for item in sort_fields:
            if item in sort_list:
                sort.append({item: {"order": order_use}})
        body_data["sort"] = sort
        if bk_host_id:
            body_data["query"]["bool"]["must"].append(
                {
                    "match": {
                        "bk_host_id": {
                            "query": bk_host_id,
                            "operator": "and",
                        }
                    }
                }
            )

        if ip != "":
            body_data["query"]["bool"]["must"].append(
                {
                    "match": {
                        "ip": {
                            "query": ip,
                            # "type": "phrase"
                            "operator": "and",
                        }
                    }
                }
            )

        if path != "":
            body_data["query"]["bool"]["must"].append(
                {
                    "match": {
                        "path": {
                            "query": path,
                            # "type": "phrase"
                            "operator": "and",
                        }
                    }
                }
            )

        if container_id and logfile:  # 这个是容器
            body_data["query"]["bool"]["must"] = [
                {
                    "match": {
                        "container_id": {
                            "query": container_id,
                            # "type": "phrase"
                            "operator": "and",
                        }
                    }
                },
                {
                    "match": {
                        "logfile": {
                            "query": logfile,
                            # "type": "phrase"
                            "operator": "and",
                        }
                    }
                },
            ]

        if ext_container_id:
            body_data["query"]["bool"]["must"].append(
                {
                    "match": {
                        "__ext.container_id": {
                            "query": ext_container_id,
                            "operator": "and",
                        }
                    }
                }
            )

        body_data["size"] = size

        body_data["from"] = abs(start)

        self._body = body_data

    @property
    def body(self):
        return self._body


class DslCreateSearchContextBodyScenarioLog(object):
    def __init__(self, **kwargs):
        """
        上下文查询构造请求参数
        sort_list, size, start, gse_index, iteration_index, dt_event_time_stamp,
        path, server_ip, order, container_id=None, logfile=None
        """
        sort_list = kwargs.get("sort_list")
        size = kwargs.get("size")
        start = kwargs.get("start")
        iteration_index = kwargs.get("iteration_index")
        gse_index = kwargs.get("gse_index")
        dt_event_time_stamp = kwargs.get("dt_event_time_stamp")
        path = kwargs.get("path")
        server_ip = kwargs.get("server_ip")
        bk_host_id = kwargs.get("bk_host_id")
        order = kwargs.get("order")

        self._body = None
        body_data = copy.deepcopy(BODY_DATA_FOR_CONTEXT)
        body_should_data = body_data["query"]["bool"]["should"]
        sort_fields = ["gseIndex", "iterationIndex", "dtEventTimeStamp"]
        sort_fields_value = [gse_index, iteration_index, dt_event_time_stamp]
        order_use: str = "asc"

        # 根据排序方式构造查询语句
        if order == "-":
            order_use = "desc"
            create_context_should_query(order, body_should_data, sort_fields, sort_fields_value)
        if order == "+":
            create_context_should_query(order, body_should_data, sort_fields, sort_fields_value)

        sort = []
        for item in sort_fields:
            if item in sort_list:
                sort.append({item: {"order": order_use}})
        body_data["sort"] = sort
        if bk_host_id:
            body_data["query"]["bool"]["must"].append(
                {
                    "match": {
                        "bk_host_id": {
                            "query": bk_host_id,
                            "operator": "and",
                        }
                    }
                }
            )
        body_data["query"]["bool"]["must"].append(
            {
                "match": {
                    "serverIp": {
                        "query": server_ip,
                        # "type": "phrase"
                        "operator": "and",
                    }
                }
            }
        )

        if path:
            body_data["query"]["bool"]["must"].append(
                {
                    "match": {
                        "path": {
                            "query": path,
                            # "type": "phrase"
                            "operator": "and",
                        }
                    }
                }
            )

        body_data["size"] = size

        body_data["from"] = abs(start)

        self._body = body_data

    @property
    def body(self):
        return self._body


class DslCreateSearchContextBodyCustomField:
    def __init__(self, **kwargs):
        """
        自定义字段上下文查询构造请求参数
        """
        size = kwargs.get("size")
        start = kwargs.get("start")
        order = kwargs.get("order")

        # 定位字段 排序字段
        target_fields: list = kwargs.get("target_fields", [])
        sort_fields: list = kwargs.get("sort_fields", [])

        params: dict = kwargs.get("params", {})

        self._body = None

        if not target_fields or not sort_fields:
            return

        # 把排序字段为空的字段剔除并记录非空字段的值
        sort_fields_value = []
        for _sort_field in sort_fields:
            _field_value = params.get(_sort_field, "")
            if _field_value == "":
                sort_fields.remove(_sort_field)
            else:
                sort_fields_value.append(_field_value)

        body_data = copy.deepcopy(BODY_DATA_FOR_CONTEXT)
        body_should_data = body_data["query"]["bool"]["should"]
        order_use: str = "asc"

        # 根据排序方式构造查询语句
        if order == "-":
            order_use = "desc"
            create_context_should_query(order, body_should_data, sort_fields, sort_fields_value)
        if order == "+":
            create_context_should_query(order, body_should_data, sort_fields, sort_fields_value)

        sort = []
        for item in sort_fields:
            sort.append({item: {"order": order_use}})
        body_data["sort"] = sort

        for item in target_fields:
            item_value = params.get(item)
            if item_value:
                body_data["query"]["bool"]["must"].append(
                    {
                        "match": {
                            item: {
                                "query": item_value,
                                "operator": "and",
                            }
                        }
                    }
                )

        body_data["size"] = size

        body_data["from"] = abs(start)

        self._body = body_data

    @property
    def body(self):
        return self._body


class DslCreateSearchTailBodyScenarioBkData:
    def __init__(self, **kwargs):
        """
        上下文查询构造请求参数
        sort_list, size, start, gseindex, path, ip, keyword
        """
        sort_list = kwargs.get("sort_list")
        size = kwargs.get("size")
        start = kwargs.get("start")
        gseindex = kwargs.get("gseindex")
        path = kwargs.get("path", "")
        ip = kwargs.get("ip", "")
        bk_host_id = kwargs.get("bk_host_id")
        container_id = kwargs.get("container_id", "")
        logfile = kwargs.get("logfile", "")
        zero = kwargs.get("zero", False)

        # 日志链路容器字段
        ext_container_id = kwargs.get("__ext", {}).get("container_id", "")

        self._body = None
        body_data = copy.deepcopy(BODY_DATA_FOR_TAIL)

        order_use: str = "asc"
        if zero:
            # 用当前时间往后前5分钟开始查询
            order_use = "desc"
            body_data["query"]["bool"]["filter"][0]["range"] = {
                "dtEventTimeStamp": {
                    "gte": int(time.time() * 1000) - 300000,
                    "lte": int(time.time() * 1000),
                    # "format": "epoch_millis"
                }
            }
        elif gseindex:
            body_data["query"]["bool"]["filter"][0]["range"]["gseindex"] = {
                "lt": int(gseindex) + CONTEXT_GSE_INDEX_SIZE,
                "gt": int(gseindex),
            }
        sort = []
        for item in sort_list:
            sort.append({item: {"order": order_use}})
        body_data["sort"] = sort
        if bk_host_id:
            body_data["query"]["bool"]["must"].append(
                {
                    "match": {
                        "bk_host_id": {
                            "query": bk_host_id,
                            "operator": "and",
                        }
                    }
                }
            )
        if ip != "":
            body_data["query"]["bool"]["must"].append(
                {
                    "match": {
                        "ip": {
                            "query": ip,
                            # "type": "phrase"
                            "operator": "and",
                        }
                    }
                }
            )
        if path != "":
            body_data["query"]["bool"]["must"].append(
                {
                    "match": {
                        "path": {
                            "query": path,
                            # "type": "phrase"
                            "operator": "and",
                        }
                    }
                }
            )

        if container_id and logfile:  # 这个是容器
            body_data["query"]["bool"]["must"] = [
                {
                    "match": {
                        "container_id": {
                            "query": container_id,
                            # "type": "phrase"
                            "operator": "and",
                        }
                    }
                },
                {
                    "match": {
                        "logfile": {
                            "query": logfile,
                            # "type": "phrase"
                            "operator": "and",
                        }
                    }
                },
            ]

        if ext_container_id:
            body_data["query"]["bool"]["must"].append(
                {
                    "match": {
                        "__ext.container_id": {
                            "query": ext_container_id,
                            "operator": "and",
                        }
                    }
                }
            )
        if size:
            body_data["size"] = size
        elif zero:
            body_data["size"] = 500
        else:
            body_data["size"] = 30
        body_data["from"] = start
        self._body = body_data

    @property
    def body(self):
        return self._body


class DslCreateSearchTailBodyScenarioLog:
    def __init__(self, **kwargs):
        """
        上下文查询构造请求参数
        sort_list, size, start, gseIndex, path, serverIp, keyword
        """
        sort_list = kwargs.get("sort_list")
        size = kwargs.get("size")
        start = kwargs.get("start")
        gse_index = kwargs.get("gseIndex")
        path = kwargs.get("path")
        server_ip = kwargs.get("serverIp")
        bk_host_id = kwargs.get("bk_host_id")
        zero = kwargs.get("zero", False)

        self._body = None
        body_data = copy.deepcopy(BODY_DATA_FOR_TAIL_SCENARIO_LOG)

        order_use: str = "asc"
        if zero:
            # 用当前时间往后前5分钟开始查询
            order_use = "desc"
            body_data["query"]["bool"]["filter"][0]["range"] = {
                "dtEventTimeStamp": {
                    "gte": int(time.time() * 1000) - 300000,
                    "lte": int(time.time() * 1000),
                    "format": "epoch_millis",
                }
            }
        elif gse_index:
            body_data["query"]["bool"]["filter"][0]["range"]["gseIndex"] = {
                "lt": int(gse_index) + CONTEXT_GSE_INDEX_SIZE,
                "gt": int(gse_index),
            }
        sort = []
        for item in sort_list:
            sort.append({item: {"order": order_use}})
        body_data["sort"] = sort
        if bk_host_id:
            body_data["query"]["bool"]["must"].append(
                {"match": {"bk_host_id": {"query": bk_host_id, "operator": "and"}}}
            )
        body_data["query"]["bool"]["must"].append({"match": {"serverIp": {"query": server_ip, "operator": "and"}}})
        if path:
            body_data["query"]["bool"]["must"].append({"match": {"path": {"query": path, "operator": "and"}}})

        if size:
            body_data["size"] = size
        elif zero:
            body_data["size"] = 500
        else:
            body_data["size"] = 30
        body_data["from"] = start
        self._body = body_data

    @property
    def body(self):
        return self._body


class DslCreateSearchTailBodyCustomField:
    def __init__(self, **kwargs):
        """
        自定义字段实时日志查询构造请求参数
        """
        size = kwargs.get("size")
        start = kwargs.get("start")
        zero = kwargs.get("zero", False)

        time_field: str = kwargs.get("time_field")

        # 定位字段 排序字段
        target_fields: list = kwargs.get("target_fields", [])
        sort_fields: list = kwargs.get("sort_fields", [])

        params: dict = kwargs.get("params", {})

        self._body = None

        if not target_fields or not sort_fields:
            return

        # 取优先级最高的字段为范围查询字段
        range_field = sort_fields[0]
        range_field_value: int = params.get(range_field, 0)

        self._body = None
        body_data = copy.deepcopy(BODY_DATA_FOR_TAIL_SCENARIO_ES)

        order_use: str = "asc"
        if zero:
            # 用当前时间往后前5分钟开始查询
            order_use = "desc"

            body_data["query"]["bool"]["filter"].append(
                {"range": {time_field: {"gte": int(time.time() * 1000) - 300000, "format": "epoch_millis"}}}
            )

        elif range_field_value:
            body_data["query"]["bool"]["filter"].append({"range": {range_field: {"gt": range_field_value}}})

        sort = []
        for item in sort_fields:
            sort.append({item: {"order": order_use}})

        body_data["sort"] = sort

        for item in target_fields:
            item_value = params.get(item)
            if item_value:
                body_data["query"]["bool"]["must"].append(
                    {
                        "match": {
                            item: {
                                "query": item_value,
                                "operator": "and",
                            }
                        }
                    }
                )
        if size:
            body_data["size"] = size
        elif zero:
            body_data["size"] = 500
        else:
            body_data["size"] = 30
        body_data["from"] = start

        self._body = body_data

    @property
    def body(self):
        return self._body
