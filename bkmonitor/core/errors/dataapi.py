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


from django.utils.translation import gettext_lazy as _lazy

from core.errors import Error

"""
@desc: 这里定义异常
"""


class DataApiError(Error):
    code = 3308001


class TSDBParseError(Error):
    """
    tsdb表名解析异常
    """

    code = 3308003
    name = _lazy("tsdb表名解析异常")
    message_tpl = _lazy("tsdb表名解析异常：{rt_id}")


class SqlQueryException(Error):
    """sql查询异常"""

    code = 3308004
    name = _lazy("sql查询异常")


class EmptyQueryException(Error):
    """sql查询无数据"""

    code = 3308005
    name = _lazy("sql查询无数据")


class DateSetNotExist(Error):
    """data id不存在"""

    code = 3308006
    name = _lazy("data id不存在")
    message_tpl = _lazy("data_id: {data_id}不存在")
