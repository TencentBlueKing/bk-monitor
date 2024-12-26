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
import re

from django.utils.translation import gettext as _

from metadata.models import ResultTable
from query_api.exceptions import (
    ResultTableNotExist,
    SQLSyntaxError,
    StorageNotSupported,
    StorageResultTableNotExist,
)
from query_api.sql_parse.statement import SQLStatement

logger = logging.getLogger("query")


# bkdata结果表： <biz_id>_<db_name>_<table_name>
BKDATA_RT_REGEX = re.compile(r"^(?P<biz_id>\d+)_(?P<db_name>exporter_.+?|.+?)_(?P<table_name>.*)$")

# bkmonitor结果表：<biz_id>?_<db_name>.<table_name>
BKMONITOR_RT_REGEX = re.compile(r"^((?P<bk_biz_id>\d+)_)?(?P<db_name>exporter_.+?|.+?)\.(?P<table_name>.*)")


class DriverProxy(object):
    def __init__(self, origin_sql):
        if isinstance(origin_sql, SQLStatement):
            self.q = origin_sql
        else:
            self.q = SQLStatement(origin_sql)
        self._check_sql()

    def _check_sql(self):
        if not self.q.select_items:
            raise SQLSyntaxError(_("语法错误: 查询字段不能为空"))

    def get_result_table_instance(self):
        # get table、database info from meta
        rt_id = self.q.result_table.value.lower()
        try:
            rt_instance = ResultTable.get_result_table(rt_id)
        except ResultTable.DoesNotExist:
            raise ResultTableNotExist(_("结果表[%s]不存在") % self.q.result_table.value)

        return rt_instance


def load_driver_by_sql(sql):
    proxy = DriverProxy(sql)
    rt_instance = proxy.get_result_table_instance()
    if not rt_instance.default_storage:
        raise StorageResultTableNotExist(_("结果表[%s]未配置物理存储") % rt_instance.table_id)
    try:
        driver_module = __import__("query_api.drivers.%s" % rt_instance.default_storage, fromlist=["load_driver"])
    except (ImportError, ValueError):
        raise StorageNotSupported(_("存储[%s]对应的查询引擎不存在") % rt_instance.default_storage)
    return driver_module.load_driver(proxy.q)
