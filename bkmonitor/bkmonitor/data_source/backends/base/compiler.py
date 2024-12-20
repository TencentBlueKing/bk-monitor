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


from django.core.exceptions import EmptyResultSet


class SQLCompiler(object):
    def __init__(self, query, connection, using):
        self.query = query
        self.connection = connection
        self.using = using
        pass

    def compile(self, node):
        vendor_impl = getattr(node, "as_" + self.connection.vendor, None)
        if vendor_impl:
            sql, params = vendor_impl(self, self.connection)
        else:
            sql, params = node.as_sql(self, self.connection)
        return sql, params

    def as_sql(self):
        raise NotImplementedError

    def execute_sql(self):
        try:
            sql, params = self.as_sql()
        except Exception:
            raise

        if not sql:
            raise EmptyResultSet

        try:
            return self.connection.execute(sql, params)
        except Exception:
            raise


class SQLInsertCompiler(SQLCompiler):
    """
    Temporarily unavailable, coming soon
    """

    def __init__(self, *args, **kwargs):
        self.return_id = False
        super(SQLInsertCompiler, self).__init__(*args, **kwargs)

    def as_sql(self):
        raise NotImplementedError


class SQLDeleteCompiler(SQLCompiler):
    """
    Temporarily unavailable, coming soon
    """

    def as_sql(self):
        raise NotImplementedError


class SQLUpdateCompiler(SQLCompiler):
    """
    Temporarily unavailable, coming soon
    """

    def as_sql(self):
        raise NotImplementedError


class SQLAggregateCompiler(SQLCompiler):
    """
    Temporarily unavailable, coming soon
    """

    def as_sql(self):
        raise NotImplementedError
