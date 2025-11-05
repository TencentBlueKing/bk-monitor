"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any
from functools import cached_property

from django.utils.translation import gettext as _

from constants.query_template import GLOBAL_BIZ_ID
from bkmonitor.query_template.builtin.apm import APMQueryTemplateName
from apm_web.strategy.query_template import LocalQueryTemplateName
from constants.apm import RPCMetricTag, CachedEnum, CommonMetricTag

from . import base
from .. import utils
from ... import constants


def _get_common_group_by() -> list[str]:
    group_by: list[str] = [
        CommonMetricTag.APP_NAME.value,
        RPCMetricTag.SERVICE_NAME.value,
        RPCMetricTag.ENV_NAME.value,
        RPCMetricTag.NAMESPACE.value,
        RPCMetricTag.CALLEE_METHOD.value,
    ]
    return group_by


def _get_common_context(threshold: int = 10, extra_group_by: list[str] | None = None) -> dict[str, Any]:
    return {"ALARM_THRESHOLD_VALUE": threshold, "GROUP_BY": _get_common_group_by() + (extra_group_by or [])}


class RPCStrategyTemplateCode(CachedEnum):
    RPC_CALLEE_SUCCESS_RATE = "rpc_callee_success_rate"
    RPC_CALLEE_AVG_TIME = "rpc_callee_avg_time"
    RPC_CALLEE_P99 = "rpc_callee_p99"
    # 处理请求量波动告警
    RPC_CALLEE_REQ_FLUCTUATION = "rpc_callee_req_fluctuation"
    RPC_CALLEE_ERROR_CODE = "rpc_callee_error_code"
    RPC_CALLER_SUCCESS_RATE = "rpc_caller_success_rate"
    RPC_CALLER_AVG_TIME = "rpc_caller_avg_time"
    RPC_CALLER_P99 = "rpc_caller_p99"
    RPC_CALLER_ERROR_CODE = "rpc_caller_error_code"
    RPC_METRIC_GO_GOROUTINE_FLUCTUATION = "rpc_metric_go_goroutine_fluctuation"
    RPC_ERROR_METRIC_PANIC = "rpc_error_metric_panic"
    RPC_ERROR_LOG_PANIC = "rpc_error_log_panic"

    @cached_property
    def label(self) -> str:
        return str(
            {
                self.RPC_CALLEE_SUCCESS_RATE: _("被调成功率告警"),
                self.RPC_CALLEE_AVG_TIME: _("被调平均耗时告警"),
                self.RPC_CALLEE_P99: _("被调 P99 耗时告警"),
                self.RPC_CALLEE_ERROR_CODE: _("被调错误码告警"),
                self.RPC_CALLEE_REQ_FLUCTUATION: _("被调请求量波动告警"),
                self.RPC_CALLER_SUCCESS_RATE: _("主调成功率告警"),
                self.RPC_CALLER_AVG_TIME: _("主调平均耗时告警"),
                self.RPC_CALLER_P99: _("主调 P99 耗时告警"),
                self.RPC_CALLER_ERROR_CODE: _("主调错误码告警"),
                self.RPC_METRIC_GO_GOROUTINE_FLUCTUATION: _("Go 协程数量波动告警"),
                self.RPC_ERROR_METRIC_PANIC: _("Panic 指标告警"),
                self.RPC_ERROR_LOG_PANIC: _("Panic 日志关键字告警"),
            }.get(self, self.value)
        )


RPC_CALLEE_SUCCESS_RATE_STRATEGY_TEMPLATE: dict[str, Any] = {
    "code": RPCStrategyTemplateCode.RPC_CALLEE_SUCCESS_RATE.value,
    "name": RPCStrategyTemplateCode.RPC_CALLEE_SUCCESS_RATE.label,
    "category": constants.StrategyTemplateCategory.RPC_CALLEE.value,
    "monitor_type": constants.StrategyTemplateMonitorType.SUCCESS_RATE.value,
    "detect": utils.detect_config(5, 5, 3),
    "algorithms": [
        utils.warning_threshold_algorithm_config(method="lte", threshold=99, suffix="%"),
        utils.fatal_threshold_algorithm_config(method="lte", threshold=95, suffix="%"),
    ],
    "query_template": {"bk_biz_id": GLOBAL_BIZ_ID, "name": APMQueryTemplateName.RPC_CALLEE_SUCCESS_RATE.value},
    "context": _get_common_context(),
}

