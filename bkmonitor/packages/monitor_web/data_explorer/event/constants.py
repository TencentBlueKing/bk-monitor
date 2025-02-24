# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import sys
from enum import Enum, IntEnum

from django.utils.translation import gettext_lazy as _


class EventCategory(Enum):
    """
    事件类别枚举
    """

    COMMON = "common"
    SYSTEM_EVENT = "system_event"
    K8S_EVENT = "k8s_event"
    CICD_EVENT = "cicd_event"
    UNKNOWN_EVENT = ""


class CategoryWeight(IntEnum):
    """
    事件类别权重枚举
    """

    COMMON = 0
    SYSTEM_EVENT = 1
    K8S_EVENT = 2
    CICD_EVENT = 3
    UNKNOWN = sys.maxsize


# 事件类别和权重映射
CATEGORY_WEIGHTS = {
    EventCategory.COMMON.value: CategoryWeight.COMMON.value,
    EventCategory.SYSTEM_EVENT.value: CategoryWeight.SYSTEM_EVENT.value,
    EventCategory.K8S_EVENT.value: CategoryWeight.K8S_EVENT.value,
    EventCategory.CICD_EVENT.value: CategoryWeight.CICD_EVENT.value,
}


class EventDimensionTypeEnum(Enum):
    """
    事件维度类型枚举
    """

    KEYWORD: str = "keyword"
    TEXT: str = "text"
    INTEGER: str = "integer"
    DATE: str = "date"


# 事件字段别名
EVENT_FIELD_ALIAS = {
    EventCategory.COMMON.value: {
        "time": _("数据上报时间"),
        "event_name": _("事件名"),
        "event.content": _("事件内容"),
        "target": _("目标"),
        "bk_biz_id": _("业务"),
        "bk_cloud_id": _("管控区域"),
        "bk_target_cloud_id": _("管控区域"),
        "bk_target_ip": _("IP"),
        "ip": _("IP"),
        "bk_agent_id": _("AgentID"),
        "domain": _("事件领域"),
        "source": _("事件来源"),
        "host": _("IP"),
        "type": _("事件类型"),
    },
    EventCategory.SYSTEM_EVENT.value: {
        "process": _("进程"),
        "oom_memcg": _("实际内存 cgroup"),
        "task_memcg": _("进程所属内存 cgroup"),
        "file_system": _("文件系统"),
        "fstype": _("文件系统类型"),
        "disk": _("磁盘"),
    },
    EventCategory.K8S_EVENT.value: {
        "bcs_cluster_id": _("集群 ID"),
        "uid": _("资源对象 Unique ID"),
        "apiVersion": _("资源对象 API 版本"),
        "kind": _("资源对象类型"),
        "namespace": _("资源对象命名空间"),
        "name": _("资源对象名称"),
    },
    EventCategory.CICD_EVENT.value: {
        "duration": _("持续时间"),
        "start_time": _("启动时间"),
        "projectId": _("项目 ID"),
        "pipelineId": _("流水线 ID"),
        "pipelineName": _("流水线名称"),
        "trigger": _("任务类型"),
        "triggerUser": _("任务创建用户"),
        "buildId": _("任务 ID"),
        "status": _("任务状态"),
    },
}

DISPLAY_FIELDS = [
    {"name": "time", "alias": _("数据上报时间")},
    {"name": "type", "alias": _("事件类型"), "type": "attach"},
    {"name": "event_name", "alias": _("事件名")},
    {"name": "event.content", "alias": _("内容"), "type": "descriptions"},
    {"name": "target", "alias": _("目标"), "type": "link"},
]

# 内置字段类型映射集
INNER_FIELD_TYPE_MAPPINGS = {
    "time": EventDimensionTypeEnum.DATE.value,
    "event_name": EventDimensionTypeEnum.KEYWORD.value,
    "event.content": EventDimensionTypeEnum.TEXT.value,
    "target": EventDimensionTypeEnum.KEYWORD.value,
}


# 查询操作符
class Operation:
    EQ = {"alias": "=", "value": "eq"}
    NE = {"alias": "!=", "value": "ne"}
    INCLUDE = {"alias": _("包含"), "value": "include"}
    EXCLUDE = {"alias": _("不包含"), "value": "exclude"}
    EQ_WITH_WILDCARD = {"alias": _("包含"), "value": "include", "options": {"label": _("使用通配符"), "name": "is_wildcard"}}
    NE_WITH_WILDCARD = {"alias": _("不包含"), "value": "exclude", "options": {"label": _("使用通配符"), "name": "is_wildcard"}}


# 类型和操作符映射
TYPE_OPERATION_MAPPINGS = {
    "date": [Operation.EQ, Operation.NE],
    "keyword": [Operation.EQ, Operation.NE, Operation.INCLUDE, Operation.EXCLUDE],
    "text": [Operation.EQ_WITH_WILDCARD, Operation.NE_WITH_WILDCARD],
    "integer": [Operation.EQ, Operation.NE],
}

ENTITIES = [
    # 规则越靠前解析优先级越高。
    # 跳转到容器监控（仅当存在 bcs_cluster_id），默认跳转到新版。
    # 注意：bcs_cluster_id 存在的情况下，host 形式是 "node-127-0-0-1"，此时跳转到旧版容器监控页面的 Node
    {
        "type": "k8s",
        "alias": _("容器"),
        "fields": ["container_id", "namespace", "bcs_cluster_id", "host"],
        # 原始数据存在这个字段，本规则才生效
        "dependent_fields": ["bcs_cluster_id"],
    },
    # 跳转到主机监控
    {"type": "ip", "alias": _("主机"), "fields": ["host", "bk_target_ip", "ip", "serverip", "bk_host_id"]},
]

DEFAULT_DIMENSION_FIELDS = ["time", "event_name", "event.content", "target", "type"]
