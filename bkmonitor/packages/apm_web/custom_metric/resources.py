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
    scope_prefix_handler,
    ScopeQueryFilterMixin,
    DefaultScopeNameMixin,
    DefaultFieldScopeMixin,
)
from monitor_web.custom_report.constants import DEFAULT_FIELD_SCOPE
from monitor_web.custom_report.handlers.metric.query import (
    ScopeQueryMetricResponseDTO,
    ScopeQueryConverter,
)
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

    @scope_prefix_handler(output_field=["dimensions.scope.name", "metrics.scope.name"])
    def perform_request(self, params: dict[str, Any]) -> dict[str, Any]:
        result = super().perform_request(params)

        # 过滤内置指标及其专有维度
        if not result.get("metrics"):
            return result

        # 过滤内置指标（以 apm_ 或 bk_apm_ 开头）
        filtered_metrics = []
        for metric in result["metrics"]:
            metric_name = str(metric["name"])
            if not (metric_name.startswith("apm_") or metric_name.startswith("bk_apm_")):
                filtered_metrics.append(metric)

        result["metrics"] = filtered_metrics

        # 收集过滤后指标使用的所有维度名称
        used_dimension_names = set()
        for metric in filtered_metrics:
            if metric.get("dimensions"):
                used_dimension_names.update(metric["dimensions"])

        # 只保留被使用的维度配置
        result["dimensions"] = [d for d in result.get("dimensions", []) if d["name"] in used_dimension_names]

        return result


class ApmModifyCustomTsFields(DefaultScopeNameMixin, ModifyCustomTsFields):
    class RequestSerializer(BaseRequestSerializer, ModifyCustomTsFields.RequestSerializer):
        def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
            """验证 scope 权限"""
            fields = attrs.get("delete_fields", []) + attrs.get("update_fields", [])
            scope_ids = [field["scope"]["id"] for field in fields]

            if scope_ids:
                converter = ScopeQueryConverter(attrs["time_series_group_id"])
                scope_objs = converter.query_time_series_scope(scope_ids=scope_ids, include_metrics=False)

                scope_prefix = attrs["scope_prefix"]
                invalid_scopes = [obj.name for obj in scope_objs if not obj.name.startswith(scope_prefix)]

                if invalid_scopes:
                    raise ValueError(f"不允许操作分组: {', '.join(invalid_scopes)}")

            return attrs

    @scope_prefix_handler(input_field=["update_fields.scope.name", "delete_fields.scope.name"])
    def perform_request(self, params: dict[str, Any]) -> dict[str, Any]:
        return super().perform_request(params)


class ApmCustomTsGroupingRuleList(ScopeQueryFilterMixin, CustomTsGroupingRuleList):
    class RequestSerializer(BaseRequestSerializer, CustomTsGroupingRuleList.RequestSerializer):
        pass

    @scope_prefix_handler(output_field="name")
    def perform_request(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        return super().perform_request(params)


class ApmCreateOrUpdateGroupingRule(ScopeQueryFilterMixin, DefaultScopeNameMixin, CreateOrUpdateGroupingRule):
    class RequestSerializer(BaseRequestSerializer, CreateOrUpdateGroupingRule.RequestSerializer):
        pass

    @scope_prefix_handler(input_field="name", output_field="name")
    def perform_request(self, params: dict[str, Any]) -> dict[str, Any]:
        return super().perform_request(params)


class ApmPreviewGroupingRule(DefaultScopeNameMixin, PreviewGroupingRule):
    class RequestSerializer(BaseRequestSerializer, PreviewGroupingRule.RequestSerializer):
        pass


class ApmDeleteGroupingRule(DeleteGroupingRule):
    class RequestSerializer(BaseRequestSerializer, DeleteGroupingRule.RequestSerializer):
        pass

    @scope_prefix_handler(input_field="name")
    def perform_request(self, params: dict[str, Any]) -> dict[str, Any]:
        return super().perform_request(params)


class ApmImportCustomTimeSeriesFields(ScopeQueryFilterMixin, DefaultFieldScopeMixin, ImportCustomTimeSeriesFields):
    class RequestSerializer(BaseRequestSerializer, ImportCustomTimeSeriesFields.RequestSerializer):
        pass

    @scope_prefix_handler(input_field="scopes.name")
    def perform_request(self, params: dict[str, Any]) -> None:
        return super().perform_request(params)


class ApmExportCustomTimeSeriesFields(ScopeQueryFilterMixin, ExportCustomTimeSeriesFields):
    class RequestSerializer(BaseRequestSerializer, ExportCustomTimeSeriesFields.RequestSerializer):
        pass

    @scope_prefix_handler(output_field="scopes.name")
    def perform_request(self, params: dict[str, Any]) -> dict[str, Any]:
        return super().perform_request(params)
