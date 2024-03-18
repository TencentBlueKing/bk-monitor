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
import typing

from django.utils.translation import gettext_lazy as _

from bkmonitor.models import NO_DATA_TAG_DIMENSION


class EventTargetType:
    EMPTY = ""
    HOST = "HOST"
    SERVICE = "SERVICE"
    TOPO = "TOPO"


EVENT_TARGET_TYPE = (
    (EventTargetType.EMPTY, _("无")),
    (EventTargetType.HOST, _("主机")),
    (EventTargetType.SERVICE, _("服务实例")),
    (EventTargetType.TOPO, _("拓扑")),
)


class AlertFieldDisplay:
    ID = _("告警ID")
    RELATED_INFO = _("关联信息")


class EventStatus:
    CLOSED = "CLOSED"
    RECOVERED = "RECOVERED"
    ABNORMAL = "ABNORMAL"
    RECOVERING = "RECOVERING"


EVENT_STATUS = (
    (EventStatus.ABNORMAL, _("未恢复")),
    (EventStatus.RECOVERED, _("已恢复")),
    (EventStatus.CLOSED, _("已关闭")),
)

EVENT_STATUS_DICT = {status: desc for (status, desc) in EVENT_STATUS}


class HandleStage:
    NOISE_REDUCE = "noise_reduce"
    HANDLE = "handle"
    SHIELD = "shield"
    ACK = "ack"


HANDLE_STAGE = (
    (HandleStage.NOISE_REDUCE, _("已抑制")),
    (HandleStage.HANDLE, _("已通知")),
    (HandleStage.SHIELD, _("已屏蔽")),
    (HandleStage.ACK, _("已确认")),
)

HANDLE_STAGE_DICT = {stage: display for (stage, display) in HANDLE_STAGE}


class EventSeverity:
    FATAL = 1
    WARNING = 2
    REMIND = 3

    EVENT_SEVERITY = (
        (FATAL, _("致命")),
        (WARNING, _("预警")),
        (REMIND, _("提醒")),
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
    NO_DATA_TAG_DIMENSION,
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


OLD_DEFAULT_TEMPLATE: str = (
    "{{content.level}}\n"
    "{{content.begin_time}}\n"
    "{{content.time}}\n"
    "{{content.duration}}\n"
    "{{content.target_type}}\n"
    "{{content.data_source}}\n"
    "{{content.content}}\n"
    "{{content.current_value}}\n"
    "{{content.biz}}\n"
    "{{content.target}}\n"
    "{{content.dimension}}\n"
    "{{content.detail}}\n"
    "{{content.assign_detail}}\n"
    "{{content.related_info}}\n"
)

DEFAULT_TEMPLATE: str = OLD_DEFAULT_TEMPLATE + "{{content.recommended_metrics}}\n" "{{content.anomaly_dimensions}}\n"

DEFAULT_TITLE_TEMPLATE: str = "{{business.bk_biz_name}} - {{alarm.name}} {{alarm.display_type}}"


# TODO(crayon) 灰度验证无误后再进行调整
DEFAULT_NOTICE_MESSAGE_TEMPLATE: typing.List[typing.Dict[str, str]] = [
    {"signal": "abnormal", "message_tmpl": OLD_DEFAULT_TEMPLATE, "title_tmpl": DEFAULT_TITLE_TEMPLATE},
    {"signal": "recovered", "message_tmpl": OLD_DEFAULT_TEMPLATE, "title_tmpl": DEFAULT_TITLE_TEMPLATE},
    {"signal": "closed", "message_tmpl": OLD_DEFAULT_TEMPLATE, "title_tmpl": DEFAULT_TITLE_TEMPLATE},
]


PUBLIC_NOTICE_CONFIG: typing.Dict[str, typing.Union[str, typing.List[typing.Dict]]] = {
    "alert_notice": [
        {
            "time_range": "00:00:00--23:59:59",
            "notify_config": [
                {"level": 1, "type": ["weixin", "mail"]},
                {"level": 2, "type": ["weixin", "mail"]},
                {"level": 3, "type": ["weixin", "mail"]},
            ],
        }
    ],
    "action_notice": [
        {
            "time_range": "00:00:00--23:59:59",
            "notify_config": [
                {"phase": 1, "type": ["mail"]},
                {"phase": 2, "type": ["mail"]},
                {"phase": 3, "type": ["mail"]},
            ],
        }
    ],
    "message": "",
}


DEFAULT_NOTICE_GROUPS: typing.List[typing.Dict[str, typing.Any]] = [
    {
        "name": _("主备负责人"),
        "notice_receiver": [{"id": "operator", "type": "group"}, {"id": "bk_bak_operator", "type": "group"}],
        **PUBLIC_NOTICE_CONFIG,
    },
    {"name": _("运维"), "notice_receiver": [{"id": "bk_biz_maintainer", "type": "group"}], **PUBLIC_NOTICE_CONFIG},
    {"name": _("开发"), "notice_receiver": [{"id": "bk_biz_developer", "type": "group"}], **PUBLIC_NOTICE_CONFIG},
    {"name": _("测试"), "notice_receiver": [{"id": "bk_biz_tester", "type": "group"}], **PUBLIC_NOTICE_CONFIG},
    {"name": _("产品"), "notice_receiver": [{"id": "bk_biz_productor", "type": "group"}], **PUBLIC_NOTICE_CONFIG},
]
