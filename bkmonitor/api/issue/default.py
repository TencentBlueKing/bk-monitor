"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.conf import settings

from core.drf_resource.contrib.nested_api import KernelAPIResource


class IssueAPIResource(KernelAPIResource):
    """
    Issue API 基类
    """

    TIMEOUT = 300
    base_url = (
        settings.NEW_MONITOR_API_BASE_URL or f"{settings.BK_COMPONENT_API_URL}/api/bk-monitor/{settings.APIGW_STAGE}/"
    )
    module_name = "issue"

    @property
    def label(self):
        return self.__doc__


class AssignResource(IssueAPIResource):
    """指派/改派 Issue 负责人"""

    action = "/app/issue/assign/"
    method = "POST"


class ResolveResource(IssueAPIResource):
    """标记 Issue 为已解决"""

    action = "/app/issue/resolve/"
    method = "POST"


class ReopenResource(IssueAPIResource):
    """重新打开 Issue（已解决 → 未解决）"""

    action = "/app/issue/reopen/"
    method = "POST"


class ArchiveResource(IssueAPIResource):
    """归档 Issue"""

    action = "/app/issue/archive/"
    method = "POST"


class RestoreResource(IssueAPIResource):
    """恢复归档 Issue"""

    action = "/app/issue/restore/"
    method = "POST"


class UpdatePriorityResource(IssueAPIResource):
    """修改 Issue 优先级"""

    action = "/app/issue/update_priority/"
    method = "POST"


class AddFollowUpResource(IssueAPIResource):
    """向 Issue 添加跟进评论"""

    action = "/app/issue/add_follow_up/"
    method = "POST"
