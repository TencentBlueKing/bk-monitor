"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from dataclasses import dataclass, field

from django.conf import settings
from django.utils.translation import gettext as _

from constants.aiops import MULTIVARIATE_ANOMALY_DETECTION_SCENE_INPUT_FIELD, SceneSet
from constants.data_source import DataSourceLabel, DataTypeLabel


# Agent状态
class AGENT_STATUS:
    UNKNOWN = -1
    ON = 0
    OFF = 1
    NOT_EXIST = 2
    NO_DATA = 3


UPTIME_CHECK_DB = "uptimecheck"


class AlgorithmType:
    Threshold = "Threshold"
    SimpleRingRatio = "SimpleRingRatio"
    AdvancedRingRatio = "AdvancedRingRatio"
    SimpleYearRound = "SimpleYearRound"
    AdvancedYearRound = "AdvancedYearRound"
    PartialNodes = "PartialNodes"


class EventLevel:
    EVENT_LEVEL = (
        (1, _("致命")),
        (2, _("预警")),
        (3, _("提醒")),
    )
    EVENT_LEVEL_MAP = dict(list(EVENT_LEVEL))


class EVENT_TYPE:
    """事件类型"""

    CUSTOM_EVENT = "custom_event"
    KEYWORDS = "keywords"
    SYSTEM = "system"


class ETL_CONFIG:
    """数据清洗类型"""

    CUSTOM_EVENT = "bk_standard_v2_event"
    CUSTOM_TS = "bk_standard_v2_time_series"


EVENT_FIELD_CHINESE = dict(
    id="ID",
    bk_biz_id=_("业务ID"),
    anomaly_count=_("告警次数"),
    duration=_("持续时间"),
    begin_time=_("发生时间"),
    strategy_name=_("触发策略"),
    event_message=_("通知内容"),
    alert_status=_("最近通知状态"),
    event_status=_("告警状态"),
    level=_("告警等级"),
    is_ack=_("是否确认"),
    ack_user=_("确认用户"),
    ack_message=_("确认信息"),
    target_key=_("目标"),
    is_shielded=_("是否屏蔽"),
    shield_type=_("屏蔽类型"),
)


# 多指标异常检测主机场景默认select
MULTIVARIATE_ANOMALY_DETECTION_SCENE_HOST_FILTER_FIELDS = [
    "bk_biz_id",
    "ip",
    "bk_cloud_id",
    "bk_target_ip",
    "bk_target_cloud_id",
]


@dataclass
class MultivariateAnomalyDetectionSceneParams:
    agg_dimensions: list
    sql_build_params: dict
    intelligent_detect_config: dict


@dataclass
class HostSceneParams(MultivariateAnomalyDetectionSceneParams):
    agg_dimensions: list = field(default_factory=lambda: MULTIVARIATE_ANOMALY_DETECTION_SCENE_HOST_FILTER_FIELDS)
    sql_build_params: dict = field(
        default_factory=lambda: {
            "data_source_label": DataSourceLabel.BK_DATA,
            "data_type_label": DataTypeLabel.TIME_SERIES,
            "result_table_id": settings.BK_DATA_MULTIVARIATE_HOST_RT_ID,
            "agg_dimension": [],
            "agg_condition": [],
            "value_fields": MULTIVARIATE_ANOMALY_DETECTION_SCENE_HOST_FILTER_FIELDS
            + [MULTIVARIATE_ANOMALY_DETECTION_SCENE_INPUT_FIELD],
        }
    )
    intelligent_detect_config: dict = field(
        default_factory=lambda: {
            "scene_id": settings.BK_DATA_SCENE_ID_MULTIVARIATE_ANOMALY_DETECTION,
            "plan_id": settings.BK_DATA_PLAN_ID_MULTIVARIATE_ANOMALY_DETECTION,
        }
    )


# 多指标异常检测场景对应dataclass类
MULTIVARIATE_ANOMALY_DETECTION_SCENE_PARAMS_MAP = {SceneSet.HOST: HostSceneParams}

OVERVIEW_ICON = "data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4KPHN2ZyB3aWR0aD0iMTZweCIgaGVpZ2h0PSIxNnB4IiB2aWV3Qm94PSIwIDAgMTYgMTYiIHZlcnNpb249IjEuMSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB4bWxuczp4bGluaz0iaHR0cDovL3d3dy53My5vcmcvMTk5OS94bGluayI+CiAgICA8dGl0bGU+aWNvbi/mpoLop4gv5bey6YCJ5oupPC90aXRsZT4KICAgIDxnIGlkPSJpY29uL+amguiniC/lt7LpgInmi6kiIHN0cm9rZT0ibm9uZSIgc3Ryb2tlLXdpZHRoPSIxIiBmaWxsPSJub25lIiBmaWxsLXJ1bGU9ImV2ZW5vZGQiPgogICAgICAgIDxnIGlkPSLnvJbnu4QiIHRyYW5zZm9ybT0idHJhbnNsYXRlKDEuMDAwMDAwLCAxLjAwMDAwMCkiPgogICAgICAgICAgICA8cmVjdCBpZD0i55+p5b2iIiBmaWxsPSIjM0E4NEZGIiBmaWxsLXJ1bGU9Im5vbnplcm8iIHg9IjAiIHk9IjAiIHdpZHRoPSI1IiBoZWlnaHQ9IjE0Ij48L3JlY3Q+CiAgICAgICAgICAgIDxyZWN0IGlkPSLnn6nlvaLlpIfku70iIGZpbGw9IiM2MUIyQzIiIHg9IjYiIHk9IjAiIHdpZHRoPSI4IiBoZWlnaHQ9IjMiPjwvcmVjdD4KICAgICAgICAgICAgPHJlY3QgaWQ9IuefqeW9ouWkh+S7vS0yIiBmaWxsPSIjRkZCODQ4IiB4PSI2IiB5PSI0IiB3aWR0aD0iOCIgaGVpZ2h0PSIxMCI+PC9yZWN0PgogICAgICAgIDwvZz4KICAgIDwvZz4KPC9zdmc+"  # noqa

# 图表类型
GRAPH_RATIO_RING = "ratio-ring"
GRAPH_TIME_SERIES = "time_series"
GRAPH_PERCENTAGE_BAR = "percentage-bar"
GRAPH_NUMBER_CHART = "number-chart"
GRAPH_RESOURCE = "resource"
GRAPH_STATUS_LIST = "status-list"
GRAPH_COLUMN_BAR = "column-bar"
GRAPH_STATUS_LIST = "status-list"

AIOPS_ACCESS_MAX_RETRIES = 3
AIOPS_ACCESS_RETRY_INTERVAL = 5 * 60
AIOPS_ACCESS_STATUS_POLLING_INTERVAL = 30
