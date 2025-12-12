"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any, TypeAlias
from dataclasses import dataclass, field, fields, asdict

from django.utils.translation import gettext_lazy as _

from core.drf_resource import api

from monitor_web.custom_report.handlers.metric.base import VALUE_UNSET, BaseUnsetDTO


@dataclass
class DimensionConfigDTO:
    alias: str
    common: bool
    hidden: bool

    @classmethod
    def from_dict(cls, dimension_config_dict: dict[str, Any]) -> "DimensionConfigDTO":
        return cls(
            alias=dimension_config_dict.get("alias", ""),
            common=dimension_config_dict.get("common", False),
            hidden=dimension_config_dict.get("hidden", False),
        )

    def update_from_dict(self, dimension_config_dict: dict[str, Any]) -> None:
        self.alias = dimension_config_dict.get("alias", self.alias)
        self.common = dimension_config_dict.get("common", self.common)
        self.hidden = dimension_config_dict.get("hidden", self.hidden)


@dataclass
class MetricConfigDTO:
    alias: str
    unit: str
    hidden: bool
    aggregate_method: str
    function: str
    interval: int
    disabled: bool

    @classmethod
    def from_dict(cls, metric_config_dict: dict[str, Any]) -> "MetricConfigDTO":
        return cls(
            alias=metric_config_dict.get("alias", ""),
            unit=metric_config_dict.get("unit", ""),
            hidden=metric_config_dict.get("hidden", False),
            aggregate_method=metric_config_dict.get("aggregate_method", ""),
            function=metric_config_dict.get("function", ""),
            interval=metric_config_dict.get("interval", 0),
            disabled=metric_config_dict.get("disabled", False),
        )


@dataclass
class ScopeQueryMetricDTO:
    id: int
    name: str
    field_scope: str
    dimensions: list[str]
    config: MetricConfigDTO
    create_time: float | None
    update_time: float | None

    @classmethod
    def from_dict(cls, metric_dict: dict[str, Any]) -> "ScopeQueryMetricDTO":
        return cls(
            id=metric_dict["field_id"],
            name=metric_dict["metric_name"],
            field_scope=metric_dict["field_scope"],
            dimensions=metric_dict.get("tag_list", []),
            config=MetricConfigDTO.from_dict(metric_dict.get("field_config", {})),
            create_time=metric_dict.get("create_time"),
            update_time=metric_dict.get("last_modify_time"),
        )


DimensionName: TypeAlias = str


@dataclass
class ScopeQueryResponseDTO:
    id: int
    name: str
    dimension_config: dict[DimensionName, DimensionConfigDTO]
    auto_rules: list[str]
    metric_list: list[ScopeQueryMetricDTO]
    create_from: str | None

    @classmethod
    def from_dict(cls, scope_dict: dict[str, Any]) -> "ScopeQueryResponseDTO":
        return cls(
            id=scope_dict["scope_id"],
            name=scope_dict["scope_name"],
            dimension_config={
                dimension_name: DimensionConfigDTO.from_dict(dimension_config_dict)
                for dimension_name, dimension_config_dict in scope_dict.get("dimension_config", {}).items()
            },
            auto_rules=scope_dict.get("auto_rules", []),
            metric_list=[
                ScopeQueryMetricDTO.from_dict(metric_dict) for metric_dict in scope_dict.get("metric_list", [])
            ],
            create_from=scope_dict["create_from"],
        )


@dataclass
class ScopeCURequestDTO(BaseUnsetDTO):
    id: int | None = None
    name: str = field(default=VALUE_UNSET)
    dimension_config: dict[DimensionName, DimensionConfigDTO] = field(default=VALUE_UNSET)
    auto_rules: list[str] = field(default=VALUE_UNSET)

    def to_request_dict(self) -> dict[str, Any]:
        scope_dict: dict[str, Any] = {}
        if self.id is not None:
            scope_dict["scope_id"] = self.id
        if self.name is not VALUE_UNSET:
            scope_dict["scope_name"] = self.name
        if self.dimension_config is not VALUE_UNSET:
            scope_dict["dimension_config"] = {
                dimension_name: asdict(dimension_config)
                for dimension_name, dimension_config in self.dimension_config.items()
            }
        if self.auto_rules is not VALUE_UNSET:
            scope_dict["auto_rules"] = self.auto_rules
        return scope_dict

    def __post_init__(self):
        super().__post_init__()
        if self.id is None:
            if self.name is VALUE_UNSET or not self.name:
                raise ValueError(_("新建分组时，必须指定非空的分组名称"))
        has_other_param: bool = any(
            getattr(self, attr, None) is not VALUE_UNSET for attr in ("name", "dimension_config", "auto_rules")
        )
        if not has_other_param:
            raise ValueError(_("新建分组时，必须指定除 id 之外的至少一个参数"))


