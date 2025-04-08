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
import copy

from apps.log_search.models import Scenario
from apps.log_unifyquery.constants import BODY_DATA_FOR_CONTEXT


def create_context_should_query(order, body_should_data, sort_fields, sort_fields_value):
    """
    上下文or查询参数构造
    请求参数
    :param order: 排序方式 -或+
    :param body_should_data: 父级查询参数
    :param sort_fields: 排序字段
    :param sort_fields_value: 排序字段对应的值
    """
    if order not in ["-", "+"]:
        return

    sort_fields_num = len(sort_fields)

    if order == "+":
        range_op = "gt" if sort_fields_num > 1 else "gte"
    else:
        range_op = "lt"

    # 需要进行term查询的字段
    term_fields = []
    # 构造查询语句
    for index, (range_field, range_field_value) in enumerate(zip(sort_fields, sort_fields_value)):
        if index == 0:
            body_should_data.append(
                {
                    "range": {
                        range_field: {
                            range_op: range_field_value,
                        }
                    }
                }
            )
        else:
            body_should_data.append(
                {
                    "bool": {
                        "filter": [
                            {"term": {_term_range_field["range_field"]: _term_range_field["range_field_value"]}}
                            for _term_range_field in term_fields
                        ]
                    }
                }
            )
            # 升序时最后一个字段操作符设置为大于等于
            if order == "+" and index + 1 == sort_fields_num:
                range_op = "gte"

            body_should_data[index]["bool"]["filter"].append(
                {
                    "range": {
                        range_field: {
                            range_op: range_field_value,
                        }
                    }
                }
            )
        term_fields.append({"range_field": range_field, "range_field_value": range_field_value})


def _get_context_body(self, order):
    target_fields = self.index_set.target_fields
    sort_fields = self.index_set.sort_fields

    if sort_fields:
        return CreateSearchContextBodyCustomField(
            size=self.size,
            start=self.start,
            order=order,
            target_fields=target_fields,
            sort_fields=sort_fields,
            params=self.search_dict,
        ).body

    elif self.scenario_id == Scenario.BKDATA:
        return CreateSearchContextBodyScenarioBkData(
            size=self.size,
            start=self.start,
            gse_index=self.gseindex,
            iteration_idx=self._iteration_idx,
            dt_event_time_stamp=self.dtEventTimeStamp,
            path=self.path,
            ip=self.ip,
            bk_host_id=self.bk_host_id,
            container_id=self.container_id,
            logfile=self.logfile,
            order=order,
            sort_list=["dtEventTimeStamp", "gseindex", "_iteration_idx"],
        ).body

    elif self.scenario_id == Scenario.LOG:
        return CreateSearchContextBodyScenarioLog(
            size=self.size,
            start=self.start,
            gse_index=self.gseIndex,
            iteration_index=self.iterationIndex,
            dt_event_time_stamp=self.dtEventTimeStamp,
            path=self.path,
            server_ip=self.serverIp,
            bk_host_id=self.bk_host_id,
            container_id=self.container_id,
            logfile=self.logfile,
            order=order,
            sort_list=["dtEventTimeStamp", "gseIndex", "iterationIndex"],
        ).body

    return {}


class CreateSearchContextBodyScenarioBkData(object):
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


class CreateSearchContextBodyScenarioLog(object):
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
        ext_container_id = kwargs.get("container_id", "")
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


class CreateSearchContextBodyCustomField:
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
        for _sort_field in sort_fields[:]:
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

        body_data["limit"] = size

        body_data["from"] = abs(start)

        self._body = body_data

    @property
    def body(self):
        return self._body
