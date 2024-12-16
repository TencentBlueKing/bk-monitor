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
"""
sql convert:
1. result_table -> <biz_id>, db_name, table_name
2. minuteX -> time:
    2.1 select
    2.2 group
    2.3 order
3. where condition:
    3.1 1m -> time.time()-60
    3.2 like/not like -> ~=/ !~
6. limit: max control
"""

import logging
import re
import time

import six
import sqlparse
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext as _
from influxdb.exceptions import InfluxDBClientError, InfluxDBServerError
from sqlparse import sql as S
from sqlparse import tokens as T
from sqlparse.sql import Parenthesis
from sqlparse.utils import imt

from kernel_api.adapters import API_FIELD_FORMATED_MAPPINGS
from metadata.models import ClusterInfo, ResultTable, TimeSeriesGroup
from query_api.drivers.influxdb.client import pool
from query_api.drivers.proxy import DriverProxy
from query_api.exceptions import SQLSyntaxError, StorageResultTableNotExist

MINUTE_X_REGEX = re.compile(r"mini?ute(\d+)$")

# bkdata结果表： <biz_id>_<db_name>_<table_name>
BKDATA_RT_REGEX = re.compile(r"^(?P<biz_id>\d+)_(?P<db_name>exporter_.+?|.+?)_(?P<table_name>.*)$")

# bkmonitor结果表：<biz_id>?_<db_name>.<table_name>
BKMONITOR_RT_REGEX = re.compile(r"^((?P<bk_biz_id>\d+)_)?(?P<db_name>exporter_.+?|.+?)\.(?P<table_name>.*)")

LIKE_KEYWORD_REGEX = re.compile(r"(NOT\s+)?(LIKE)", flags=re.IGNORECASE)

MAX_LIMIT = 50000

NM = 1000 * 1000000

logger = logging.getLogger("sql_parse")


CUSTOM_RT_MAP = {}


