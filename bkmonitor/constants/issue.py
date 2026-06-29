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

    # status → 中文标签，用于面向用户的报错文案（避免直接暴露 pending_review 等枚举值）
    LABELS = dict(CHOICES)


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
    COMMENT_EDIT = "comment_edit"
    STATUS_CHANGE = "status_change"
    ASSIGNEE_CHANGE = "assignee_change"
    PRIORITY_CHANGE = "priority_change"
    NAME_CHANGE = "name_change"
    # 合并/拆分活动：content 字段使用结构化 JSON，区分 manual 与 by_main_resolve / by_main_archive
    MERGED_INTO = "merged_into"
    SPLIT_FROM = "split_from"
    CREATE_TAPD = "create_tapd"
    TAPD_LINK = "tapd_link"

    CHOICES = (
        (CREATE, _("创建")),
        (COMMENT, _("评论")),
        (COMMENT_EDIT, _("评论编辑")),
        (STATUS_CHANGE, _("状态变更")),
        (ASSIGNEE_CHANGE, _("负责人变更")),
        (PRIORITY_CHANGE, _("优先级变更")),
        (NAME_CHANGE, _("名称变更")),
        (MERGED_INTO, _("合并进主")),
        (SPLIT_FROM, _("从主拆分")),
        (CREATE_TAPD, _("创建TAPD")),
        (TAPD_LINK, _("关联TAPD")),
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

    # impact_scope 维度 → AlertDocument 查询字段映射
    #
    # 用途：前端根据 impact_scope 中的实例反查关联告警时，使用此映射构造 ES 查询条件
    #
    # 结构说明：
    #   - key: 简化两段式维度标识 "impact_scope.{dimension}"
    #   - value: 列表，统一为单个 query_string 元素
    #     - keys: 固定为 ["query_string"]，后端按 query_string 查询处理
    #     - value_tpl: 完整的 query_string 查询语句，{field} 占位符对应 instance_list 中的字段名
    #       多个子条件用大写 OR / AND 连接；冒号等保留字符需用反斜杠转义
    #       tags.XXX 字段由后端查询转换层自动处理为 nested 查询
    #     - condition: 合并后仅作占位，统一为 "and"
    #
    # 后端在返回 impact_scope 时，会将 value_tpl 中的占位符替换为实例的实际值，
    # 渲染后的结果存放在 instance_list 每个实例的 alert_query_fields 字段中
    ALERT_QUERY_MAPPING = {
        "impact_scope.set": [
            {
                "keys": ["query_string"],
                "value_tpl": "set_id:{set_id} OR tags.set_id:{set_id}",
                "condition": "and",
            },
        ],
        "impact_scope.host": [
            {
                "keys": ["query_string"],
                "value_tpl": "bk_host_id:{bk_host_id} OR tags.bk_host_id:{bk_host_id}",
                "condition": "and",
            },
        ],
        "impact_scope.service_instances": [
            {
                "keys": ["query_string"],
                "value_tpl": (
                    "bk_service_instance_id:{bk_service_instance_id} "
                    "OR tags.bk_service_instance_id:{bk_service_instance_id} "
                    "OR tags.bk_target_service_instance_id:{bk_service_instance_id}"
                ),
                "condition": "and",
            },
        ],
        "impact_scope.cluster": [
            {
                "keys": ["query_string"],
                "value_tpl": "tags.bcs_cluster_id:{bcs_cluster_id}",
                "condition": "and",
            },
        ],
        # node: 需同时满足集群过滤（AND），否则同集群不同命名空间的同名节点会误匹配
        "impact_scope.node": [
            {
                "keys": ["query_string"],
                "value_tpl": (
                    "tags.bcs_cluster_id:{bcs_cluster_id} "
                    "AND (event.target:{node} OR tags.node:{node} OR tags.node_name:{node})"
                ),
                "condition": "and",
            },
        ],
        # service: 需同时满足集群过滤（AND），避免跨集群同名 service 误匹配
        "impact_scope.service": [
            {
                "keys": ["query_string"],
                "value_tpl": (
                    "tags.bcs_cluster_id:{bcs_cluster_id} "
                    "AND (event.target:{service} OR tags.service:{service} OR tags.service_name:{service})"
                ),
                "condition": "and",
            },
        ],
        # pod: 需同时满足集群过滤（AND），避免跨集群同名 pod 误匹配
        "impact_scope.pod": [
            {
                "keys": ["query_string"],
                "value_tpl": (
                    "tags.bcs_cluster_id:{bcs_cluster_id} "
                    "AND (event.target:{pod} OR tags.pod:{pod} OR tags.pod_name:{pod})"
                ),
                "condition": "and",
            },
        ],
        # apm_app: event.target 格式为 "{app_name}:{service_name}"，需前缀匹配
        # 冒号为 query_string 保留字符，需用 \: 转义，* 才能作为通配符生效
        "impact_scope.apm_app": [
            {
                "keys": ["query_string"],
                "value_tpl": "event.target:{app_name}\\:* OR tags.app_name:{app_name}",
                "condition": "and",
            },
        ],
        # apm_service: event.target 中的冒号需转义
        "impact_scope.apm_service": [
            {
                "keys": ["query_string"],
                "value_tpl": ("event.target:{app_name}\\:{service_name} OR tags.service_name:{service_name}"),
                "condition": "and",
            },
        ],
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
