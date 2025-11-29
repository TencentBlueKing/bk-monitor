"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from bkmonitor.models import AlgorithmModel
from constants.apm import CachedEnum
from constants.data_source import ResultTableLabelObj

DEFAULT_ROOT_ID: int = 0

DEFAULT_DETECT_TYPE: str = "default"

BUILTIN_USER_GROUP_ID: int = -9999


class ThresholdLevel(CachedEnum):
    """告警级别"""

    FATAL = 1
    WARNING = 2
    REMINDER = 3

    @classmethod
    def choices(cls) -> list[tuple[int, str]]:
        return [(member.value, member.label) for member in cls]

    @cached_property
    def label(self) -> str:
        return str({self.FATAL: _("致命"), self.WARNING: _("预警"), self.REMINDER: _("提醒")}.get(self, self.value))


class AlgorithmType(CachedEnum):
    """算法类型"""

    THRESHOLD = AlgorithmModel.AlgorithmChoices.Threshold
    ADVANCED_YEAR_ROUND = AlgorithmModel.AlgorithmChoices.AdvancedYearRound
    YEAR_ROUND_AND_RING_RATIO = "YearRoundAndRingRatio"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]

    @cached_property
    def label(self) -> str:
        return str({self.THRESHOLD: _("静态阈值"), self.YEAR_ROUND_AND_RING_RATIO: _("同环比")}.get(self, self.value))


class AlgorithmYearRoundAndRingRatioMethod(CachedEnum):
    """同环比方法"""

    FIVE_MINUTE_RING_RATIO = "FiveMinuteRingRatio"
    YESTERDAY_COMPARISON = "YesterdayComparison"
    LAST_WEEK_COMPARISON = "LastWeekComparison"
    WEEKLY_AVERAGE_COMPARISON = "WeeklyAverageComparison"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]

    @cached_property
    def label(self) -> str:
        return str(
            {
                self.FIVE_MINUTE_RING_RATIO: _("前五分钟对比"),
                self.YESTERDAY_COMPARISON: _("昨天同期对比"),
                self.LAST_WEEK_COMPARISON: _("上周同期对比"),
                self.WEEKLY_AVERAGE_COMPARISON: _("前七天同期均值对比"),
            }.get(self, self.value)
        )

    @cached_property
    def config(self) -> dict[str, Any]:
        return {
            self.FIVE_MINUTE_RING_RATIO: {
                "ceil_interval": 5,
                "floor_interval": 5,
                "fetch_type": "last",
                "type": AlgorithmModel.AlgorithmChoices.AdvancedRingRatio,
            },
            self.YESTERDAY_COMPARISON: {
                "ceil_interval": 1,
                "floor_interval": 1,
                "fetch_type": "avg",
                "type": AlgorithmModel.AlgorithmChoices.AdvancedYearRound,
            },
            self.LAST_WEEK_COMPARISON: {
                "ceil_interval": 7,
                "floor_interval": 7,
                "fetch_type": "last",
                "type": AlgorithmModel.AlgorithmChoices.AdvancedYearRound,
            },
            self.WEEKLY_AVERAGE_COMPARISON: {
                "ceil_interval": 7,
                "floor_interval": 7,
                "fetch_type": "avg",
                "type": AlgorithmModel.AlgorithmChoices.AdvancedYearRound,
            },
        }.get(self, {})


class DetectConnector(CachedEnum):
    """检测连接符"""

    AND = "and"
    OR = "or"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]

    @cached_property
    def label(self) -> str:
        return str({self.AND: _("且"), self.OR: _("或")}.get(self, self.value))


class StrategyTemplateType(CachedEnum):
    """策略模板类型"""

    APP_TEMPLATE = "app"
    BUILTIN_TEMPLATE = "builtin"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]

    @cached_property
    def label(self) -> str:
        return str({self.APP_TEMPLATE: _("克隆模板"), self.BUILTIN_TEMPLATE: _("内置模板")}.get(self, self.value))


class StrategyTemplateSystem(CachedEnum):
    """策略模板类型"""

    RPC = "RPC"
    K8S = "K8S"
    LOG = "LOG"
    TRACE = "TRACE"
    EVENT = "EVENT"
    METRIC = "METRIC"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]

    @cached_property
    def label(self) -> str:
        return str(
            {
                self.RPC: _("调用分析"),
                self.K8S: _("容器"),
                self.LOG: _("日志"),
                self.TRACE: _("调用链"),
                self.EVENT: _("事件"),
                self.METRIC: _("指标"),
            }.get(self, self.value)
        )

    @cached_property
    def scenario(self) -> str:
        return {self.K8S: ResultTableLabelObj.KubernetesObject.kubernetes}.get(
            self, ResultTableLabelObj.ApplicationsObj.apm
        )


class StrategyTemplateCategory(CachedEnum):
    """策略模板分类"""

    DEFAULT = "DEFAULT"
    RPC_CALLEE = "RPC_CALLEE"
    RPC_CALLER = "RPC_CALLER"
    RPC_METRIC = "RPC_METRIC"
    RPC_LOG = "RPC_LOG"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]

    @cached_property
    def label(self) -> str:
        return str(
            {
                self.DEFAULT: _("默认"),
                self.RPC_CALLEE: _("被调"),
                self.RPC_CALLER: _("主调"),
                self.RPC_METRIC: _("自定义指标"),
                self.RPC_LOG: _("日志"),
            }.get(self, self.value)
        )


class StrategyTemplateMonitorType(CachedEnum):
    """策略模板数据类型"""

    # DEFAULT
    DEFAULT = "DEFAULT"

    # RED
    P99 = "P99"
    AVG = "AVG"
    SUCCESS_RATE = "SUCCESS_RATE"

    # 事件
    CICD = "CICD"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(member.value, member.label) for member in cls]

    @cached_property
    def label(self) -> str:
        return str(
            {
                self.DEFAULT: _("默认"),
                self.P99: _("耗时分位"),
                self.AVG: _("平均耗时"),
                self.SUCCESS_RATE: _("成功率"),
                self.CICD: _("CICD"),
            }.get(self, self.value)
        )


class StrategyTemplateIsEnabled(CachedEnum):
    """策略模板启用状态"""

    ENABLED = True
    DISABLED = False

    @classmethod
    def choices(cls) -> list[tuple[bool, str]]:
        return [(member.value, member.label) for member in cls]

    @cached_property
    def label(self) -> str:
        return str(
            {
                self.ENABLED: _("启用"),
                self.DISABLED: _("禁用"),
            }.get(self, str(self.value))
        )


class StrategyTemplateIsAutoApply(CachedEnum):
    """新服务自动下发状态"""

    ENABLED = True
    DISABLED = False

    @classmethod
    def choices(cls) -> list[tuple[bool, str]]:
        return [(member.value, member.label) for member in cls]

    @cached_property
    def label(self) -> str:
        return str(
            {
                self.ENABLED: _("已启用新服务自动下发"),
                self.DISABLED: _("未启用新服务自动下发"),
            }.get(self, str(self.value))
        )
