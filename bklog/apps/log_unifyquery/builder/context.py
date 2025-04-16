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

import arrow


def build_context_params(params):
    time_now = arrow.utcnow()
    params["end_time"] = int(time_now.timestamp())
    params["start_time"] = int(time_now.shift(days=-7).timestamp())
    params["index_set_ids"] = [params["index_set_id"]]
    return params


def create_context_conditions(order, sort_fields, sort_fields_value, and_conditions=None):
    """
    上下文or查询参数构造
    请求参数
    :param order: 排序方式 -或+
    :param sort_fields: 排序字段
    :param sort_fields_value: 排序字段对应的值
    :param and_conditions: 需要与每个主条件分支用 AND 连接的额外条件
    """
    if order not in ["-", "+"]:
        return {}

    conditions = {
        "field_list": [],
        "condition_list": []
    }

    op_map = {
        "+": {"range_op": "gt", "term_op": "eq"},
        "-": {"range_op": "lt", "term_op": "eq"}
    }

    # 生成主条件模板
    main_conditions = []
    for idx, (field, value) in enumerate(zip(sort_fields, sort_fields_value)):
        condition_group = []
        # 添加前序字段的精确匹配
        for prev_field, prev_value in zip(sort_fields[:idx], sort_fields_value[:idx]):
            condition_group.append({
                "field_name": prev_field,
                "op": op_map[order]["term_op"],
                "value": [str(prev_value)]
            })
        # 添加当前字段的范围条件
        current_op = "gte" if (order == "+" and idx == len(sort_fields) - 1) else op_map[order]["range_op"]
        condition_group.append({
            "field_name": field,
            "op": current_op,
            "value": [str(value)]
        })
        main_conditions.append(condition_group)

    # 将 AND 条件嵌套到每个主条件分支
    for group_idx, group in enumerate(main_conditions):
        # 添加主条件字段
        conditions["field_list"].extend(group)

        # 添加主条件内部连接符（前序字段间用 AND）
        if len(group) > 1:
            conditions["condition_list"].extend(["and"] * (len(group) - 1))

        # 添加 AND 条件到当前主条件分支
        if and_conditions:
            # 主条件与 AND 条件之间用 AND 连接
            if group:
                conditions["condition_list"].append("and")

            # 添加 AND 条件字段
            conditions["field_list"].extend(and_conditions)

            # 添加 AND 条件内部连接符
            if len(and_conditions) > 1:
                conditions["condition_list"].extend(["and"] * (len(and_conditions) - 1))

        # 添加主条件之间的 OR 连接（非第一个分支）
        if group_idx < len(main_conditions) - 1:
            conditions["condition_list"].append("or")

    return conditions


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
        body_data = kwargs.get("body_data", {})

        # 日志链路容器字段
        ext_container_id = kwargs.get("__ext", {}).get("container_id", "")

        self._body = None
        and_conditions = []
        sort_fields = ["gseindex", "_iteration_idx", "dtEventTimeStamp"]
        sort_fields_value = [gse_index, iteration_idx, dt_event_time_stamp]

        # 排序
        sort = []
        for item in sort_fields:
            if item in sort_list:
                if order == "+":
                    sort.append(f"{item}")
                else:
                    sort.append(f"-{item}")
        body_data["order_by"] = sort

        if bk_host_id:
            and_conditions.append(
                {
                    "field_name": "bk_host_id",
                    "op": "eq",
                    "value": [str(bk_host_id)]
                }
            )

        if ip != "":
            and_conditions.append(
                {
                    "field_name": "ip",
                    "op": "eq",
                    "value": [str(ip)]
                }
            )

        if path != "":
            and_conditions.append(
                {
                    "field_name": "path",
                    "op": "eq",
                    "value": [str(path)]
                }
            )

        if container_id and logfile:  # 这个是容器
            and_conditions.extend([
                {
                    "field_name": "container_id",
                    "op": "eq",
                    "value": [str(container_id)]
                },
                {
                    "field_name": "logfile",
                    "op": "eq",
                    "value": [str(logfile)]
                },
            ])

        if ext_container_id:
            and_conditions.append(
                {
                    "field_name": "__ext.container_id",
                    "op": "eq",
                    "value": [str(ext_container_id)]
                }
            )

        # 根据排序方式构造查询条件
        body_data["query_list"][0]["conditions"] = create_context_conditions(order, sort_fields, sort_fields_value,
                                                                             and_conditions)

        body_data["limit"] = size

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
        body_data = kwargs.get("body_data", {})

        self._body = None
        and_conditions = []
        sort_fields = ["gseIndex", "iterationIndex", "dtEventTimeStamp"]
        sort_fields_value = [gse_index, iteration_index, dt_event_time_stamp]

        # 根据排序方式构造查询语句
        sort = []
        for item in sort_fields:
            if item in sort_list:
                if order == "+":
                    sort.append(f"{item}")
                else:
                    sort.append(f"-{item}")
        body_data["order_by"] = sort

        if bk_host_id:
            and_conditions.append(
                {
                    "field_name": "bk_host_id",
                    "op": "eq",
                    "value": [str(bk_host_id)]
                }
            )
        and_conditions.append(
            {
                "field_name": "serverIp",
                "op": "eq",
                "value": [str(server_ip)]
            }
        )

        if path:
            and_conditions.append(
                {
                    "field_name": "path",
                    "op": "eq",
                    "value": [str(path)]
                }
            )

        if ext_container_id:
            and_conditions.append(
                {
                    "field_name": "__ext.container_id",
                    "op": "eq",
                    "value": [str(ext_container_id)]
                }
            )

        # 根据排序方式构造查询条件
        body_data["query_list"][0]["conditions"] = create_context_conditions(order, sort_fields, sort_fields_value,
                                                                             and_conditions)

        body_data["limit"] = size

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