RPC_CALLEE_AVG_TIME_STRATEGY_TEMPLATE: dict[str, Any] = {
    "code": RPCStrategyTemplateCode.RPC_CALLEE_AVG_TIME.value,
    "name": RPCStrategyTemplateCode.RPC_CALLEE_AVG_TIME.label,
    "category": constants.StrategyTemplateCategory.RPC_CALLEE.value,
    "monitor_type": constants.StrategyTemplateMonitorType.AVG.value,
    "detect": utils.detect_config(5, 5, 3),
    "algorithms": [
        utils.warning_threshold_algorithm_config(method="gte", threshold=2000, suffix="ms"),
        utils.fatal_threshold_algorithm_config(method="gte", threshold=4000, suffix="ms"),
    ],
    "query_template": {"bk_biz_id": GLOBAL_BIZ_ID, "name": APMQueryTemplateName.RPC_CALLEE_AVG_TIME.value},
    "context": _get_common_context(),
}

RPC_CALLEE_P99_STRATEGY_TEMPLATE: dict[str, Any] = {
    "code": RPCStrategyTemplateCode.RPC_CALLEE_P99.value,
    "name": RPCStrategyTemplateCode.RPC_CALLEE_P99.label,
    "category": constants.StrategyTemplateCategory.RPC_CALLEE.value,
    "monitor_type": constants.StrategyTemplateMonitorType.P99.value,
    "detect": utils.detect_config(5, 5, 3),
    "algorithms": [
        utils.warning_threshold_algorithm_config(method="gte", threshold=3000, suffix="ms"),
        utils.fatal_threshold_algorithm_config(method="gte", threshold=5000, suffix="ms"),
    ],
    "query_template": {"bk_biz_id": GLOBAL_BIZ_ID, "name": APMQueryTemplateName.RPC_CALLEE_P99.value},
    "context": _get_common_context(),
}

RPC_CALLEE_ERROR_CODE_STRATEGY_TEMPLATE: dict[str, Any] = {
    "code": RPCStrategyTemplateCode.RPC_CALLEE_ERROR_CODE.value,
    "name": RPCStrategyTemplateCode.RPC_CALLEE_ERROR_CODE.label,
    "category": constants.StrategyTemplateCategory.RPC_CALLEE.value,
    "monitor_type": constants.StrategyTemplateMonitorType.DEFAULT.value,
    "detect": utils.detect_config(5, 5, 3),
    "algorithms": [
        utils.warning_threshold_algorithm_config(method="gte", threshold=10),
        utils.fatal_threshold_algorithm_config(method="gte", threshold=50),
    ],
    "query_template": {"bk_biz_id": GLOBAL_BIZ_ID, "name": APMQueryTemplateName.RPC_CALLEE_ERROR_CODE.value},
    "context": _get_common_context(extra_group_by=[RPCMetricTag.CODE.value]),
}

RPC_CALLEE_REQ_FLUCTUATION_STRATEGY_TEMPLATE: dict[str, Any] = {
    "code": RPCStrategyTemplateCode.RPC_CALLEE_REQ_FLUCTUATION.value,
    "name": RPCStrategyTemplateCode.RPC_CALLEE_REQ_FLUCTUATION.label,
    "category": constants.StrategyTemplateCategory.RPC_CALLEE.value,
    "monitor_type": constants.StrategyTemplateMonitorType.DEFAULT.value,
    "detect": utils.detect_config(5, 3, 3),
    "algorithms": [
        utils.warning_year_round_and_ring_ratio_algorithm_config(
            method=constants.AlgorithmYearRoundAndRingRatioMethod.WEEKLY_AVERAGE_COMPARISON,
            ceil=30,
            floor=30,
        ),
        utils.fatal_year_round_and_ring_ratio_algorithm_config(
            method=constants.AlgorithmYearRoundAndRingRatioMethod.WEEKLY_AVERAGE_COMPARISON,
            ceil=100,
            floor=100,
        ),
    ],
    "query_template": {"bk_biz_id": GLOBAL_BIZ_ID, "name": APMQueryTemplateName.RPC_CALLEE_REQ_TOTAL.value},
    "context": _get_common_context(threshold=0),
}


