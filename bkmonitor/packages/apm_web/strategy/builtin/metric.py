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


class MetricStrategyTemplateCode(CachedEnum):
    METRIC_RPC_PANIC = "metric_rpc_panic"

    @cached_property
    def label(self) -> str:
        return str({self.METRIC_RPC_PANIC: _("[RPC 框架] Panic 告警")}.get(self, self.value))


METRIC_RPC_PANIC_STRATEGY_TEMPLATE: dict[str, Any] = {
    "code": MetricStrategyTemplateCode.METRIC_RPC_PANIC.value,
    "name": MetricStrategyTemplateCode.METRIC_RPC_PANIC.label,
    "category": constants.StrategyTemplateCategory.DEFAULT.value,
    "monitor_type": constants.StrategyTemplateMonitorType.DEFAULT.value,
    "detect": utils.detect_config(5, 1, 1),
    "algorithms": [
        utils.fatal_threshold_algorithm_config(method="gte", threshold=1),
    ],
    "user_group_ids": [constants.BUILTIN_USER_GROUP_ID],
    "query_template": {"bk_biz_id": GLOBAL_BIZ_ID, "name": APMQueryTemplateName.CUSTOM_METRIC_PANIC.value},
    "context": {},
}


class MetricStrategyTemplateSet(base.StrategyTemplateSet):
    SYSTEM: constants.StrategyTemplateSystem = constants.StrategyTemplateSystem.METRIC

    ENABLED_CODES: list[str] = [MetricStrategyTemplateCode.METRIC_RPC_PANIC.value]

    QUERY_TEMPLATES: list[dict[str, Any]] = [METRIC_RPC_PANIC_STRATEGY_TEMPLATE]
