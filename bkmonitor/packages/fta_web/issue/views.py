"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from bkmonitor.iam import ActionEnum
from bkmonitor.iam.drf import IAMPermission
from bkmonitor.iam.resource import ResourceEnum
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class IssueViewSet(ResourceViewSet):
    """Issues 功能接口 ViewSet"""

    # 只读接口使用 VIEW_EVENT 权限，写操作使用 MANAGE_EVENT 权限
    READ_ONLY_ENDPOINTS = ["issue/search", "issue/detail", "issue/activities", "issue/history"]

    class IssueBusinessActionPermission(IAMPermission):
        """
        Issue 功能专用业务权限校验。

        Issue 有些接口的 bk_biz_id 嵌套在请求体的 issues[*].bk_biz_id 中，
        框架默认的 BusinessActionPermission 只提取顶层 bk_biz_id，
        导致 request.biz_id 为空时直接放行，跳过 IAM 校验。

        本类从 issues 数组中提取所有唯一 bk_biz_id，
        对每个业务 ID 分别做 IAM 校验，全部通过才放行。
        若请求体中没有 issues 字段（如 GET 接口），则回退到标准逻辑。
        """

        def has_permission(self, request, view):
            body = request.data or {}
            issues = body.get("issues") if isinstance(body, dict) else None

            if issues:
                biz_ids = {item["bk_biz_id"] for item in issues if isinstance(item, dict) and item.get("bk_biz_id")}
            else:
                biz_id = getattr(request, "biz_id", None) or (body.get("bk_biz_id") if isinstance(body, dict) else None)
                biz_ids = {biz_id} if biz_id else set()

            if not biz_ids:
                return False

            for biz_id in biz_ids:
                self.resources = [ResourceEnum.BUSINESS.create_instance(str(biz_id))]
                super().has_permission(request, view)  # 无权限时 raise PermissionDeniedError
            return True

    def get_permissions(self):
        # 查询变更记录为只读操作，使用 VIEW_EVENT 权限
        # 其余写操作（指派、解决、改优先级、添加跟进）使用 MANAGE_EVENT 权限
        if self.action in self.READ_ONLY_ENDPOINTS:
            return [self.IssueBusinessActionPermission([ActionEnum.VIEW_EVENT])]
        return [self.IssueBusinessActionPermission([ActionEnum.MANAGE_EVENT])]

    resource_routes = [
        # Issue 列表查询
        ResourceRoute("POST", resource.issue.search_issue, endpoint="issue/search"),
        # Issue 详情（元数据）
        ResourceRoute("GET", resource.issue.issue_detail, endpoint="issue/detail"),
        # 指派负责人（含改派，支持批量）
        ResourceRoute("POST", resource.issue.assign_issue, endpoint="issue/assign"),
        # 标记为已解决（支持批量）
        ResourceRoute("POST", resource.issue.resolve_issue, endpoint="issue/resolve"),
        # 重新打开已解决 Issue（支持批量）
        ResourceRoute("POST", resource.issue.reopen_issue, endpoint="issue/reopen"),
        # 归档 Issue（实例级，支持批量）
        ResourceRoute("POST", resource.issue.archive_issue, endpoint="issue/archive"),
        # 恢复归档 Issue（实例级，支持批量）
        ResourceRoute("POST", resource.issue.restore_issue, endpoint="issue/restore"),
        # 修改优先级（支持批量）
        ResourceRoute("POST", resource.issue.update_issue_priority, endpoint="issue/update_priority"),
        # 添加跟进信息（支持批量）
        ResourceRoute("POST", resource.issue.add_issue_follow_up, endpoint="issue/add_follow_up"),
        # 查询变更记录(活动日志)
        ResourceRoute("GET", resource.issue.list_issue_activities, endpoint="issue/activities"),
        # 查询历史 Issue（同策略下已解决的历史 Issue 列表）
        ResourceRoute("GET", resource.issue.list_issue_history, endpoint="issue/history"),
    ]
