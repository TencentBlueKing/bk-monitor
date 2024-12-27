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

from django.utils.encoding import force_str


class BaseDatabaseOperations(object):
    """
    This class encapsulates all backend-specific differences, such as the way
    a backend performs ordering or calculates the ID of a recently-inserted
    row.
    """

    compiler_module = "bkmonitor.data_source.models.sql.compiler"

    def __init__(self, connection):
        self.connection = connection
        self._cache = None

    def compiler(self, compiler_name):
        """
        Returns the SQLCompiler class corresponding to the given name,
        in the namespace corresponding to the `compiler_module` attribute
        on this backend.
        """
        if self._cache is None:
            self._cache = import_module(self.compiler_module)
        return getattr(self._cache, compiler_name)

    def prep_for_like_query(self, x):
        """Prepares a value for use in a LIKE query."""
        return force_str(x).replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")

    def prep_regex_query(self, reg_expr):
        reg_expr = force_str(reg_expr).replace("/", "\\/")
        return RegularExpressions(f"/{reg_expr}/")


class RegularExpressions(str):
    is_regex = True
