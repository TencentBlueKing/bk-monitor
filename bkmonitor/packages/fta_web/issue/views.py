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
    READ_ONLY_ENDPOINTS = ["issue/search", "issue/detail", "issue/activities", "issue/history", "issue/top_n"]

    # 允许不传业务 ID 的接口（由业务层自行限制数据范围）
    # 新增支持「无业务 ID」的接口时，只需在此处追加 endpoint 名称即可
    NO_BIZ_REQUIRED_ENDPOINTS = ["issue/search", "issue/top_n"]

    class IssueBusinessActionPermission(IAMPermission):
        """
        Issue 功能专用业务权限校验。

        Issue 接口的 bk_biz_id 来源有三种情况：
        1. 批量写操作：bk_biz_id 嵌套在请求体的 issues[*].bk_biz_id 中；
        2. 查询接口（issue/search）：bk_biz_id 以列表形式存放在 bk_biz_ids 字段中；
        3. 其他接口（GET 接口等）：bk_biz_id 为顶层单值字段，或由框架从 URL 注入 request.biz_id。

        框架默认的 BusinessActionPermission 只提取顶层 bk_biz_id，
        导致上述情况 1、2 时 request.biz_id 为空，跳过 IAM 校验。

        本类按优先级依次尝试三种来源提取所有唯一 bk_biz_id，
        对每个业务 ID 分别做 IAM 校验，全部通过才放行。
        """

        def has_permission(self, request, view):
            body = request.data or {}
            issues = body.get("issues") if isinstance(body, dict) else None

            if issues:
                # 批量写操作：从 issues[*].bk_biz_id 提取
                biz_ids = {item["bk_biz_id"] for item in issues if isinstance(item, dict) and item.get("bk_biz_id")}
            elif isinstance(body, dict) and body.get("bk_biz_ids"):
                # 查询issue列表接口：bk_biz_ids 为列表
                biz_ids = set(body["bk_biz_ids"])
            else:
                # 其他接口：request.biz_id 由 RequestProvider middleware 在 process_view 阶段注入，
                # 提取来源依次为：URL 路径参数、GET query string（bk_biz_id）、POST 表单（bk_biz_id）、JSON body（bk_biz_id）
                biz_id = getattr(request, "biz_id", None)
                biz_ids = {biz_id} if biz_id else set()

            if not biz_ids:
                # 部分接口允许不传业务 ID（见 NO_BIZ_REQUIRED_ENDPOINTS），此时由业务层自行限制数据范围
                # 其他接口必须携带业务 ID，否则拒绝访问。
                return view.action in getattr(view, "NO_BIZ_REQUIRED_ENDPOINTS", [])

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
        # Issue TopN 统计
        ResourceRoute("POST", resource.issue.issue_top_n, endpoint="issue/top_n"),
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
