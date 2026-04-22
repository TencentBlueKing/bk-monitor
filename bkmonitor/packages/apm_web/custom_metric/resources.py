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

from apm_web.custom_metric.serializers import BaseRequestSerializer
from monitor_web.custom_report.resources.metric import (
    GetCustomTsFields,
    ModifyCustomTsFields,
    CustomTsGroupingRuleList,
    CreateOrUpdateGroupingRule,
    PreviewGroupingRule,
    DeleteGroupingRule,
    ImportCustomTimeSeriesFields,
    ExportCustomTimeSeriesFields,
    ValidateCustomTsMetricFieldName,
)

# 排除 APM 内置指标的条件：匹配以 apm_ 或 bk_apm_ 开头的指标名，然后取反
APM_BUILTIN_METRIC_EXCLUDE_CONDITION = {
    "key": "name",
    "values": ["apm_", "bk_apm_"],
    "search_type": "startswith",
    "negate": True,
}


class ApmGetCustomTsFields(GetCustomTsFields):
    class RequestSerializer(BaseRequestSerializer, GetCustomTsFields.RequestSerializer):
        pass

    def get_extra_mandatory_conditions(self, params: dict) -> list[dict]:
        """APM 场景：通过 mandatory_conditions 排除内置指标"""
        return [APM_BUILTIN_METRIC_EXCLUDE_CONDITION]


class ApmModifyCustomTsFields(ModifyCustomTsFields):
    class RequestSerializer(BaseRequestSerializer, ModifyCustomTsFields.RequestSerializer):
        pass

    def perform_request(self, params: dict[str, Any]) -> dict[str, Any]:
        return super().perform_request(params)


class ApmCustomTsGroupingRuleList(CustomTsGroupingRuleList):
    class RequestSerializer(BaseRequestSerializer, CustomTsGroupingRuleList.RequestSerializer):
        pass

    def get_extra_mandatory_conditions(self, params: dict) -> list[dict]:
        """APM 场景：排除内置指标后重新计算 metric_count"""
        return [APM_BUILTIN_METRIC_EXCLUDE_CONDITION]


class ApmCreateOrUpdateGroupingRule(CreateOrUpdateGroupingRule):
    class RequestSerializer(BaseRequestSerializer, CreateOrUpdateGroupingRule.RequestSerializer):
        pass

    def perform_request(self, params: dict[str, Any]) -> None:
        return super().perform_request(params)


class ApmPreviewGroupingRule(PreviewGroupingRule):
    class RequestSerializer(BaseRequestSerializer, PreviewGroupingRule.RequestSerializer):
        pass


class ApmDeleteGroupingRule(DeleteGroupingRule):
    class RequestSerializer(BaseRequestSerializer, DeleteGroupingRule.RequestSerializer):
        pass

    def perform_request(self, params: dict[str, Any]) -> dict[str, Any]:
        return super().perform_request(params)


class ApmImportCustomTimeSeriesFields(ImportCustomTimeSeriesFields):
    class RequestSerializer(BaseRequestSerializer, ImportCustomTimeSeriesFields.RequestSerializer):
        pass

    def perform_request(self, params: dict[str, Any]) -> None:
        return super().perform_request(params)


class ApmExportCustomTimeSeriesFields(ExportCustomTimeSeriesFields):
    class RequestSerializer(BaseRequestSerializer, ExportCustomTimeSeriesFields.RequestSerializer):
        pass

    def perform_request(self, params: dict[str, Any]) -> dict[str, Any]:
        return super().perform_request(params)


class ApmValidateCustomTsMetricFieldName(ValidateCustomTsMetricFieldName):
    class RequestSerializer(BaseRequestSerializer, ValidateCustomTsMetricFieldName.RequestSerializer):
        pass
