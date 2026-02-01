"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import typing
from functools import cached_property

from django.utils.translation import gettext_lazy as _

from bkmonitor.models import NO_DATA_TAG_DIMENSION

from constants.apm import CachedEnum


class EventTargetType:
    EMPTY = ""
    HOST = "HOST"
    SERVICE = "SERVICE"
    TOPO = "TOPO"


class K8STargetType:
    POD = "K8S-POD"
    NODE = "K8S-NODE"
    SERVICE = "K8S-SERVICE"
    WORKLOAD = "K8S-WORKLOAD"


K8S_RESOURCE_TYPE = {
    K8STargetType.POD: "pod",
    K8STargetType.NODE: "node",
    K8STargetType.SERVICE: "service",
    K8STargetType.WORKLOAD: "workload",
}


class APMTargetType:
    SERVICE = "APM-SERVICE"

    @staticmethod
    def parse_target(target: str) -> tuple[str, str]:
        """解析 APM 场景的 target 目标格式"""
        app_name, service_name = target.split(":", 1)
        return app_name, service_name


EVENT_EXTRA_TARGET_TYPE = (
    K8STargetType.POD,
    K8STargetType.NODE,
    K8STargetType.SERVICE,
    K8STargetType.WORKLOAD,
    APMTargetType.SERVICE,
)


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
    (EventStatus.CLOSED, _("已失效")),
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

CMDB_TARGET_DIMENSIONS = [
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

DEFAULT_TEMPLATE: str = OLD_DEFAULT_TEMPLATE + "{{content.recommended_metrics}}\n{{content.anomaly_dimensions}}\n"

DEFAULT_TITLE_TEMPLATE: str = "{{business.bk_biz_name}} - {{alarm.name}} {{alarm.display_type}}"


# TODO(crayon) 灰度验证无误后再进行调整
DEFAULT_NOTICE_MESSAGE_TEMPLATE: list[dict[str, str]] = [
    {"signal": "abnormal", "message_tmpl": OLD_DEFAULT_TEMPLATE, "title_tmpl": DEFAULT_TITLE_TEMPLATE},
    {"signal": "recovered", "message_tmpl": OLD_DEFAULT_TEMPLATE, "title_tmpl": DEFAULT_TITLE_TEMPLATE},
    {"signal": "closed", "message_tmpl": OLD_DEFAULT_TEMPLATE, "title_tmpl": DEFAULT_TITLE_TEMPLATE},
]


PUBLIC_NOTICE_CONFIG: dict[str, str | list[dict]] = {
    "alert_notice": [
        {
            "time_range": "00:00:00--23:59:59",
            "notify_config": [
                {"level": 1, "type": ["mail"]},
                {"level": 2, "type": ["mail"]},
                {"level": 3, "type": ["mail"]},
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


DEFAULT_NOTICE_GROUPS: list[dict[str, typing.Any]] = [
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


class AlertRedirectType(CachedEnum):
    DETAIL = "detail"
    QUERY = "query"
    LOG_SEARCH = "log_search"
    EVENT_EXPLORE = "event_explore"
    APM_RPC = "apm_rpc"
    APM_TRACE = "apm_trace"
    APM_QUERY = "apm_query"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]

    @cached_property
    def label(self) -> str:
        return str(
            {
                self.DETAIL: _("告警详情"),
                self.QUERY: _("指标检索"),
                self.LOG_SEARCH: _("日志检索"),
                self.EVENT_EXPLORE: _("事件检索"),
                self.APM_RPC: _("调用分析"),
                self.APM_TRACE: _("Tracing 检索"),
                # APM 自定义指标检索
                self.APM_QUERY: _("指标检索"),
            }.get(self, self.value)
        )
