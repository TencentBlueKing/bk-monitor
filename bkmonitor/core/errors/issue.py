"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

"""
Issue 业务错误

错误码段：3327xxx（当前未被其他模块占用）
"""
from django.utils.translation import gettext_lazy as _lazy

from core.errors.common import CommonError


class IssueError(CommonError):
    """Issue 错误基类"""

    code = 3327000
    name = _lazy("Issue 错误")
    message_tpl = "{message}"


class IssueRenameConflictError(IssueError):
    """重命名 Issue 冲突（同业务下已存在同名 Issue）"""

    code = 3327001
    status_code = 409  # Conflict 语义（业务错误码仍以 body.code 为准，前端据此识别）
    name = _lazy("Issue 重名")
    message_tpl = "{message}"
