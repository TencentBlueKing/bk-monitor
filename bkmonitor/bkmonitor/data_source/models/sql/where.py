"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.core.exceptions import EmptyResultSet
from django.db.models.constants import LOOKUP_SEP
from django.db.models.sql.where import AND
from django.utils import tree

from bkmonitor.data_source.backends.time_series import escape_sql_field_name
from bkmonitor.data_source.models.lookups import get_lookup_class


class WhereNode(tree.Node):
    """
    Used to represent the SQL where-clause.
    """

    default = AND

    def as_sql(self, compiler, connection):
        return self.make_sql(self, compiler, connection, False)

    def make_sql(self, q_object, compiler, connection, multi_quota=True):
        result = []
        result_params = []
        child_multi_quota = multi_quota or len(q_object.children) > 1
        for child in q_object.children:
            try:
                if isinstance(child, tree.Node):
                    sql, params = self.make_sql(child, compiler, connection, child_multi_quota)
                elif isinstance(child, str):
                    sql, params = child, []
                elif isinstance(child, tuple) and len(child) == 2:
                    lookup_obj = self.build_lookup(child)
                    sql, params = lookup_obj.as_sql(compiler, connection)
                else:
                    raise Exception(f"Unsupported query conditions({str(child)})")
            except EmptyResultSet:
                pass
            else:
                if sql:
                    result.append(sql)
                    result_params.extend(params)

        conn = f" {q_object.connector} "
        sql_string = conn.join(result)
        if sql_string:
            if q_object.negated:
                sql_string = f"NOT ({sql_string})"
            elif len(result) > 1 and multi_quota:
                sql_string = f"({sql_string})"
        return sql_string, result_params

    def build_lookup(self, filter_expr):
        lookup, value = filter_expr
        lookup_splitted = lookup.rsplit(LOOKUP_SEP, 1)
        if len(lookup_splitted) == 1:
            field_name = lookup_splitted[0]
            lookup_name = "eq"
        elif len(lookup_splitted) == 2:
            field_name, lookup_name = lookup_splitted
        else:
            raise Exception(f"Unsupported query conditions({str(filter_expr)})")
        field_name = escape_sql_field_name(field_name)
        return get_lookup_class(lookup_name)(field_name, value)

    def clone(self):
        clone = self.__class__(children=[], connector=self.connector, negated=self.negated)
        for child in self.children:
            if hasattr(child, "clone"):
                clone.children.append(child.clone())
            else:
                clone.children.append(child)
        return clone
