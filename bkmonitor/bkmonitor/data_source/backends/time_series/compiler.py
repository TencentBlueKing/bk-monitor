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
from functools import reduce

from django.db.models import Q
from django.db.models.sql import AND, OR

from bkmonitor.data_source.backends.base import compiler
from constants.data_source import DataSourceLabel


def escape_sql_field_name(field_name):
    for k in ["`", " ", "(", ")"]:
        if k in field_name:
            return field_name
    return "`%s`" % field_name


class SQLCompiler(compiler.SQLCompiler):
    def as_sql(self):
        result = ["SELECT"]

        select_fields = self.query.select[:]
        data_source, data_type = self.query.using
        if data_source == DataSourceLabel.BK_DATA:
            # if using bk_data
            # must add group_by_fields + time_fields into select_fields
            if self.query.time_field:
                select_fields += self.query.group_by + [
                    "MAX(%(field)s) as %(field)s" % dict(field=self.query.time_field),
                ]
        out_cols = sorted(set(select_fields), key=select_fields.index)
        if out_cols:
            result.append(", ".join([escape_sql_field_name(col) for col in out_cols]))
        else:
            result.append("*")

        result.append("FROM")
        if not self.query.table_name:
            raise Exception("SQL Error: Empty table name")
        result.append(self.query.table_name)

        clone_where = self.query.where.clone()
        q_object = self._parse_agg_condition()
        if q_object:
            clone_where.add(q_object, AND)
        params = []
        where, w_params = self.compile(clone_where)
        if where:
            result.append("WHERE %s" % where)
            params.extend(w_params)

        group_by_fields = self.query.group_by
        group_by = sorted(set(group_by_fields), key=group_by_fields.index)
        if group_by:
            result.append("GROUP BY %s" % ", ".join(escape_sql_field_name(col) for col in group_by))

        order_by_fields = self.query.order_by
        order_by = sorted(set(order_by_fields), key=order_by_fields.index)
        if order_by:
            result.append("ORDER BY %s" % ", ".join(escape_sql_field_name(col) for col in order_by))

        if self.query.high_mark is not None:
            result.append("LIMIT %d" % (self.query.high_mark - self.query.low_mark))

        if self.query.slimit is not None:
            result.append("SLIMIT %d" % self.query.slimit)
        # if self.query.low_mark:
        #     if self.query.high_mark is None:
        #         val = self.connection.ops.no_limit_value()
        #         if val:
        #             result.append('LIMIT %d' % val)
        #     result.append('OFFSET %d' % self.query.low_mark)

        return " ".join(result), tuple(params)

    def _parse_agg_condition(self):
        """
        agg_condition format:
        #
        # [{u'key': u'bk_cloud_id', u'method': u'eq', u'value': u'2'},
        #  {u'condition': u'and', u'key': u'ip', u'value': u'127.0.0.1', u'method': u'eq'},
        #  {u'condition': u'or', u'key': u'bk_cloud_id', u'value': u'2', u'method': u'eq'},
        #  {u'condition': u'and', u'key': u'ip', u'value': u'127.0.0.2', u'method': u'eq'},
        # ]
        #
        列表结构：
        - 每一个item代表一个条件，第一个item，没有condition连接字段
        - 以or为分割，将各个部分的条件用括号括起来

        例如：上面的结构
        (bk_cloud_id='2' and ip='127.0.0.1') or (bk_cloud_id='2' and ip='127.0.0.2')

        返回结果: 使用Q表达式包起来
        Q(bk_cloud_id='2', ip='127.0.0.1') | Q(bk_cloud_id='2', ip='127.0.0.2')

        """
        if not self.query.agg_condition:
            return

        ret = Q()

        where_cond = []
        for cond in self.query.agg_condition:
            field_lookup = "{}__{}".format(cond["key"], cond["method"])
            value = cond["value"]

            if not isinstance(value, (list, tuple)):
                value = [value]

            condition = cond.get("condition") or "and"
            if condition.upper() == AND:
                where_cond.append(Q(**{field_lookup: value}))
            elif condition.upper() == OR:
                if where_cond:
                    q = Q(reduce(lambda x, y: x & y, where_cond))
                    ret = (ret | q) if ret else q
                where_cond = [Q(**{field_lookup: value})]
            else:
                raise Exception("Unsupported connector(%s)" % condition)

        if where_cond:
            q = Q(reduce(lambda x, y: x & y, where_cond))
            ret = (ret | q) if ret else q

        return ret


class SQLInsertCompiler(compiler.SQLInsertCompiler, SQLCompiler):
    pass


class SQLDeleteCompiler(compiler.SQLDeleteCompiler, SQLCompiler):
    pass


class SQLUpdateCompiler(compiler.SQLUpdateCompiler, SQLCompiler):
    pass


class SQLAggregateCompiler(compiler.SQLAggregateCompiler, SQLCompiler):
    pass
