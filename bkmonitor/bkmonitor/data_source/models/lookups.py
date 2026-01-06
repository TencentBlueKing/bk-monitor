"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import re

from django.db.models.sql.where import AND, OR


class Lookup:
    lookup_name = None

    def __init__(self, lhs, rhs):
        self.lhs, self.rhs = lhs, rhs

    def process_lhs(self, compiler, connection, lhs=None):
        return lhs or self.lhs, []

    def process_rhs(self, compiler, connection):
        return "%s", [self.rhs]

    def get_rhs_op(self, connection, rhs):
        return connection.operators[self.lookup_name] % rhs

    def as_sql(self, compiler, connection):
        lhs_sql, params = self.process_lhs(compiler, connection, self.lhs)
        rhs_sql, rhs_params = self.process_rhs(compiler, connection)
        params.extend(rhs_params)
        rhs_sql = self.get_rhs_op(connection, rhs_sql)
        return f"{lhs_sql} {rhs_sql}", params


def is_list_type(value):
    return isinstance(value, list | tuple)


class Exact(Lookup):
    lookup_name = "exact"


class Equal(Lookup):
    lookup_name = "eq"
    list_connector = f" {OR} "

    def as_sql(self, compiler, connection):
        lhs_sql, params = self.process_lhs(compiler, connection, self.lhs)
        rhs_sql, rhs_params = self.process_rhs(compiler, connection)
        rhs_sql = self.get_rhs_op(connection, rhs_sql)
        if rhs_params and is_list_type(rhs_params[0]):
            params.extend(rhs_params[0])
            result = [
                f"{lhs_sql} {rhs_sql}",
            ] * len(rhs_params[0])
            sql_string = self.list_connector.join(result)
            if len(result) > 1:
                sql_string = f"({sql_string})"
        else:
            params.extend(rhs_params)
            sql_string = f"{lhs_sql} {rhs_sql}"
        return sql_string, params


class NotEqual(Equal):
    lookup_name = "neq"
    list_connector = f" {AND} "


class GreaterThan(Lookup):
    lookup_name = "gt"

    def process_rhs(self, compiler, connection):
        rhs, params = super().process_rhs(compiler, connection)
        if params and is_list_type(params[0]):
            params[0] = max(params[0])
        return rhs, params


class GreaterThanOrEqual(GreaterThan):
    lookup_name = "gte"


class LessThan(Lookup):
    lookup_name = "lt"

    def process_rhs(self, compiler, connection):
        rhs, params = super().process_rhs(compiler, connection)
        if params and is_list_type(params[0]):
            params[0] = min(params[0])
        return rhs, params


class LessThanOrEqual(LessThan):
    lookup_name = "lte"


class Contains(Lookup):
    lookup_name = "contains"

    def process_rhs(self, qn, connection):
        rhs, params = super().process_rhs(qn, connection)
        if params:
            params[0] = f"%{connection.ops.prep_for_like_query(params[0])}%"
        return rhs, params


class Regex(Equal):
    lookup_name = "reg"
    list_connector = f" {OR} "

    def process_rhs(self, qn, connection):
        rhs, params = super().process_rhs(qn, connection)
        if params[0]:
            params[0] = list(map(getattr(self, "escape", lambda x: x), params[0]))
            params[0] = list(map(connection.ops.prep_regex_query, params[0]))
        return rhs, params


class NeRegex(Regex):
    lookup_name = "nreg"
    list_connector = f" {AND} "


class StrEscapeMixin:
    @staticmethod
    def escape(v):
        v = re.escape(v)
        return v.replace("\\/", "/")


class Include(Regex, StrEscapeMixin):
    pass


class Exclude(NeRegex, StrEscapeMixin):
    pass


default_lookups = {}
default_lookups["exact"] = Exact
default_lookups["eq"] = Equal
default_lookups["neq"] = NotEqual
default_lookups["!="] = NotEqual
default_lookups["gt"] = GreaterThan
default_lookups["gte"] = GreaterThanOrEqual
default_lookups["lt"] = LessThan
default_lookups["lte"] = LessThanOrEqual
default_lookups["contains"] = Contains
default_lookups["reg"] = Regex
default_lookups["nreg"] = NeRegex
default_lookups["include"] = Include
default_lookups["exclude"] = Exclude


def get_lookup_class(lookup_name):
    lookup_class = default_lookups.get(lookup_name)
    if lookup_class is None:
        raise Exception(f"Unsupported lookup '{lookup_name}'")
    return lookup_class