RPC_CALLER_SUCCESS_RATE_STRATEGY_TEMPLATE: dict[str, Any] = {
    "code": RPCStrategyTemplateCode.RPC_CALLER_SUCCESS_RATE.value,
    "name": RPCStrategyTemplateCode.RPC_CALLER_SUCCESS_RATE.label,
    "category": constants.StrategyTemplateCategory.RPC_CALLER.value,
    "monitor_type": constants.StrategyTemplateMonitorType.SUCCESS_RATE.value,
    "detect": utils.detect_config(5, 5, 3),
    "algorithms": [
        utils.warning_threshold_algorithm_config(method="lte", threshold=99, suffix="%"),
        utils.fatal_threshold_algorithm_config(method="lte", threshold=95, suffix="%"),
    ],
    "query_template": {"bk_biz_id": GLOBAL_BIZ_ID, "name": APMQueryTemplateName.RPC_CALLER_SUCCESS_RATE.value},
    "context": _get_common_context(),
}

RPC_CALLER_AVG_TIME_STRATEGY_TEMPLATE: dict[str, Any] = {
    "code": RPCStrategyTemplateCode.RPC_CALLER_AVG_TIME.value,
    "name": RPCStrategyTemplateCode.RPC_CALLER_AVG_TIME.label,
    "category": constants.StrategyTemplateCategory.RPC_CALLER.value,
    "monitor_type": constants.StrategyTemplateMonitorType.AVG.value,
    "detect": utils.detect_config(5, 5, 3),
    "algorithms": [
        utils.warning_threshold_algorithm_config(method="gte", threshold=2000, suffix="ms"),
        utils.fatal_threshold_algorithm_config(method="gte", threshold=4000, suffix="ms"),
    ],
    "query_template": {"bk_biz_id": GLOBAL_BIZ_ID, "name": APMQueryTemplateName.RPC_CALLER_AVG_TIME.value},
    "context": _get_common_context(),
}

RPC_CALLER_P99_STRATEGY_TEMPLATE: dict[str, Any] = {
    "code": RPCStrategyTemplateCode.RPC_CALLER_P99.value,
    "name": RPCStrategyTemplateCode.RPC_CALLER_P99.label,
    "category": constants.StrategyTemplateCategory.RPC_CALLER.value,
    "monitor_type": constants.StrategyTemplateMonitorType.P99.value,
    "detect": utils.detect_config(5, 5, 3),
    "algorithms": [
        utils.warning_threshold_algorithm_config(method="gte", threshold=3000, suffix="ms"),
        utils.fatal_threshold_algorithm_config(method="gte", threshold=5000, suffix="ms"),
    ],
    "query_template": {"bk_biz_id": GLOBAL_BIZ_ID, "name": APMQueryTemplateName.RPC_CALLER_P99.value},
    "context": _get_common_context(),
}

RPC_CALLER_ERROR_CODE_STRATEGY_TEMPLATE: dict[str, Any] = {
    "code": RPCStrategyTemplateCode.RPC_CALLER_ERROR_CODE.value,
    "name": RPCStrategyTemplateCode.RPC_CALLER_ERROR_CODE.label,
    "category": constants.StrategyTemplateCategory.RPC_CALLER.value,
    "monitor_type": constants.StrategyTemplateMonitorType.DEFAULT.value,
    "detect": utils.detect_config(5, 5, 3),
    "algorithms": [
        utils.warning_threshold_algorithm_config(method="gte", threshold=10),
        utils.fatal_threshold_algorithm_config(method="gte", threshold=50),
    ],
    "query_template": {"bk_biz_id": GLOBAL_BIZ_ID, "name": APMQueryTemplateName.RPC_CALLER_ERROR_CODE.value},
    "context": _get_common_context(extra_group_by=[RPCMetricTag.CODE.value]),
}

RPC_ERROR_METRIC_PANIC_STRATEGY_TEMPLATE: dict[str, Any] = {
    "code": RPCStrategyTemplateCode.RPC_ERROR_METRIC_PANIC.value,
    "name": RPCStrategyTemplateCode.RPC_ERROR_METRIC_PANIC.label,
    "category": constants.StrategyTemplateCategory.RPC_METRIC.value,
    "monitor_type": constants.StrategyTemplateMonitorType.DEFAULT.value,
    "detect": utils.detect_config(5, 1, 1),
    "algorithms": [
        utils.fatal_threshold_algorithm_config(method="gte", threshold=1),
    ],
    "query_template": {"bk_biz_id": GLOBAL_BIZ_ID, "name": APMQueryTemplateName.CUSTOM_METRIC_PANIC.value},
    "context": {},
}

