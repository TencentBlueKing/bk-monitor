"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from functools import cached_property

from typing import Any


from django.utils.translation import gettext as _

from constants.apm import CachedEnum
from constants.query_template import GLOBAL_BIZ_ID
from . import base
from .. import utils
from ... import constants, query_template


class LogStrategyTemplateCode(CachedEnum):
    LOG_NODATA = "log_nodata"

    @cached_property
    def label(self) -> str:
        return str({self.LOG_NODATA: _("日志无数据告警")}.get(self, self.value))


LOG_NODATA_STRATEGY_TEMPLATE = {
    "name": LogStrategyTemplateCode.LOG_NODATA.label,
    "code": LogStrategyTemplateCode.LOG_NODATA.value,
    "category": constants.StrategyTemplateCategory.DEFAULT.value,
    "monitor_type": constants.StrategyTemplateMonitorType.DEFAULT.value,
    "detect": utils.detect_config(5, 5, 5),
    "algorithms": [utils.fatal_threshold_algorithm_config(method="eq", threshold=0)],
    "query_template": {"bk_biz_id": GLOBAL_BIZ_ID, "name": query_template.LocalQueryTemplateName.LOG_TOTAL.value},
    "context": {},
}


class LogStrategyTemplateSet(base.StrategyTemplateSet):
    SYSTEM: constants.StrategyTemplateSystem = constants.StrategyTemplateSystem.LOG

    ENABLED_CODES: list[str] = [
        LogStrategyTemplateCode.LOG_NODATA.value,
    ]

    STRATEGY_TEMPLATES: list[dict[str, Any]] = [
        LOG_NODATA_STRATEGY_TEMPLATE,
    ]
