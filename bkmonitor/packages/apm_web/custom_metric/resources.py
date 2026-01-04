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
from apm_web.custom_metric.utils import (
    remove_scope_prefix,
    ScopeNamePrefixMixin,
    ScopeQueryFilterMixin,
    DefaultScopeNameMixin,
    DefaultFieldScopeMixin,
)
from monitor_web.custom_report.constants import DEFAULT_FIELD_SCOPE
from monitor_web.custom_report.handlers.metric.query import ScopeQueryMetricResponseDTO
from monitor_web.custom_report.resources.metric import (
    GetCustomTsFields,
    ModifyCustomTsFields,
    CustomTsGroupingRuleList,
    CreateOrUpdateGroupingRule,
    PreviewGroupingRule,
    DeleteGroupingRule,
    ImportCustomTimeSeriesFields,
    ExportCustomTimeSeriesFields,
)


class ApmGetCustomTsFields(ScopeQueryFilterMixin, GetCustomTsFields):
    class RequestSerializer(BaseRequestSerializer, GetCustomTsFields.RequestSerializer):
        pass

    def get_movable(self, metric_obj: ScopeQueryMetricResponseDTO, params: dict) -> bool:
        return metric_obj.field_scope == params["scope_prefix"] + DEFAULT_FIELD_SCOPE

    def perform_request(self, params: dict[str, Any]) -> dict[str, Any]:
        result = super().perform_request(params)
        scope_prefix = params["scope_prefix"]

        result["dimensions"] = remove_scope_prefix(result.get("dimensions", []), scope_prefix)
        result["metrics"] = remove_scope_prefix(result.get("metrics", []), scope_prefix)

        return result


class ApmModifyCustomTsFields(DefaultScopeNameMixin, ModifyCustomTsFields):
    class RequestSerializer(BaseRequestSerializer, ModifyCustomTsFields.RequestSerializer):
        def to_internal_value(self, data):
            """验证数据并为 scope.name 添加服务名前缀"""
            validated_data = super().to_internal_value(data)
            scope_prefix = validated_data.get("scope_prefix")

            for field_key in ("update_fields", "delete_fields"):
                for field in validated_data.get(field_key, []):
                    if (scope := field.get("scope")) and "name" in scope:
                        scope["name"] = f"{scope_prefix}{scope['name']}"

            return validated_data


class ApmCustomTsGroupingRuleList(ScopeQueryFilterMixin, CustomTsGroupingRuleList):
    class RequestSerializer(BaseRequestSerializer, CustomTsGroupingRuleList.RequestSerializer):
        pass

    def perform_request(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        result = super().perform_request(params)
        scope_prefix = params["scope_prefix"]

        return remove_scope_prefix(result, scope_prefix, scope_key=None)


class ApmCreateOrUpdateGroupingRule(DefaultScopeNameMixin, CreateOrUpdateGroupingRule):
    class RequestSerializer(ScopeNamePrefixMixin, BaseRequestSerializer, CreateOrUpdateGroupingRule.RequestSerializer):
        pass


class ApmPreviewGroupingRule(DefaultScopeNameMixin, PreviewGroupingRule):
    class RequestSerializer(BaseRequestSerializer, PreviewGroupingRule.RequestSerializer):
        pass


class ApmDeleteGroupingRule(DeleteGroupingRule):
    class RequestSerializer(ScopeNamePrefixMixin, BaseRequestSerializer, DeleteGroupingRule.RequestSerializer):
        pass


class ApmImportCustomTimeSeriesFields(ScopeQueryFilterMixin, DefaultFieldScopeMixin, ImportCustomTimeSeriesFields):
    class RequestSerializer(BaseRequestSerializer, ImportCustomTimeSeriesFields.RequestSerializer):
        pass

    def perform_request(self, params: dict[str, Any]) -> None:
        """调用父类处理前，为 scope.name 添加前缀"""
        scope_prefix = params["scope_prefix"]

        # 为所有 scope 的 name 添加前缀
        for scope in params.get("scopes", []):
            if "name" in scope:
                scope["name"] = f"{scope_prefix}{scope['name']}"

        return super().perform_request(params)


class ApmExportCustomTimeSeriesFields(ScopeQueryFilterMixin, ExportCustomTimeSeriesFields):
    class RequestSerializer(BaseRequestSerializer, ExportCustomTimeSeriesFields.RequestSerializer):
        pass

    def perform_request(self, params: dict[str, Any]) -> dict[str, Any]:
        result = super().perform_request(params)
        scope_prefix = params["scope_prefix"]

        result["scopes"] = remove_scope_prefix(result.get("scopes", []), scope_prefix, scope_key=None)

        return result