RPC_ERROR_LOG_PANIC_STRATEGY_TEMPLATE: dict[str, Any] = {
    "code": RPCStrategyTemplateCode.RPC_ERROR_LOG_PANIC.value,
    "name": RPCStrategyTemplateCode.RPC_ERROR_LOG_PANIC.label,
    "category": constants.StrategyTemplateCategory.RPC_LOG.value,
    "monitor_type": constants.StrategyTemplateMonitorType.DEFAULT.value,
    "detect": utils.detect_config(5, 1, 1),
    "algorithms": [
        utils.fatal_threshold_algorithm_config(method="gte", threshold=1),
    ],
    "query_template": {"bk_biz_id": GLOBAL_BIZ_ID, "name": LocalQueryTemplateName.RPC_PANIC_LOG.value},
    "context": {},
}

RPC_METRIC_GO_GOROUTINE_FLUCTUATION_STRATEGY_TEMPLATE: dict[str, Any] = {
    "code": RPCStrategyTemplateCode.RPC_METRIC_GO_GOROUTINE_FLUCTUATION.value,
    "name": RPCStrategyTemplateCode.RPC_METRIC_GO_GOROUTINE_FLUCTUATION.label,
    "category": constants.StrategyTemplateCategory.RPC_METRIC.value,
    "monitor_type": constants.StrategyTemplateMonitorType.DEFAULT.value,
    "detect": utils.detect_config(5, 3, 3),
    "algorithms": [
        utils.warning_threshold_algorithm_config(method="gt", threshold=1500),
        utils.fatal_threshold_algorithm_config(method="gt", threshold=1000),
        utils.fatal_year_round_and_ring_ratio_algorithm_config(
            method=constants.AlgorithmYearRoundAndRingRatioMethod.FIVE_MINUTE_RING_RATIO, ceil=50, floor=100
        ),
    ],
    "query_template": {"bk_biz_id": GLOBAL_BIZ_ID, "name": APMQueryTemplateName.CUSTOM_METRIC_GO_GOROUTINE.value},
    "context": {
        "GROUP_BY": [
            CommonMetricTag.APP_NAME.value,
            RPCMetricTag.SERVICE_NAME.value,
            RPCMetricTag.ENV_NAME.value,
            RPCMetricTag.NAMESPACE.value,
            RPCMetricTag.INSTANCE.value,
        ]
    },
}


class RPCStrategyTemplateSet(base.StrategyTemplateSet):
    SYSTEM: constants.StrategyTemplateSystem = constants.StrategyTemplateSystem.RPC

    ENABLED_CODES: list[str] = [
        RPCStrategyTemplateCode.RPC_CALLEE_SUCCESS_RATE.value,
        RPCStrategyTemplateCode.RPC_CALLEE_ERROR_CODE.value,
        RPCStrategyTemplateCode.RPC_CALLEE_P99.value,
        RPCStrategyTemplateCode.RPC_CALLEE_REQ_FLUCTUATION.value,
        RPCStrategyTemplateCode.RPC_CALLER_SUCCESS_RATE.value,
        RPCStrategyTemplateCode.RPC_CALLER_P99.value,
        RPCStrategyTemplateCode.RPC_ERROR_LOG_PANIC.value,
        RPCStrategyTemplateCode.RPC_ERROR_METRIC_PANIC.value,
        RPCStrategyTemplateCode.RPC_METRIC_GO_GOROUTINE_FLUCTUATION.value,
    ]

    STRATEGY_TEMPLATES: list[dict[str, Any]] = [
        RPC_CALLEE_SUCCESS_RATE_STRATEGY_TEMPLATE,
        RPC_CALLEE_AVG_TIME_STRATEGY_TEMPLATE,
        RPC_CALLEE_P99_STRATEGY_TEMPLATE,
        RPC_CALLEE_ERROR_CODE_STRATEGY_TEMPLATE,
        RPC_CALLEE_REQ_FLUCTUATION_STRATEGY_TEMPLATE,
        RPC_CALLER_SUCCESS_RATE_STRATEGY_TEMPLATE,
        RPC_CALLER_AVG_TIME_STRATEGY_TEMPLATE,
        RPC_CALLER_P99_STRATEGY_TEMPLATE,
        RPC_CALLER_ERROR_CODE_STRATEGY_TEMPLATE,
        RPC_ERROR_LOG_PANIC_STRATEGY_TEMPLATE,
        RPC_ERROR_METRIC_PANIC_STRATEGY_TEMPLATE,
        RPC_METRIC_GO_GOROUTINE_FLUCTUATION_STRATEGY_TEMPLATE,
    ]
