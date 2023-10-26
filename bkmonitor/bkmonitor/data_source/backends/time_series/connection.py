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


import logging

from opentelemetry import trace
from pymysql.converters import escape_item, escape_string

from bkmonitor.data_source.backends.base.connection import BaseDatabaseConnection

from .operations import DatabaseOperations

logger = logging.getLogger("bkmonitor.data_source.time_series")
tracer = trace.get_tracer(__name__)
DEFAULT_CHARSET = "utf8"


class DatabaseConnection(BaseDatabaseConnection):
    vendor = "time_series"
    prefer_storage = "tsdb"

    operators = {
        "exact": "= %s",
        "eq": "= %s",
        "neq": "!= %s",
        "!=": "!= %s",
        "gt": "> %s",
        "gte": ">= %s",
        "lt": "< %s",
        "lte": "<= %s",
        "contains": "LIKE %s",
        "reg": "=~ %s",
        "nreg": "!~ %s",
    }

    def __init__(self, query_func, charset=""):
        self.query_func = query_func
        self.charset = charset or DEFAULT_CHARSET
        self.ops = DatabaseOperations(self)

    def execute(self, sql, params):
        params = tuple(self.escape(arg) for arg in params)
        sql_str = sql % params
        logger.info("BKSQL QUERY: %s" % sql_str)
        with tracer.start_as_current_span("bksql") as span:
            span.set_attribute("bk.system", "bksql")
            span.set_attribute("bk.bksql.statement", sql_str)
            result = self.query_func(sql=sql_str, prefer_storage="")
            return result.get("list")

    def escape(self, obj, mapping=None):
        """Escape whatever value you pass to it"""
        if isinstance(obj, str):
            fill_char = "'"
            if getattr(obj, "is_regex", False):
                # regex ignore escape
                fill_char = ""
            else:
                obj = escape_string(obj)
            return fill_char + obj + fill_char
        return escape_item(obj, self.charset, mapping=mapping)
