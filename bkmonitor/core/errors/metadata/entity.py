"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.translation import gettext_lazy as _lazy

from core.errors import Error


class EntityError(Error):
    """实体模块错误基类"""

    status_code = 500
    code = 3345001
    name = _lazy("实体模块错误")
    message_tpl = _lazy("实体模块错误：{msg}")


class EntityNotFoundError(EntityError):
    """实体不存在错误"""

    status_code = 404
    code = 3345002
    name = _lazy("实体不存在")
    message_tpl = _lazy("实体不存在: {namespace}/{name}")


class UnsupportedKindError(EntityError):
    """不支持的实体类型错误"""

    status_code = 400
    code = 3345003
    name = _lazy("不支持的实体类型")
    message_tpl = _lazy("不支持的实体类型: {kind}")
