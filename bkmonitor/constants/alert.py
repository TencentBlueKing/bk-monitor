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

from django.utils.translation import ugettext_lazy as _lazy

from bkmonitor.models import NO_DATA_TAG_DIMENSION


class EventTargetType:
    EMPTY = ""
    HOST = "HOST"
    SERVICE = "SERVICE"
    TOPO = "TOPO"


EVENT_TARGET_TYPE = (
    (EventTargetType.EMPTY, _lazy("无")),
    (EventTargetType.HOST, _lazy("主机")),
    (EventTargetType.SERVICE, _lazy("服务实例")),
    (EventTargetType.TOPO, _lazy("拓扑")),
)


class AlertFieldDisplay:
    ID = _lazy("告警ID")
    RELATED_INFO = _lazy("关联信息")


class EventStatus:
    CLOSED = "CLOSED"
    RECOVERED = "RECOVERED"
    ABNORMAL = "ABNORMAL"
    RECOVERING = "RECOVERING"


EVENT_STATUS = (
    (EventStatus.ABNORMAL, _lazy("未恢复")),
    (EventStatus.RECOVERED, _lazy("已恢复")),
    (EventStatus.CLOSED, _lazy("已关闭")),
)

EVENT_STATUS_DICT = {status: desc for (status, desc) in EVENT_STATUS}


class HandleStage:
    NOISE_REDUCE = "noise_reduce"
    HANDLE = "handle"
    SHIELD = "shield"
    ACK = "ack"


HANDLE_STAGE = (
    (HandleStage.NOISE_REDUCE, _lazy("已抑制")),
    (HandleStage.HANDLE, _lazy("已通知")),
    (HandleStage.SHIELD, _lazy("已屏蔽")),
    (HandleStage.ACK, _lazy("已确认")),
)

HANDLE_STAGE_DICT = {stage: display for (stage, display) in HANDLE_STAGE}


class EventSeverity:
    FATAL = 1
    WARNING = 2
    REMIND = 3

    EVENT_SEVERITY = (
        (FATAL, _lazy("致命")),
        (WARNING, _lazy("预警")),
        (REMIND, _lazy("提醒")),
    )

    EVENT_SEVERITY_DICT = {status: desc for (status, desc) in EVENT_SEVERITY}

    @staticmethod
    def get_display_name(severity):
        return EVENT_SEVERITY_DICT.get(severity, severity)


EVENT_SEVERITY = EventSeverity.EVENT_SEVERITY


class AlertAssignSeverity(EventSeverity):
    KEEP = 0


EVENT_SEVERITY_DICT = EventSeverity.EVENT_SEVERITY_DICT

# 展示时需要忽略的标签
IGNORED_TAGS = (
    "bk_target_ip",
    "bk_target_cloud_id",
    "bk_target_service_instance_id",
    "bk_topo_node",
    "bk_cloud_id",
    "bk_obj_id",
    "bk_inst_id",
    "ip",
    "bk_cloud_id",
    "bk_host_id",
    NO_DATA_TAG_DIMENSION
)

TARGET_DIMENSIONS = [
    "bk_target_ip",
    "bk_target_cloud_id",
    "bk_target_service_instance_id",
    "ip",
    "bk_cloud_id",
    "bk_topo_node",
    "bk_service_instance_id",
    "target",
    "target_type",
    "bk_host_id",
]

DEFAULT_DEDUPE_FIELDS = ["alert_name", "strategy_id", "target_type", "target", "bk_biz_id"]

CLUSTER_PATTERN = r"{[^}]+}"
