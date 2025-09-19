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
from constants.apm import CachedEnum

from constants.query_template import GLOBAL_BIZ_ID
from bkmonitor.query_template.builtin.apm import APMQueryTemplateName

from django.utils.translation import gettext as _

from . import base, utils
from .. import constants


def _get_common_context() -> dict[str, Any]:
    return {"ALARM_THRESHOLD_VALUE": 10}


class RPCStrategyTemplateCode(CachedEnum):
    RPC_CALLEE_SUCCESS_RATE = "rpc_callee_success_rate"
    RPC_CALLEE_AVG_TIME = "rpc_callee_avg_time"
    RPC_CALLEE_P99 = "rpc_callee_p99"
    RPC_CALLEE_ERROR_CODE = "rpc_caller_error_code"
    RPC_CALLER_SUCCESS_RATE = "rpc_caller_success_rate"
    RPC_CALLER_AVG_TIME = "rpc_caller_avg_time"
    RPC_CALLER_P99 = "rpc_caller_p99"
    RPC_CALLER_ERROR_CODE = "rpc_caller_error_code"

    @cached_property
    def label(self) -> str:
        return str(
            {
                self.RPC_CALLEE_SUCCESS_RATE: _("被调成功率告警"),
                self.RPC_CALLEE_AVG_TIME: _("被调平均耗时告警"),
                self.RPC_CALLEE_P99: _("被调 P99 耗时告警"),
                self.RPC_CALLEE_ERROR_CODE: _("被调错误码告警"),
                self.RPC_CALLER_SUCCESS_RATE: _("主调成功率告警"),
                self.RPC_CALLER_AVG_TIME: _("主调平均耗时告警"),
                self.RPC_CALLER_P99: _("主调 P99 耗时告警"),
                self.RPC_CALLER_ERROR_CODE: _("主调错误码告警"),
            }.get(self, self.value)
        )


RPC_CALLEE_SUCCESS_RATE_STRATEGY_TEMPLATE: dict[str, Any] = {
    "code": RPCStrategyTemplateCode.RPC_CALLEE_SUCCESS_RATE.value,
    "name": RPCStrategyTemplateCode.RPC_CALLEE_SUCCESS_RATE.label,
    "category": constants.StrategyTemplateCategory.RPC_CALLEE.value,
    "monitor_type": constants.StrategyTemplateMonitorType.SUCCESS_RATE.value,
    "detect": utils.detect_config(5, 5, 3),
    "algorithms": [
        utils.warning_threshold_algorithm_config(method="lte", threshold=95),
        utils.fatal_threshold_algorithm_config(method="lte", threshold=90),
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
        utils.warning_threshold_algorithm_config(method="gte", threshold=2000),
        utils.fatal_threshold_algorithm_config(method="gte", threshold=4000),
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
        utils.warning_threshold_algorithm_config(method="gte", threshold=3000),
        utils.fatal_threshold_algorithm_config(method="gte", threshold=5000),
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
    "context": _get_common_context(),
}

RPC_CALLER_SUCCESS_RATE_STRATEGY_TEMPLATE: dict[str, Any] = {
    "code": RPCStrategyTemplateCode.RPC_CALLER_SUCCESS_RATE.value,
    "name": RPCStrategyTemplateCode.RPC_CALLER_SUCCESS_RATE.label,
    "category": constants.StrategyTemplateCategory.RPC_CALLER.value,
    "monitor_type": constants.StrategyTemplateMonitorType.SUCCESS_RATE.value,
    "detect": utils.detect_config(5, 5, 3),
    "algorithms": [
        utils.warning_threshold_algorithm_config(method="lte", threshold=95),
        utils.fatal_threshold_algorithm_config(method="lte", threshold=90),
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
        utils.warning_threshold_algorithm_config(method="gte", threshold=2000),
        utils.fatal_threshold_algorithm_config(method="gte", threshold=4000),
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
        utils.warning_threshold_algorithm_config(method="gte", threshold=3000),
        utils.fatal_threshold_algorithm_config(method="gte", threshold=5000),
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
    "context": _get_common_context(),
}


class RPCStrategyTemplateSet(base.StrategyTemplateSet):
    SYSTEM: constants.StrategyTemplateSystem = constants.StrategyTemplateSystem.RPC

    ENABLED_CODES: list[str] = [
        RPCStrategyTemplateCode.RPC_CALLEE_SUCCESS_RATE.value,
        RPCStrategyTemplateCode.RPC_CALLEE_ERROR_CODE.value,
        RPCStrategyTemplateCode.RPC_CALLEE_P99.value,
        RPCStrategyTemplateCode.RPC_CALLER_SUCCESS_RATE.value,
        RPCStrategyTemplateCode.RPC_CALLER_P99.value,
    ]

    STRATEGY_TEMPLATES: list[dict[str, Any]] = [
        RPC_CALLEE_SUCCESS_RATE_STRATEGY_TEMPLATE,
        RPC_CALLEE_AVG_TIME_STRATEGY_TEMPLATE,
        RPC_CALLEE_P99_STRATEGY_TEMPLATE,
        RPC_CALLEE_ERROR_CODE_STRATEGY_TEMPLATE,
        RPC_CALLER_SUCCESS_RATE_STRATEGY_TEMPLATE,
        RPC_CALLER_AVG_TIME_STRATEGY_TEMPLATE,
        RPC_CALLER_P99_STRATEGY_TEMPLATE,
        RPC_CALLER_ERROR_CODE_STRATEGY_TEMPLATE,
    ]