class InfluxDBDriver(DriverProxy):
    def __init__(self, sql, rt_instance=None):
        super(InfluxDBDriver, self).__init__(sql)

        self.minute_x = None
        self.minute_x_field = None
        self.db_name = None
        self.table_name = None
        self.connection_args = dict(time_out=30)
        # [username, password]
        self.auth_info = []

        self.__adapter_fields = list()
        self.__rt_instance = rt_instance

        self._process_select_items()
        self._process_result_table()
        self._process_minutex()
        if self.q.where_token:
            self._process_where_condition()
        self._process_limit()
        self._process_slimit()
        self._process_group_fields()
        self._build_sql()

    def _check_sql(self):
        if not self.q.select_items:
            raise SQLSyntaxError(_("语法错误: 查询字段不能为空"))

    def _build_sql(self):
        logger.info(">>> %s" % str(self.q.statement))

    @property
    def sql(self):
        return str(self.q.statement)

    def _gen_string_token(self, any_string):
        if not any_string:
            return None
        any_string = six.text_type(any_string)
        tokens = sqlparse.parse(any_string)[0].tokens
        if len(tokens) > 1:
            return S.TokenList(tokens)
        else:
            return tokens[0]

    def _delelte_token_self(self, token, parent=None):
        if parent is None:
            parent = token.parent
        where_idx = parent.token_index(token)
        del parent.tokens[where_idx]

    def _replace_token(self, token_or_list, value):
        # the value only can _replace_token only once
        # if you want replace more time, call self.q.refresh_token()
        if isinstance(token_or_list, (list, tuple)):
            token_num = len(token_or_list)
            if token_num < 1:
                return
            for idx, token in enumerate(token_or_list):
                if idx < token_num - 1:
                    self._replace_token(token, None)
                else:
                    # replace token_list end
                    self._replace_token(token, value)
                    return

        if isinstance(value, S.Token):
            new_token = value
        else:
            new_token = self._gen_string_token(value)
        if new_token:
            token_or_list.parent.insert_before(token_or_list, new_token)
        self._delelte_token_self(token_or_list)

    def _process_select_items(self):
        for idx, select_item in enumerate(self.q.select_items):
            if not isinstance(select_item, S.TokenList):
                continue

            if not select_item.has_alias():
                general_field_token = select_item
            else:
                general_field_token = select_item.tokens[0]
                alias_token = select_item.tokens[-1]
                alias_name = alias_token.value.strip("`").strip("'").strip('"')
                self._replace_token(alias_token, '"%s"' % alias_name)

            while isinstance(general_field_token, S.Function):
                idx, turbid_field_token = general_field_token.token_next_by(i=S.Parenthesis)
                _, func_token = general_field_token.token_prev(idx)
                if func_token.value.upper() == "AVG":
                    self._replace_token(func_token, "MEAN")

                _, field_token = turbid_field_token.token_next(0)
                general_field_token = field_token
            else:
                field_token = general_field_token
                if field_token.is_group:
                    field_token = field_token.token_first()

                field_name = field_token.value.strip("`").strip("'").strip('"')
                if field_name != "*":
                    self._replace_token(field_token, '"%s"' % field_name)

    def _process_group_fields(self):
        for group_field_token in self.q.group_items:
            origin_group_field = group_field_token.value.lower()
            if origin_group_field in API_FIELD_FORMATED_MAPPINGS:
                alias_group_field = API_FIELD_FORMATED_MAPPINGS[origin_group_field]
                self.__adapter_fields.append((origin_group_field, alias_group_field))
                self._replace_token(group_field_token, alias_group_field)

    def _process_result_table(self):
        global CUSTOM_RT_MAP
        # get table、database info from meta
        if self.__rt_instance is None:
            self.__rt_instance = self.get_result_table_instance()

        try:
            rt_info = ResultTable.get_result_table_storage_info(self.__rt_instance.table_id, ClusterInfo.TYPE_INFLUXDB)
        except ObjectDoesNotExist:
            raise StorageResultTableNotExist(_("结果表[%s]对应的物理存储不存在") % self.q.result_table.value)

        cluster_info = rt_info["cluster_config"]
        storage_info = rt_info["storage_config"]
        cluster_info["host"] = cluster_info.pop("domain_name")
        self.connection_args.update(cluster_info)
        if "auth_info" in rt_info:
            self.auth_info = [rt_info["auth_info"].get(key, "") for key in ["username", "password"]]
        table_name = storage_info["real_table_name"]
        retention_policy_name = storage_info["retention_policy_name"]
        self.table_name = '"{}".{}'.format(retention_policy_name, table_name) if retention_policy_name else table_name
        self.db_name = storage_info["database"]

        rt_id = self.q.result_table.value.lower()
        match = BKDATA_RT_REGEX.match(rt_id) or BKMONITOR_RT_REGEX.match(rt_id)
        if not match:
            raise SQLSyntaxError(_("无效的rt表名"))
        match_info = match.groupdict()
        insert_where_filter = {}

        # 自定义时序数据表不自动注入业务过滤
        if "biz_id" in match_info:
            if rt_id in CUSTOM_RT_MAP:
                is_custom_series_rt = CUSTOM_RT_MAP[rt_id]
            else:
                is_custom_series_rt = TimeSeriesGroup.objects.filter(table_id=self.__rt_instance.table_id).exists()
                CUSTOM_RT_MAP[rt_id] = is_custom_series_rt

            if not is_custom_series_rt:
                # add biz_id into where
                bk_biz_id = match_info["biz_id"]
                insert_where_filter["bk_biz_id"] = bk_biz_id

        if self.__rt_instance.schema_type == ResultTable.SCHEMA_TYPE_FREE:
            # 动态字段解析
            if not ResultTable.is_disable_metric_cutter(self.__rt_instance.table_id):
                insert_where_filter.update(self._handle_free_schema_sql())

        if insert_where_filter:
            self.add_where_condition(insert_where_filter)
        self._replace_token(self.q.result_table, self.table_name)

    def _handle_free_schema_sql(self):
        """
        处理动态schema结构的表的查询
        :return: 过滤条件组成的字段
        """
        if not len(self.q.select_items) == 1:
            raise SQLSyntaxError(_("动态字段表查询的指标项最多只能指定一个"))

        select_item = self.q.select_items[0]
        self.field_name = ""
        if not isinstance(select_item, S.TokenList):
            # 无效的select 语句
            return {}

        if not select_item.has_alias():
            field_token = select_item
        else:
            field_token = select_item.tokens[0]

        if isinstance(field_token, S.Function):
            no_use, field_token = field_token.token_next_by(i=S.Parenthesis)
            no_use, field_token = field_token.token_next(0)
            if field_token.is_group:
                field_token = field_token.token_first()

        self.field_name = field_token.value.strip("`").strip('"').strip("'")
        if self.field_name == "*":
            return {}

        self._replace_token(field_token, self._gen_string_token("metric_value"))
        # add where
        return {"metric_name": self.field_name}

    def _handle_free_schema_ret(self, data_list):
        # process select item contain [*]
        # add some code here
        return data_list

    def add_where_condition(self, where_condition_dict):
        """
        添加新的过滤条件
        :param where_condition_dict: 过滤条件组成的字典
        :return: None
        """

        def gen_where_sql(field, value):
            # 仅支持等于条件
            if isinstance(value, six.string_types):
                return "{}='{}'".format(field, value)
            return "{}={}".format(field, value)

        where_sql = " and ".join([gen_where_sql(k, v) for k, v in list(where_condition_dict.items())])

        if self.q.where_token:
            idx = len(self.q.where_token.tokens)
            self.q.where_token.insert_before(idx, self._gen_string_token(" and %s " % where_sql))
        else:
            where_token = self._gen_string_token(" where %s " % where_sql)
            self.q.statement.insert_after(self.q.result_table, where_token)

    @classmethod
    def _get_select_field_name(cls, select_field_token):
        field_name = select_field_token.value
        if select_field_token.is_group and select_field_token.has_alias():
            field_name = select_field_token.token_first().value
        return field_name

    def _process_minutex(self):
        self._process_minutex_items(self.q.select_items, "select", fn_get_item_name=self._get_select_field_name)

        self._process_minutex_items(
            self.q.group_items, "group", fn_get_time_field_name=lambda minute_x: "time(%dm)" % minute_x
        )

        if self.q.order_items:
            self._process_minutex_items(self.q.order_items, "order")

    def _process_minutex_items(self, items, item_type, fn_get_item_name=None, fn_get_time_field_name=None):
        """
        :param items: field_token
        :param item_type:  select/group/order
        :param fn_get_item_name: get_field_token_value function
        :param fn_get_time_field_name: get_time_field_name function
        :return:
        """
        if fn_get_item_name is None:

            def fn_get_item_name(_item):
                return _item.value

        if fn_get_time_field_name is None:

            def fn_get_time_field_name(minute_x):
                return "time"

        minute_count = 0
        for item in items:
            item_name = fn_get_item_name(item)
            if item_name.lower() == "time":
                minute_count += 1
                continue

            pattern = MINUTE_X_REGEX.match(item_name)
            if pattern:
                if item.has_alias():
                    raise SQLSyntaxError(_("minuteX字段不能设置别名"))
                if self.minute_x and self.minute_x != int(pattern.group(1)):
                    raise SQLSyntaxError(_("minuteX字段必须保持一致"))
                self.minute_x = int(pattern.group(1))
                self.minute_x_field = item_name
                minute_count += 1
                self._replace_token(item, fn_get_time_field_name(self.minute_x))

        if minute_count > 1:
            raise SQLSyntaxError(six.text_type(_("%s只能使用一个minuteX/time字段") % item_type.upper()))

    def _process_where_condition(self, where_token=None):
        where_token = where_token or self.q.where_token

        tidx = 0
        while tidx is not None:
            # process time field
            tidx, comparison_token = where_token.token_next_by(i=Parenthesis, t=T.Comparison, idx=tidx)
            if isinstance(comparison_token, Parenthesis):
                self._process_where_condition(comparison_token)
                continue

            if comparison_token:
                _, where_field = where_token.token_prev(tidx)
                _, value_token = where_token.token_next(tidx)

                if re.match(r"(?i)^time$", where_field.value):
                    # process time field
                    if re.match(r"^'(\d+)(m|h|d)'|'today'", value_token.value):
                        self._process_time_alias(value_token)

                    if imt(value_token, t=T.Number):
                        self._format_timestamps(value_token)

                    tidx, token = where_token.token_next_by(m=(T.Token.Keyword, r"(?i)^time$", True), idx=tidx)

        # process adapter_fields
        for condition_token in where_token.get_sublists():
            where_field = getattr(condition_token, "left", None)
            if where_field is not None:
                origin_where_field = where_field.value.lower()
                if origin_where_field in API_FIELD_FORMATED_MAPPINGS:
                    self._replace_token(condition_token.left, API_FIELD_FORMATED_MAPPINGS[origin_where_field])
                # process `LIKE`/`NOT LIKE`
                ret = LIKE_KEYWORD_REGEX.match(condition_token.token_next(0)[1].value)
                if ret:
                    like_token = condition_token.token_next(0)[1]
                    like_value_token = condition_token.right
                    self._process_like_value(like_value_token)
                    if ret.groups()[0]:
                        # NOT LIKE
                        self._replace_token(like_token, S.Token(T.Token.Operator.Comparison, "!~"))
                    else:
                        # LIKE
                        self._replace_token(like_token, S.Token(T.Token.Operator.Comparison, "=~"))

    def _process_like_value(self, like_value_token):
        value = like_value_token.value.replace("'%", "/").replace("%'", "/")
        if value.startswith("/"):
            value = value
        else:
            value = "/^%s" % value.replace("'", "", 1)

        if value.endswith("/"):
            value = value
        else:
            value = "%s$/" % value[: len(value) - 1]

        self._replace_token(like_value_token, value)

    def _format_timestamps(self, timestamps_token):
        # format all ms to ns
        value = timestamps_token.value.ljust(19, "0")
        self._replace_token(timestamps_token, value)

    def _process_time_alias(self, time_alias_token):
        # called with re match
        value = time_alias_token.value
        replaced_timestamp = None
        if value == "'today'":
            replaced_timestamp = (
                int(
                    time.mktime(
                        time.strptime(
                            time.strftime("%Y-%m-%d 00:00:00", time.localtime(time.time())), "%Y-%m-%d %H:%M:%S"
                        )
                    )
                )
                * NM
            )
        else:
            _rematch = re.search(r"^'(\d+)(m|h|d)'", value)
            _number, _unit = int(_rematch.group(1)), _rematch.group(2)
            if _unit == "h":
                replaced_timestamp = (int(time.time()) - _number * 60 * 60) * NM
            elif _unit == "m":
                # 基于分钟需要取整
                replaced_timestamp = (int(time.time()) // 60 * 60 - _number * 60) * NM
            elif _unit == "d":
                replaced_timestamp = (int(time.time()) - _number * 60 * 60 * 24) * NM

        self._replace_token(time_alias_token, replaced_timestamp)

    def _process_limit(self):
        if not self.q.limit_item:
            return

        try:
            limit_nums = [int(x.strip()) for x in self.q.limit_item.value.split(",")]
        except ValueError:
            raise SQLSyntaxError("`LIMIT` syntax error.")

        if len(limit_nums) > 2:
            raise SQLSyntaxError("`LIMIT` allows only one" " value to be specified.")

        limit_value = min(limit_nums[-1], settings.SQL_MAX_LIMIT)

        if self.q.limit_item:
            self._replace_token(self.q.limit_item, limit_value)

    def _process_slimit(self):
        if not self.q.slimit_item:
            # 5w条线，不能再多了
            slimit_token = self._gen_string_token(" slimit %d" % MAX_LIMIT)
            self.q.statement.insert_after(len(self.q.statement.tokens), slimit_token)
            return

        try:
            slimit_nums = [int(x.strip()) for x in self.q.slimit_item.value.split(",")]
        except ValueError:
            raise SQLSyntaxError("`SLIMIT` syntax error.")

        if len(slimit_nums) > 2:
            raise SQLSyntaxError("`SLIMIT` allows only one" " value to be specified.")

        slimit_value = min(slimit_nums[-1], MAX_LIMIT)

        if self.q.slimit_item:
            self._replace_token(self.q.slimit_item, slimit_value)

    def query(self):
        start_mark = time.time()
        sql = self.sql
        try:
            query_client = pool.get_client(**self.connection_args)
            if self.auth_info:
                query_client.switch_user(*self.auth_info)
            _result = []
            rt = {"list": _result, "totalRecords": 0, "timetaken": 0, "device": ClusterInfo.TYPE_INFLUXDB}
            query_client._headers.update({"Content-Type": "application/json", "Accept": "application/json"})
            result_set = query_client.query(sql, database=self.db_name, epoch="ms") or {}
        except (InfluxDBServerError, InfluxDBClientError) as e:
            logger.exception("influxdb query error: %s" % self.__dict__)
            raise e
        for key, _r in list(result_set.items()):
            measurement, series_name = key  # noqa
            series_name = series_name or {}
            if series_name:
                for origin, alias in self.__adapter_fields:
                    if alias in series_name:
                        series_name[origin] = series_name.pop(alias)

            for x in _r:
                x.update(series_name)
                if self.minute_x_field:
                    x[self.minute_x_field] = x["time"]
                _result.append(x)
        rt["list"] = _result
        rt["totalRecords"] = len(_result)
        rt["timetaken"] = time.time() - start_mark
        return rt


def load_driver(sql):
    return InfluxDBDriver(sql)
