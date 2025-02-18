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
from enum import Enum


class EventDimensionTypeEnum(Enum):
    """
    事件维度类型枚举
    """

    KEYWORD: str = "keyword"
    TEXT: str = "text"
    INTEGER: str = "integer"
    DATE: str = "date"


class EventDataLabelEnum(Enum):
    """
    数据标签枚举
    """

    SYSTEM_EVENT: str = "system_event"
    K8S_EVENT: str = "k8s_event"
    CICD_EVENT: str = "cicd_event"


# 事件字段别名
EVENT_FIELD_ALIAS = {
    "common": {
        "event_name": "事件名",
        "event.content": "事件内容",
        "target": "目标",
        "bk_biz_id": "业务",
        "bk_cloud_id": "管控区域",
        "bk_target_cloud_id": "管控区域",
        "bk_target_ip": "IP",
        "ip": "IP",
        "bk_agent_id": "AgentID",
        "domain": "事件领域",
        "source": "事件来源",
    },
    "system_event": {
        "process": "进程",
        "oom_memcg": "实际内存 cgroup",
        "task_memcg": "进程所属内存 cgroup",
        "file_system": "文件系统",
        "fstype": "文件系统类型",
        "disk": "磁盘",
    },
    "k8s_event": {
        "bcs_cluster_id": "集群 ID",
        "host": "IP",
        "type": "事件类型",
        "uid": "资源对象 Unique ID",
        "apiVersion": "资源对象 API 版本",
        "kind": "资源对象类型",
        "namespace": "资源对象命名空间",
        "name": "资源对象名称",
    },
    "cicd_event": {
        "source": "事件来源",
        "duration": "持续时间",
        "start_time": "启动时间",
        "typeti": "事件优先级",
        "projectId": "项目 ID",
        "pipelineId": "流水线 ID",
        "pipelineName": "流水线名称",
        "trigger": "任务类型",
        "triggerUser": "任务创建用户",
        "buildId": "任务 ID",
        "status": "任务状态",
    },
}

DISPLAY_FIELDS = [
    {"name": "time", "alias": "数据上报时间"},
    {"name": "type", "alias": "事件级别", "type": "attach"},
    {"name": "event_name", "alias": "事件名"},
    {"name": "event.content", "alias": "内容", "type": "descriptions"},
    {"name": "target", "alias": "目标", "type": "link"},
]

# 内置字段类型映射集
INNER_FIELD_TYPE_MAPPINGS = {
    "time": EventDimensionTypeEnum.DATE.value,
    "event_name": EventDimensionTypeEnum.KEYWORD.value,
    "event.content": EventDimensionTypeEnum.KEYWORD.value,
    "target": EventDimensionTypeEnum.KEYWORD.value,
}


# 查询操作符
class Operation:
    EQ = [{"alias": "=", "value": "eq"}, {"alias": "!=", "value": "ne"}]
    NE = {"alias": "!=", "value": "ne"}
    INCLUDE = {"alias": "包含", "value": "include"}
    EXCLUDE = {"alias": "不包含", "value": "exclude"}
    EQ_WITH_WILDCARD = {"alias": "包含", "value": "eq", "options": {"label": "使用通配符", "name": "is_wildcard"}}
    NE_WITH_WILDCARD = {"alias": "不包含", "value": "ne", "options": {"label": "使用通配符", "name": "is_wildcard"}}


# 类型和操作符映射
TYPE_OPERATION_MAPPINGS = {
    "time": [Operation.EQ, Operation.NE],
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
        "alias": "容器",
        "fields": ["container_id", "namespace", "bcs_cluster_id", "host"],
        # 原始数据存在这个字段，本规则才生效
        "dependent_fields": ["bcs_cluster_id"],
    },
    # 跳转到主机监控
    {"type": "ip", "alias": "主机", "fields": ["host", "bk_target_ip", "ip", "serverip", "bk_host_id"]},
]