@dataclass
class ScopeCUResponseDTO:
    id: int
    name: str
    dimension_config: dict[DimensionName, DimensionConfigDTO]
    auto_rules: list[str]
    create_from: str | None

    @classmethod
    def from_dict(cls, scope_dict: dict[str, Any]) -> "ScopeCUResponseDTO":
        return cls(
            id=scope_dict["scope_id"],
            name=scope_dict["scope_name"],
            dimension_config={
                dimension_name: DimensionConfigDTO.from_dict(dimension_config_dict)
                for dimension_name, dimension_config_dict in scope_dict.get("dimension_config", {}).items()
            },
            auto_rules=scope_dict.get("auto_rules", []),
            create_from=scope_dict["create_from"],
        )


class BaseQueryConverter:
    def __init__(self, time_series_group_id: int):
        self.time_series_group_id = time_series_group_id


class ScopeQueryConverter(BaseQueryConverter):
    @staticmethod
    def filter_disabled_metric(scope_objs: list[ScopeQueryResponseDTO]) -> list[ScopeQueryResponseDTO]:
        """[原地修改]过滤掉 disabled 为 True 的指标"""
        for scope_obj in scope_objs:
            metric_list: list[ScopeQueryMetricDTO] = []
            for metric_obj in scope_obj.metric_list:
                if metric_obj.config.disabled:
                    continue
                metric_list.append(metric_obj)
            scope_obj.metric_list = metric_list
        return scope_objs

    def query_time_series_scope(
        self, scope_id: int | None = None, scope_ids: list[int] = None, scope_name: str = None
    ) -> list[ScopeQueryResponseDTO]:
        request_param: dict[str, Any] = {"group_id": self.time_series_group_id}
        if scope_id is not None:
            request_param["scope_id"] = scope_id
        if scope_ids is not None:
            request_param["scope_ids"] = scope_ids
        if scope_name is not None:
            request_param["scope_name"] = scope_name
        scope_list = api.metadata.query_time_series_scope(**request_param)
        return [ScopeQueryResponseDTO.from_dict(scope_dict) for scope_dict in scope_list]

    def create_or_update_time_series_scope(self, scopes: list[ScopeCURequestDTO]) -> list[ScopeCUResponseDTO]:
        if not scopes:
            return []

        request_params: dict[str, Any] = {
            "group_id": self.time_series_group_id,
            "scopes": [scope_obj.to_request_dict() for scope_obj in scopes],
        }
        scope_list: list[dict[str, Any]] = api.metadata.create_or_update_time_series_scope(**request_params)
        return [ScopeCUResponseDTO.from_dict(scope_dict) for scope_dict in scope_list]


@dataclass
class BasicScopeDTO(BaseUnsetDTO):
    id: int = field(default=VALUE_UNSET)
    name: str = field(default=VALUE_UNSET)


@dataclass
class MetricCURequestDTO(BaseUnsetDTO):
    id: int | None
    name: str = field(default=VALUE_UNSET)
    dimensions: list[str] = field(default=VALUE_UNSET)
    config: MetricConfigDTO = field(default=VALUE_UNSET)
    label: str = field(default=VALUE_UNSET)
    scope: BasicScopeDTO = field(default=VALUE_UNSET)

    def __post_init__(self):
        super().__post_init__()
        if self.id is None:
            if self.name is VALUE_UNSET or not self.name:
                raise ValueError(_("新建指标时，必须指定非空的指标名称"))
        has_other_param: bool = any(
            getattr(self, _field.name, None) is not VALUE_UNSET for _field in fields(self) if _field.name != "id"
        )
        if not has_other_param:
            raise ValueError(_("新建指标时，必须指定除 id 之外的至少一个参数"))

    def to_request_dict(self) -> dict[str, Any]:
        metric_dict: dict[str, Any] = {"field_id": self.id}
        if self.name is not VALUE_UNSET:
            metric_dict["field_name"] = self.name
        if self.dimensions is not VALUE_UNSET:
            metric_dict["tag_list"] = self.dimensions
        if self.config is not VALUE_UNSET:
            metric_dict["field_config"] = asdict(self.config)
        if self.label is not VALUE_UNSET:
            metric_dict["label"] = self.label
        if self.scope is not VALUE_UNSET:
            if self.scope.id is not VALUE_UNSET:
                metric_dict["scope_id"] = self.scope.id
            if self.scope.name is not VALUE_UNSET:
                metric_dict["scope_name"] = self.scope.name
        return metric_dict


class MetricQueryConverter(BaseQueryConverter):
    def create_or_update_time_series_metric(self, metrics: list[MetricCURequestDTO]):
        if not metrics:
            return
        api.metadata.create_or_update_time_series_metric(
            group_id=self.time_series_group_id, metrics=[metric_obj.to_request_dict() for metric_obj in metrics]
        )
