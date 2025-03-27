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
import time


class UnifyQueryDslCreateSearchTailBodyScenarioBkData:
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
        base_params = kwargs.get("base_params")

        # 日志链路容器字段
        ext_container_id = kwargs.get("__ext", {}).get("container_id", "")

        self._body = None

        order_use: str = "asc"
        if zero:
            # 用当前时间往后前5分钟开始查询
            order_use = "desc"
            base_params["start_time"] = int(time.time() * 1000) - 300000
            base_params["end_time"] = int(time.time() * 1000)
        elif gseindex:
            base_params["start_time"] = int(time.time() * 1000) - 300000 * 12
            base_params["end_time"] = int(time.time() * 1000)
            base_params["query_list"][0]["conditions"]["field_list"].append(
                {
                    "field_name": "gseIndex",
                    "op": "gt",
                    "value": [str(gseindex)],
                }
            )
        sort = []
        for item in sort_list:
            if order_use == "asc":
                sort.append(f"{item}")
            elif order_use == "desc":
                sort.append(f"-{item}")
        base_params["order_by"] = sort
        if bk_host_id:
            base_params["query_list"][0]["conditions"]["field_list"].append(
                {
                    "field_name": "bk_host_id",
                    "op": "eq",
                    "value": [str(bk_host_id)],
                }
            )
        if ip != "":
            base_params["query_list"][0]["conditions"]["field_list"].append(
                {
                    "field_name": "ip",
                    "op": "eq",
                    "value": [str(ip)],
                }
            )
        if path != "":
            base_params["query_list"][0]["conditions"]["field_list"].append(
                {
                    "field_name": "path",
                    "op": "eq",
                    "value": [str(path)],
                }
            )

        if container_id and logfile:  # 这个是容器
            base_params["query_list"][0]["conditions"]["field_list"] = [
                {
                    "field_name": "container_id",
                    "op": "eq",
                    "value": [str(container_id)],
                },
                {
                    "field_name": "logfile",
                    "op": "eq",
                    "value": [str(logfile)],
                },
            ]

        if ext_container_id:
            base_params["query_list"][0]["conditions"]["field_list"].append(
                {
                    "field_name": "__ext.container_id",
                    "op": "eq",
                    "value": [str(ext_container_id)],
                }
            )

        field_list_len = len(base_params["query_list"][0]["conditions"]["field_list"])
        if field_list_len > 1:
            base_params["query_list"][0]["conditions"]["condition_list"] = ["and" for _ in range(field_list_len - 1)]

        if size:
            base_params["limit"] = size
        elif zero:
            base_params["limit"] = 500
        else:
            base_params["limit"] = 30
        base_params["from"] = start
        self._body = base_params

    @property
    def body(self):
        return self._body


class UnifyQueryDslCreateSearchTailBodyScenarioLog:
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
        ext_container_id = kwargs.get("container_id", "")
        base_params = kwargs.get("base_params")

        self._body = None

        order_use: str = "asc"
        if zero:
            # 用当前时间往后前5分钟开始查询
            order_use = "desc"
            base_params["start_time"] = int(time.time() * 1000) - 300000
            base_params["end_time"] = int(time.time() * 1000)
        elif gse_index:
            base_params["start_time"] = int(time.time() * 1000) - 300000 * 12
            base_params["end_time"] = int(time.time() * 1000)
            base_params["query_list"][0]["conditions"]["field_list"].append(
                {
                    "field_name": "gseIndex",
                    "op": "gt",
                    "value": [str(gse_index)],
                }
            )
        sort = []
        for item in sort_list:
            if order_use == "asc":
                sort.append(f"{item}")
            elif order_use == "desc":
                sort.append(f"-{item}")
        base_params["order_by"] = sort
        if bk_host_id:
            base_params["query_list"][0]["conditions"]["field_list"].append(
                {
                    "field_name": "bk_host_id",
                    "op": "eq",
                    "value": [str(bk_host_id)],
                }
            )
        base_params["query_list"][0]["conditions"]["field_list"].append(
            {
                "field_name": "serverIp",
                "op": "eq",
                "value": [str(server_ip)],
            }
        )
        if path:
            base_params["query_list"][0]["conditions"]["field_list"].append(
                {
                    "field_name": "path",
                    "op": "eq",
                    "value": [str(path)],
                }
            )
            base_params["query_list"][0]["conditions"]["condition_list"] = ["and"]
        if ext_container_id:
            base_params["query_list"][0]["conditions"]["field_list"].append(
                {
                    "field_name": "__ext.container_id",
                    "op": "eq",
                    "value": [str(ext_container_id)],
                }
            )

        field_list_len = len(base_params["query_list"][0]["conditions"]["field_list"])
        if field_list_len > 1:
            base_params["query_list"][0]["conditions"]["condition_list"] = ["and" for _ in range(field_list_len - 1)]

        if size:
            base_params["limit"] = size
        elif zero:
            base_params["limit"] = 500
        else:
            base_params["limit"] = 30
        base_params["from"] = start
        self._body = base_params

    @property
    def body(self):
        return self._body


class UnifyQueryDslCreateSearchTailBodyCustomField:
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
        base_params = kwargs.get("base_params")

        base_params["query_list"][0]["time_field"] = time_field

        self._body = None

        if not target_fields or not sort_fields:
            return

        # 取优先级最高的字段为范围查询字段
        range_field = sort_fields[0]
        range_field_value: int = params.get(range_field, 0)

        self._body = None

        order_use: str = "asc"
        if zero:
            # 用当前时间往后前5分钟开始查询
            order_use = "desc"

            base_params["start_time"] = int(time.time() * 1000) - 300000
            base_params["end_time"] = int(time.time() * 1000)

        elif range_field_value:
            base_params["start_time"] = int(time.time() * 1000) - 300000 * 12
            base_params["end_time"] = int(time.time() * 1000)
            base_params["query_list"][0]["conditions"]["field_list"].append(
                {
                    "field_name": range_field,
                    "op": "gt",
                    "value": [str(range_field_value)],
                }
            )

        sort = []
        for item in sort_fields:
            if order_use == "asc":
                sort.append(f"{item}")
            elif order_use == "desc":
                sort.append(f"-{item}")
        base_params["order_by"] = sort

        for item in target_fields:
            item_value = params.get(item)
            if item_value:
                base_params["query_list"][0]["conditions"]["field_list"].append(
                    {
                        "field_name": item,
                        "op": "eq",
                        "value": [str(item_value)],
                    }
                )

        field_list_len = len(base_params["query_list"][0]["conditions"]["field_list"])
        if field_list_len > 1:
            base_params["query_list"][0]["conditions"]["condition_list"] = ["and" for _ in range(field_list_len - 1)]

        if size:
            base_params["limit"] = size
        elif zero:
            base_params["limit"] = 500
        else:
            base_params["limit"] = 30
        base_params["from"] = start
        self._body = base_params

    @property
    def body(self):
        return self._body
