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

    # 维度到 instance_list 中 ID 字段的映射
    # flattened 类型下，exists 查询必须使用叶子节点字段路径
    ID_FIELD_MAP = {
        SET: "set_id",
        HOST: "bk_host_id",
        SERVICE_INSTANCES: "bk_service_instance_id",
        CLUSTER: "bcs_cluster_id",
        NODE: "node",
        SERVICE: "service",
        POD: "pod",
        APM_APP: "app_name",
        APM_SERVICE: "service_name",
    }

    @classmethod
    def get_display_name(cls, dimension: str) -> str:
        """获取维度的展示名称，未匹配时返回原维度值"""
        return dict(cls.CHOICES).get(dimension, dimension)

    @classmethod
    def get_id_field(cls, dimension: str) -> str:
        """获取维度在 instance_list 中对应的 ID 字段名，未匹配时返回维度本身"""
        return cls.ID_FIELD_MAP.get(dimension, dimension)

    @classmethod
    def get_full_dimension(cls, dimension: str) -> str:
        """获取维度的完整维度名，未匹配时返回原维度值
        示例：host -> impact_scope.host.instance_list.bk_host_id
        """
        id_field = cls.get_id_field(dimension)
        return f"impact_scope.{dimension}.instance_list.{id_field}"
