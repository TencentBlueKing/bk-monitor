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

from pymysql.converters import escape_item, escape_string


def sql_format_params(sql, params):
    # 实时计算语法与查询语法存在一定差异，需要对sql进行特殊处理
    sql = sql.replace("!=", "<>")

    def escape(obj):
        if isinstance(obj, str):
            return "'" + escape_string(obj) + "'"
        return escape_item(obj, "utf8", mapping=None)

    params = tuple(escape(arg) for arg in params)
    return sql % params
