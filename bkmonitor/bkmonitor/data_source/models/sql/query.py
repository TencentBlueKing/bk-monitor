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


from importlib import import_module

from django.db.models.sql import AND

from bkmonitor.data_source.models.sql.where import WhereNode
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api

DATA_SOURCE = {
    DataSourceLabel.BK_MONITOR_COLLECTOR: {
        DataTypeLabel.TIME_SERIES: {
            "query": api.metadata.get_ts_data,
            "backends": "bkmonitor.data_source.backends.time_series",
        },
        DataTypeLabel.LOG: {
            "query": api.metadata.get_es_data,
            "backends": "bkmonitor.data_source.backends.elastic_search",
        },
        DataTypeLabel.ALERT: {
            "query": None,
            "backends": "bkmonitor.data_source.backends.fta_event",
        },
    },
    DataSourceLabel.BK_DATA: {
        DataTypeLabel.TIME_SERIES: {
            "query": api.bkdata.query_data,
            "backends": "bkmonitor.data_source.backends.time_series",
        },
        DataTypeLabel.LOG: {"query": api.bkdata.query_data, "backends": "bkmonitor.data_source.backends.log"},
    },
    DataSourceLabel.BK_LOG_SEARCH: {
        DataTypeLabel.TIME_SERIES: {
            "query": api.log_search.es_query_search,
            "backends": "bkmonitor.data_source.backends.log_search",
        },
        DataTypeLabel.LOG: {
            "query": api.log_search.es_query_search,
            "backends": "bkmonitor.data_source.backends.log_search",
        },
    },
    DataSourceLabel.CUSTOM: {
        DataTypeLabel.EVENT: {
            "query": api.metadata.get_es_data,
            "backends": "bkmonitor.data_source.backends.elastic_search",
        },
        DataTypeLabel.TIME_SERIES: {
            "query": api.metadata.get_ts_data,
            "backends": "bkmonitor.data_source.backends.time_series",
        },
    },
    DataSourceLabel.BK_FTA: {
        DataTypeLabel.EVENT: {
            "query": None,
            "backends": "bkmonitor.data_source.backends.fta_event",
        },
        DataTypeLabel.ALERT: {
            "query": None,
            "backends": "bkmonitor.data_source.backends.fta_event",
        },
    },
    DataSourceLabel.BK_APM: {
        DataTypeLabel.TIME_SERIES: {
            "query": api.apm_api.query_es,
            "backends": "bkmonitor.data_source.backends.elastic_search",
        },
        DataTypeLabel.LOG: {
            "query": api.apm_api.query_es,
            "backends": "bkmonitor.data_source.backends.elastic_search",
        },
    },
}


def load_backends(using):
    data_source, data_type = using
    config = DATA_SOURCE.get(data_source, {}).get(data_type)
    query_func = config["query"]
    backend_name = config["backends"]
    try:
        return query_func, import_module("%s.connection" % backend_name)
    except ImportError:
        raise


class RawQuery(object):
    """
    A single raw SQL query
    """

    def __init__(self, sql, using=None, params=None):
        self.params = params or ()
        self.sql = sql

        self.using = using or (DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)

    def execute_query(self):
        sql = self.sql % self.params
        query_func, backend = load_backends(self.using)
        conn = backend.DatabaseConnection(query_func)
        return conn.execute(sql)


class Query(object):
    """
    A single SQL query.
    """

    compiler = "SQLCompiler"

    def __init__(self, using, where=WhereNode):
        self.select = []
        self.table_name = None
        self.where = where()
        self.where_class = where
        self.agg_condition = []
        self.group_by = []
        self.order_by = []
        self.low_mark, self.high_mark = 0, None  # Used for offset/limit
        self.slimit = None
        self.offset = None

        # dsl
        self.index_set_id = None
        self.raw_query_string = ""
        self.group_hits_size = 0
        self.time_field = ""
        self.event_group_id = ""
        self.target_type = "ip"
        self.using = using

    def __str__(self):
        sql, params = self.sql_with_params()
        return sql % params

    def clone(self):
        obj = self.__class__(using=self.using)
        obj.select = self.select[:]
        obj.table_name = self.table_name
        obj.where = self.where.clone()
        obj.where_class = self.where_class
        obj.group_by = self.group_by[:]
        obj.order_by = self.order_by[:]
        obj.time_field = self.time_field
        obj.target_type = self.target_type
        obj.agg_condition = self.agg_condition[:]
        obj.low_mark, obj.high_mark = self.low_mark, self.high_mark
        obj.slimit = self.slimit
        obj.offset = self.offset

        # dsl
        obj.index_set_id = self.index_set_id
        obj.raw_query_string = self.raw_query_string
        obj.event_group_id = self.event_group_id
        return obj

    def sql_with_params(self):
        """
        Returns the query as an SQL string
        """
        return self.get_compiler(self.using).as_sql()

    def get_compiler(self, using=None, connection=None):
        if using is None and connection is None:
            raise ValueError("Need either using or connection")
        if using:
            query_func, backend = load_backends(using)
            connection = backend.DatabaseConnection(query_func)
        return connection.ops.compiler(self.compiler)(self, connection, using)

    def add_select(self, col):
        if col and col.strip():
            self.select.append(col)

    def clear_select_fields(self):
        self.select = []

    def set_agg_condition(self, agg_condition):
        if agg_condition:
            self.agg_condition = agg_condition

    def set_time_field(self, time_field):
        if time_field:
            self.time_field = time_field

    def set_target_type(self, target_type):
        if target_type:
            self.target_type = target_type

    def set_offset(self, offset):
        if offset:
            self.offset = offset

    def add_q(self, q_object):
        self.where.add(q_object, AND)

    def add_ordering(self, *ordering):
        if ordering:
            self.order_by.extend([x for x in ordering if x and x.strip()])

    def add_grouping(self, *grouping):
        if grouping:
            self.group_by.extend([x for x in grouping if x and x.strip()])

    def set_limits(self, low=None, high=None):
        if high is not None:
            if self.high_mark is not None:
                self.high_mark = min(self.high_mark, self.low_mark + high)
            else:
                self.high_mark = self.low_mark + high
        if low is not None:
            if self.high_mark is not None:
                self.low_mark = min(self.high_mark, self.low_mark + low)
            else:
                self.low_mark = self.low_mark + low

    def set_slimit(self, s):
        self.slimit = s


class InsertQuery(Query):
    """
    TODO: Empty implements
    """

    compiler = "SQLInsertCompiler"

    def __init__(self, *args, **kwargs):
        super(InsertQuery, self).__init__(*args, **kwargs)
