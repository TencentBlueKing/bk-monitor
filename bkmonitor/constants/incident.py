"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.translation import gettext_lazy as _lazy

from api.bkdata.default import UpdateIncidentDetail
from constants.common import CustomEnum

INCIDENT_ATTRIBUTE_ALIAS_MAPPINGS = {
    field_name: field.label for field_name, field in UpdateIncidentDetail.RequestSerializer().get_fields().items()
}


class IncidentStatus(CustomEnum):
    """故障状态枚举"""

    ABNORMAL = "abnormal"
    RECOVERING = "recovering"
    RECOVERED = "recovered"
    CLOSED = "closed"

    @property
    def alias(self) -> str:
        incident_status_map = {
            "abnormal": _lazy("未恢复"),
            "recovered": _lazy("已恢复"),
            "recovering": _lazy("观察中"),
            "closed": _lazy("已解决"),
        }
        return incident_status_map[self.value]

    @property
    def order(self) -> str:
        incident_status_order_map = {
            "abnormal": 0,
            "recovered": 2,
            "recovering": 1,
            "closed": 3,
        }
        return incident_status_order_map[self.value]


class IncidentLevel(CustomEnum):
    """故障级别枚举"""

    ERROR = "ERROR"
    WARN = "WARN"
    INFO = "INFO"

    @property
    def alias(self) -> str:
        incident_level_map = {
            "ERROR": _lazy("致命"),
            "WARN": _lazy("预警"),
            "INFO": _lazy("提醒"),
        }
        return incident_level_map[self.value]


INCIDENT_ATTRIBUTE_VALUE_ENUMS = {
    "status": IncidentStatus,
    "level": IncidentLevel,
}


class IncidentOperationClass(CustomEnum):
    """故障操作类别"""

    SYSTEM = "system"
    USER = "user"

    @property
    def alias(self) -> str:
        incident_operation_class_map = {
            "system": _lazy("系统事件"),
            "user": _lazy("人工操作"),
        }
        return incident_operation_class_map[self.value]


class IncidentOperationType(CustomEnum):
    """故障操作类型"""

    CREATE = "incident_create"
    OBSERVE = "incident_observe"
    RECOVER = "incident_recover"
    NOTICE = "incident_notice"
    UPDATE = "incident_update"
    MERGE = "incident_merge"
    ALERT_TRIGGER = "alert_trigger"
    ALERT_RECOVER = "alert_recover"
    ALERT_INVALID = "alert_invalid"
    ALERT_NOTICE = "alert_notice"
    ALERT_CONVERGENCE = "alert_convergence"
    MANUAL_UPDATE = "manual_update"
    FEEDBACK = "feedback"
    CLOSE = "incident_close"
    GROUP_GATHER = "group_gather"
    ALERT_CONFIRM = "alert_confirm"
    ALERT_SHIELD = "alert_shield"
    ALERT_HANDLE = "alert_handle"
    ALERT_CLOSE = "alert_close"
    ALERT_DISPATCH = "alert_dispatch"

    @property
    def alias(self):
        incident_operation_type_map = {
            "incident_create": _lazy("故障生成"),
            "incident_observe": _lazy("故障观察中"),
            "incident_recover": _lazy("故障恢复"),
            "incident_notice": _lazy("故障通知"),
            "incident_update": _lazy("修改故障属性"),
            "incident_merge": _lazy("故障合并"),
            "alert_trigger": _lazy("触发告警"),
            "alert_recover": _lazy("告警恢复"),
            "alert_invalid": _lazy("告警失效"),
            "alert_notice": _lazy("告警通知"),
            "alert_convergence": _lazy("告警收敛"),
            "manual_update": _lazy("修改故障属性"),
            "feedback": _lazy("反馈/取消反馈根因"),
            "incident_close": _lazy("故障关闭"),
            "group_gather": _lazy("一键拉群"),
            "alert_confirm": _lazy("告警确认"),
            "alert_shield": _lazy("告警屏蔽"),
            "alert_handle": _lazy("告警处理"),
            "alert_close": _lazy("告警关闭"),
            "alert_dispatch": _lazy("告警分派"),
        }
        return incident_operation_type_map[self.value]

    @property
    def operation_class(self) -> IncidentOperationClass:
        if self.value in [
            "incident_create",
            "incident_observe",
            "incident_recover",
            "incident_notice",
            "incident_update",
            "incident_merge",
            "alert_trigger",
            "alert_recover",
            "alert_invalid",
            "alert_notice",
            "alert_convergence",
        ]:
            return IncidentOperationClass.SYSTEM
        else:
            return IncidentOperationClass.USER


class IncidentSyncType(CustomEnum):
    """故障同步类型."""

    CREATE = "create"
    UPDATE = "update"


class IncidentGraphEdgeType(CustomEnum):
    """故障图谱边类型."""

    DEPENDENCY = "dependency"
    SPREAD = "spread"
    EBPF_CALL = "ebpf_call"


class IncidentGraphEdgeEventType(CustomEnum):
    """故障图谱边事件类型."""

    ANOMALY = "anomaly"
    NORMAL = "normal"


class IncidentGraphEdgeEventDirection(CustomEnum):
    """故障图谱边事件传播方向."""

    FORWARD = "forward"
    REVERSE = "reverse"


class IncidentAlertAggregateDimension(CustomEnum):
    """故障告警聚合维度."""

    STATUS = "status"
    NODE_LEVEL = "node_level"
    NODE_TYPE = "node_type"
    ALERT_NAME = "alert_name"
    NODE_NAME = "node_name"
    METRIC_NAME = "metric_name"

    @property
    def alias(self) -> str:
        aggregate_dimension_map = {
            "status": _lazy("节点状态"),
            "node_level": _lazy("节点层级"),
            "node_type": _lazy("节点类型"),
            "alert_name": _lazy("告警名称"),
            "node_name": _lazy("节点名称"),
            "metric_name": _lazy("指标名称"),
        }
        return aggregate_dimension_map[self.value]

    @property
    def chain_key(self) -> str:
        aggregate_dimension_map = {
            "status": "status",
            "node_level": "entity.rank.rank_category.category_name",
            "node_type": "entity.rank.rank_name",
            "alert_name": "alert_name",
            "node_name": "entity.entity_name",
            "metric_name": "metric_display",
        }
        return aggregate_dimension_map[self.value]


class IncidentGraphComponentType(CustomEnum):
    """故障图谱组件类型."""

    PRIMARY = "primary"
    BASE_MAP = "base_map"
    TOPO = "topo"
    ONE_HOP = "one_hop"
