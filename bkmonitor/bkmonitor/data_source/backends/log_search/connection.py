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
import json
import logging

from opentelemetry import trace
from bkmonitor.data_source.backends.base.connection import BaseDatabaseConnection

from .operations import DatabaseOperations

logger = logging.getLogger("bkmonitor.data_source.log_search")
tracer = trace.get_tracer(__name__)
DEFAULT_CHARSET = "utf8"


class DatabaseConnection(BaseDatabaseConnection):
    vendor = "log_search"
    prefer_storage = "es"

    operators = {
        "is": "is",
        "is one of": "is one of",
        "is not": "is not",
        "is not one of": "is not one of",
    }

    def __init__(self, query_func, charset=""):
        self.query_func = query_func
        self.charset = charset or DEFAULT_CHARSET
        self.ops = DatabaseOperations(self)

    def execute(self, sql, params):
        logger.info("LOG SEARCH QUERY: %s" % params)
        with tracer.start_as_current_span("bk_log_search") as span:
            span.set_attribute("bk.system", "bk_log_search")
            span.set_attribute("bk.bk_log_search.statement", json.dumps(params))
            return self.query_func(**params)
