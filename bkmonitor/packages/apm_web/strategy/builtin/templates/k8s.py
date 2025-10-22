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

from django.db.models import Q

from bkmonitor.data_source import q_to_conditions

from bkmonitor.query_template.builtin import K8SQueryTemplateName

from constants.apm import CachedEnum, K8SMetricTag

from django.utils.translation import gettext as _

from constants.query_template import GLOBAL_BIZ_ID
from . import base
from .. import utils
from ... import constants


class K8SStrategyTemplateCode(CachedEnum):
    K8S_CPU_USAGE = "k8s_cpu_usage"
    K8S_MEMORY_USAGE = "k8s_memory_usage"
    K8S_ABNORMAL_RESTART = "k8s_abnormal_restart"
    K8S_OOM_KILLED = "k8s_oom_killed"

    @cached_property
    def label(self) -> str:
        return str(
            {
                self.K8S_CPU_USAGE: _("CPU 使用率过高告警"),
                self.K8S_MEMORY_USAGE: _("内存使用率过高告警"),
                self.K8S_ABNORMAL_RESTART: _("异常重启告警"),
                self.K8S_OOM_KILLED: _("OOM Killed 退出告警"),
            }.get(self, self.value)
        )


K8S_CPU_USAGE_STRATEGY_TEMPLATE = {
    "name": K8SStrategyTemplateCode.K8S_CPU_USAGE.label,
    "code": K8SStrategyTemplateCode.K8S_CPU_USAGE.value,
    "category": constants.StrategyTemplateCategory.DEFAULT.value,
    "monitor_type": constants.StrategyTemplateMonitorType.DEFAULT.value,
    "detect": utils.detect_config(10, 15, 15),
    "algorithms": [
        utils.warning_threshold_algorithm_config(method="gte", threshold=85, suffix="%"),
        utils.fatal_threshold_algorithm_config(method="gte", threshold=90, suffix="%"),
    ],
    "query_template": {"bk_biz_id": GLOBAL_BIZ_ID, "name": K8SQueryTemplateName.CPU_LIMIT_USAGE.value},
    "context": {"CONDITIONS": []},
}

K8S_MEMORY_USAGE_STRATEGY_TEMPLATE = {
    "name": K8SStrategyTemplateCode.K8S_MEMORY_USAGE.label,
    "code": K8SStrategyTemplateCode.K8S_MEMORY_USAGE.value,
    "category": constants.StrategyTemplateCategory.DEFAULT.value,
    "monitor_type": constants.StrategyTemplateMonitorType.DEFAULT.value,
    "detect": utils.detect_config(10, 15, 15),
    "algorithms": [
        utils.warning_threshold_algorithm_config(method="gte", threshold=85, suffix="%"),
        utils.fatal_threshold_algorithm_config(method="gte", threshold=90, suffix="%"),
    ],
    "query_template": {"bk_biz_id": GLOBAL_BIZ_ID, "name": K8SQueryTemplateName.MEMORY_LIMIT_USAGE.value},
    "context": {"CONDITIONS": []},
}

K8S_ABNORMAL_RESTART_STRATEGY_TEMPLATE = {
    "name": K8SStrategyTemplateCode.K8S_ABNORMAL_RESTART.label,
    "code": K8SStrategyTemplateCode.K8S_ABNORMAL_RESTART.value,
    "category": constants.StrategyTemplateCategory.DEFAULT.value,
    "monitor_type": constants.StrategyTemplateMonitorType.DEFAULT.value,
    "detect": utils.detect_config(5, 1, 1),
    "algorithms": [
        utils.fatal_threshold_algorithm_config(method="gte", threshold=1),
    ],
    "query_template": {"bk_biz_id": GLOBAL_BIZ_ID, "name": K8SQueryTemplateName.ABNORMAL_RESTART.value},
    "context": {
        "CONDITIONS": [],
        "GROUP_BY": [K8SMetricTag.BCS_CLUSTER_ID.value, K8SMetricTag.NAMESPACE.value, K8SMetricTag.POD_NAME.value],
    },
}

K8S_OOM_KILLED_STRATEGY_TEMPLATE = {
    "name": K8SStrategyTemplateCode.K8S_OOM_KILLED.label,
    "code": K8SStrategyTemplateCode.K8S_OOM_KILLED.value,
    "category": constants.StrategyTemplateCategory.DEFAULT.value,
    "monitor_type": constants.StrategyTemplateMonitorType.DEFAULT.value,
    "detect": utils.detect_config(5, 1, 1),
    "algorithms": [
        utils.fatal_threshold_algorithm_config(method="gte", threshold=1),
    ],
    "query_template": {"bk_biz_id": GLOBAL_BIZ_ID, "name": K8SQueryTemplateName.TERMINATE_REASON.value},
    "context": {"CONDITIONS": q_to_conditions(Q(reason="OOMKilled"))},
}


class K8SStrategyTemplateSet(base.StrategyTemplateSet):
    SYSTEM: constants.StrategyTemplateSystem = constants.StrategyTemplateSystem.K8S

    ENABLED_CODES: list[str] = [
        K8SStrategyTemplateCode.K8S_CPU_USAGE.value,
        K8SStrategyTemplateCode.K8S_MEMORY_USAGE.value,
        K8SStrategyTemplateCode.K8S_ABNORMAL_RESTART.value,
        K8SStrategyTemplateCode.K8S_OOM_KILLED.value,
    ]

    STRATEGY_TEMPLATES: list[dict[str, Any]] = [
        K8S_CPU_USAGE_STRATEGY_TEMPLATE,
        K8S_MEMORY_USAGE_STRATEGY_TEMPLATE,
        K8S_ABNORMAL_RESTART_STRATEGY_TEMPLATE,
        K8S_OOM_KILLED_STRATEGY_TEMPLATE,
    ]
