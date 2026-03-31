"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.translation import gettext_lazy as _


class IssueStatus:
    PENDING_REVIEW = "pending_review"
    UNRESOLVED = "unresolved"
    RESOLVED = "resolved"
    ARCHIVED = "archived"

    ACTIVE_STATUSES = [PENDING_REVIEW, UNRESOLVED]

    CHOICES = (
        (PENDING_REVIEW, _("待审核")),
        (UNRESOLVED, _("未解决")),
        (RESOLVED, _("已解决")),
        (ARCHIVED, _("归档")),
    )


class IssuePriority:
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"

    DEFAULT = P2

    CHOICES = (
        (P0, _("高")),
        (P1, _("中")),
        (P2, _("低")),
    )


class IssueActivityType:
    CREATE = "create"
    COMMENT = "comment"
    STATUS_CHANGE = "status_change"
    ASSIGNEE_CHANGE = "assignee_change"
    PRIORITY_CHANGE = "priority_change"

    CHOICES = (
        (CREATE, _("创建")),
        (COMMENT, _("评论")),
        (STATUS_CHANGE, _("状态变更")),
        (ASSIGNEE_CHANGE, _("负责人变更")),
        (PRIORITY_CHANGE, _("优先级变更")),
    )


class ImpactScopeDimension:
    """影响范围维度枚举"""

    SET = "set"
    HOST = "host"
    SERVICE_INSTANCES = "service_instances"
    CLUSTER = "cluster"
    NODE = "node"
    SERVICE = "service"
    POD = "pod"
    APM_APP = "apm_app"
    APM_SERVICE = "apm_service"

    CHOICES = (
        (SET, _("集群")),
        (HOST, _("主机")),
        (SERVICE_INSTANCES, _("服务实例")),
        (CLUSTER, _("bcs集群")),
        (NODE, "node"),
        (SERVICE, "service"),
        (POD, "pod"),
        (APM_APP, "apm_app"),
        (APM_SERVICE, "apm_service"),
    )

    @classmethod
    def get_display_name(cls, dimension: str) -> str:
        """获取维度的展示名称，未匹配时返回原维度值"""
        return dict(cls.CHOICES).get(dimension, dimension)
