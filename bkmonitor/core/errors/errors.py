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
from django.utils.translation import gettext as _

"""
@desc: 这里定义异常
"""


class Error(Exception):
    pass


class APIError(Error):
    pass


class ESBAPIError(APIError):
    pass


class CCAPIError(ESBAPIError):
    pass


class JobAPIError(ESBAPIError):
    pass


class JAAPIError(APIError):
    pass


class JAItemDoseNotExists(JAAPIError):
    pass


class MessageTemplateSyntaxError(Error):
    pass


class TableNotExistException(Error):
    """计算平台结果表不存在"""

    def __init__(self, message):
        self.message = getattr(message, "message", message).split(":")[0]
        self.table_name = self.message.strip(_("结果表")).strip(_("不存在"))

    def __str__(self):
        return self.message


class TSDBParseError(Error):
    """
    tsdb表名解析异常
    """


class SqlQueryException(Error):
    """计算平台sql查询异常"""

    pass


class PermissionException(Error):
    """权限不足"""

    pass


class EmptyQueryException(Error):
    """计算平台sql查询无数据"""

    pass


class DateSetNotExist(Error):
    """计算平台data id不存在"""


class MigrateError(Error):
    """
    迁移执行失败
    """

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message
