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
    COMMENT_EDIT = "comment_edit"
    STATUS_CHANGE = "status_change"
    ASSIGNEE_CHANGE = "assignee_change"
    PRIORITY_CHANGE = "priority_change"
    NAME_CHANGE = "name_change"

    CHOICES = (
        (CREATE, _("创建")),
        (COMMENT, _("评论")),
        (COMMENT_EDIT, _("评论编辑")),
        (STATUS_CHANGE, _("状态变更")),
        (ASSIGNEE_CHANGE, _("负责人变更")),
        (PRIORITY_CHANGE, _("优先级变更")),
        (NAME_CHANGE, _("名称变更")),
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
    #   - value: 列表，每个元素为一组查询条件
    #     - keys: AlertDocument 中可查询的字段列表
    #       - "event.XXX"     → 走顶层 term 查询
    #       - "tags.XXX"      → 走 event.tags nested 查询
    #       - "query_string"  → 走 query_string 查询（value_tpl 为完整查询语句）
    #     - value_tpl: 值模板，{field} 占位符对应 instance_list 中的字段名
    #     - condition: 元素间的组合逻辑
    #       - "or"  → 该元素与列表中其他元素为"或"关系，任一命中即匹配
    #       - "and" → 该元素与列表中其他元素为"与"关系，必须同时满足
    #       同一元素内多个 keys 之间始终为"或"关系
    #
    # 后端在返回 impact_scope 时，会将 value_tpl 中的占位符替换为实例的实际值，
    # 渲染后的结果存放在 instance_list 每个实例的 alert_query_fields 字段中
    ALERT_QUERY_MAPPING = {
        "impact_scope.set": [
            {
                "keys": ["event.bk_topo_node", "tags.bk_topo_node"],
                "value_tpl": "set|{set_id}",
                "condition": "or",
            },
        ],
        "impact_scope.host": [
            {
                "keys": ["event.bk_host_id", "tags.bk_host_id"],
                "value_tpl": "{bk_host_id}",
                "condition": "or",
            },
        ],
        "impact_scope.service_instances": [
            {
                "keys": [
                    "event.bk_service_instance_id",
                    "tags.bk_service_instance_id",
                    "tags.bk_target_service_instance_id",
                ],
                "value_tpl": "{bk_service_instance_id}",
                "condition": "or",
            },
        ],
        "impact_scope.cluster": [
            {
                "keys": ["tags.bcs_cluster_id"],
                "value_tpl": "{bcs_cluster_id}",
                "condition": "or",
            },
        ],
        # node: 需同时满足集群过滤（and），否则同集群不同命名空间的同名节点会误匹配
        "impact_scope.node": [
            {
                "keys": ["tags.bcs_cluster_id"],
                "value_tpl": "{bcs_cluster_id}",
                "condition": "and",
            },
            {
                "keys": ["event.target", "tags.node", "tags.node_name"],
                "value_tpl": "{node}",
                "condition": "or",
            },
        ],
        # service: 需同时满足集群过滤（and），避免跨集群同名 service 误匹配
        "impact_scope.service": [
            {
                "keys": ["tags.bcs_cluster_id"],
                "value_tpl": "{bcs_cluster_id}",
                "condition": "and",
            },
            {
                "keys": ["event.target", "tags.service", "tags.service_name"],
                "value_tpl": "{service}",
                "condition": "or",
            },
        ],
        # pod: 需同时满足集群过滤（and），避免跨集群同名 pod 误匹配
        "impact_scope.pod": [
            {
                "keys": ["tags.bcs_cluster_id"],
                "value_tpl": "{bcs_cluster_id}",
                "condition": "and",
            },
            {
                "keys": ["event.target", "tags.pod", "tags.pod_name"],
                "value_tpl": "{pod}",
                "condition": "or",
            },
        ],
        # apm_app: event.target 格式为 "{app_name}:{service_name}"，需前缀匹配
        # query_string 中双引号内 * 不作为通配符，需用 \: 转义冒号，* 才能作为通配符生效
        # 渲染示例：event.target:nf\:* → 匹配 event.target 以 "nf:" 开头的所有文档
        "impact_scope.apm_app": [
            {
                "keys": ["query_string"],
                "value_tpl": "event.target:{app_name}\\:*",
                "condition": "or",
            },
            {
                "keys": ["tags.app_name"],
                "value_tpl": "{app_name}",
                "condition": "or",
            },
        ],
        "impact_scope.apm_service": [
            {
                "keys": ["event.target"],
                "value_tpl": "{app_name}:{service_name}",
                "condition": "or",
            },
            {
                "keys": ["tags.service_name"],
                "value_tpl": "{service_name}",
                "condition": "or",
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
