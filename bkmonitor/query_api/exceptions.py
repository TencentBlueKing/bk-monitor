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


import six


class QueryExceptions(Exception):

    error_code = "00"

    def __init__(self, message, error_code=None):
        self.message = message
        self.code = error_code or self.error_code

    def __str__(self):
        return six.text_type("{} code: {}".format(self.message, self.code))


class ResultTableNotExist(QueryExceptions):
    """结果表不存在"""

    error_code = "01"


class StorageResultTableNotExist(QueryExceptions):
    """结果表存在，物理表不存在"""

    error_code = "02"


class QueryTimeOut(QueryExceptions):
    """响应超时"""

    error_code = "03"


class QueryForbidden(QueryExceptions):
    """没有权限执行"""

    error_code = "04"


class SQLSyntaxError(QueryExceptions):
    error_code = "06"


class StorageNotSupported(QueryExceptions):
    """该存储查询不支持检索"""

    error_code = "07"


class TimeFieldError(QueryExceptions):
    """时间字段处理异常"""

    error_code = "08"
