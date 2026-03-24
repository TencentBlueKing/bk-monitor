"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any, TypeAlias, ClassVar, Self
from dataclasses import dataclass, field, fields

from django.utils.translation import gettext_lazy as _

from core.drf_resource import api

from monitor_web.custom_report.handlers.metric.base import VALUE_UNSET, BaseUnsetDTO
from monitor_web.custom_report.constants import ScopeCreateFrom, DEFAULT_FIELD_SCOPE, UNGROUP_SCOPE_NAME


class BaseQueryConverter:
    def __init__(self, time_series_group_id: int):
        self.time_series_group_id = time_series_group_id


@dataclass
class BaseConfigRequestDTO(BaseUnsetDTO):
    def to_request_dict(self) -> dict[str, Any]:
        config_dict: dict[str, Any] = {}
        for _field in fields(self):
            field_value = getattr(self, _field.name, None)
            if field_value is VALUE_UNSET:
                continue
            config_dict[_field.name] = field_value
        return config_dict


@dataclass
class DimensionConfigRequestDTO(BaseConfigRequestDTO):
    alias: str = field(default=VALUE_UNSET)
    common: bool = field(default=VALUE_UNSET)
    hidden: bool = field(default=VALUE_UNSET)

    def update_from_dict(self, dimension_config_dict: dict[str, Any]) -> None:
        self.alias = dimension_config_dict.get("alias", self.alias)
        self.common = dimension_config_dict.get("common", self.common)
        self.hidden = dimension_config_dict.get("hidden", self.hidden)


@dataclass
class MetricConfigRequestDTO(BaseConfigRequestDTO):
    alias: str = field(default=VALUE_UNSET)
    unit: str = field(default=VALUE_UNSET)
    hidden: bool = field(default=VALUE_UNSET)
    aggregate_method: str = field(default=VALUE_UNSET)
    function: list = field(default=VALUE_UNSET)
    interval: int = field(default=VALUE_UNSET)
    disabled: bool = field(default=VALUE_UNSET)


@dataclass
class BaseConfigResponseDTO:
    @classmethod
    def from_response_dict(cls, response_dict: dict[str, Any]) -> Self:
        config_dict: dict[str, Any] = {}
        for _field in fields(cls):
            if _field.name in response_dict:
                config_dict[_field.name] = response_dict[_field.name]
        return cls(**config_dict)


@dataclass
class DimensionConfigResponseDTO(BaseConfigResponseDTO):
    alias: str = ""
    common: bool = False
    hidden: bool = False


@dataclass
class MetricConfigResponseDTO(BaseConfigResponseDTO):
    alias: str = ""
    unit: str = ""
    hidden: bool = False
    aggregate_method: str = ""
    function: list = field(default_factory=list)
    interval: int = 0
    disabled: bool = False


@dataclass
class ScopeQueryMetricResponseDTO:
    id: int
    name: str
    field_scope: str
    dimensions: list[str]
    config: MetricConfigResponseDTO
    create_time: float | None
    update_time: float | None

    @classmethod
    def from_response_dict(cls, metric_dict: dict[str, Any]) -> "ScopeQueryMetricResponseDTO":
        return cls(
            id=metric_dict["field_id"],
            name=metric_dict["metric_name"],
            field_scope=metric_dict["field_scope"],
            dimensions=metric_dict.get("tag_list", []),
            config=MetricConfigResponseDTO.from_response_dict(metric_dict.get("field_config", {})),
            create_time=metric_dict.get("create_time"),
            update_time=metric_dict.get("last_modify_time"),
        )


DimensionName: TypeAlias = str


@dataclass
class ScopeQueryResponseDTO:
    id: int
    name: str
    dimension_config: dict[DimensionName, DimensionConfigResponseDTO]
    auto_rules: list[str]
    metric_list: list[ScopeQueryMetricResponseDTO]
    create_from: str

    @classmethod
    def from_response_dict(cls, scope_dict: dict[str, Any]) -> Self:
        return cls(
            id=scope_dict["scope_id"],
            name=scope_dict["scope_name"],
            dimension_config={
                dimension_name: DimensionConfigResponseDTO.from_response_dict(dimension_config_dict)
                for dimension_name, dimension_config_dict in scope_dict.get("dimension_config", {}).items()
            },
            auto_rules=scope_dict.get("auto_rules", []),
            metric_list=[
                ScopeQueryMetricResponseDTO.from_response_dict(metric_dict)
                for metric_dict in scope_dict.get("metric_list", [])
            ],
            create_from=scope_dict["create_from"] or ScopeCreateFrom.USER,
        )


@dataclass
class ScopeCURequestDTO(BaseUnsetDTO):
    id: int | None = None
    name: str = field(default=VALUE_UNSET)
    dimension_config: dict[DimensionName, DimensionConfigRequestDTO] = field(default=VALUE_UNSET)
    auto_rules: list[str] = field(default=VALUE_UNSET)

    LOCAL_TO_REMOTE_MAP: ClassVar[dict[str, str]] = {
        "name": "scope_name",
        "auto_rules": "auto_rules",
    }

    def __post_init__(self):
        super().__post_init__()
        if self.id is None:
            if self.name is VALUE_UNSET or not self.name:
                raise ValueError(_("新建分组时，必须指定非空的分组名称"))
        has_other_param: bool = any(
            getattr(self, attr, None) is not VALUE_UNSET for attr in ("name", "dimension_config", "auto_rules")
        )
        if not has_other_param:
            raise ValueError(_("新建或编辑分组时，必须指定除 id 之外的至少一个参数"))

    def to_request_dict(self) -> dict[str, Any]:
        scope_dict = super()._get_remote_dict()
        if self.id is not None:
            scope_dict["scope_id"] = self.id
        if self.dimension_config is not VALUE_UNSET:
            scope_dict["dimension_config"] = {
                dimension_name: dimension_config.to_request_dict()
                for dimension_name, dimension_config in self.dimension_config.items()
            }
        return scope_dict


@dataclass
class ScopeCUResponseDTO:
    id: int
    name: str
    dimension_config: dict[DimensionName, DimensionConfigResponseDTO]
    auto_rules: list[str]
    create_from: str | None

    @classmethod
    def from_response_dict(cls, scope_dict: dict[str, Any]) -> "ScopeCUResponseDTO":
        return cls(
            id=scope_dict["scope_id"],
            name=scope_dict["scope_name"],
            dimension_config={
                dimension_name: DimensionConfigResponseDTO.from_response_dict(dimension_config_dict)
                for dimension_name, dimension_config_dict in scope_dict.get("dimension_config", {}).items()
            },
            auto_rules=scope_dict.get("auto_rules", []),
            create_from=scope_dict["create_from"],
        )


class ScopeQueryConverter(BaseQueryConverter):
    @staticmethod
    def filter_disabled_metric(scope_objs: list[ScopeQueryResponseDTO]) -> list[ScopeQueryResponseDTO]:
        """[原地修改]过滤掉 disabled 为 True 的指标"""
        for scope_obj in scope_objs:
            metric_list: list[ScopeQueryMetricResponseDTO] = []
            for metric_obj in scope_obj.metric_list:
                if metric_obj.config.disabled:
                    continue
                metric_list.append(metric_obj)
            scope_obj.metric_list = metric_list
        return scope_objs

    def query_time_series_scope(
        self, scope_ids: list[int] | None = None, scope_name: str | None = None, include_metrics: bool = True
    ) -> list[ScopeQueryResponseDTO]:
        request_param: dict[str, Any] = {
            "group_id": self.time_series_group_id,
            "include_metrics": include_metrics,
        }
        if scope_ids is not None:
            request_param["scope_ids"] = scope_ids
        if scope_name:
            request_param["scope_name"] = scope_name
        scope_list = api.metadata.query_time_series_scope(**request_param)
        return [ScopeQueryResponseDTO.from_response_dict(scope_dict) for scope_dict in scope_list]

    def create_or_update_time_series_scope(self, scopes: list[ScopeCURequestDTO]) -> list[ScopeCUResponseDTO]:
        if not scopes:
            return []

        request_params: dict[str, Any] = {
            "group_id": self.time_series_group_id,
            "scopes": [scope_obj.to_request_dict() for scope_obj in scopes],
        }
        scope_list: list[dict[str, Any]] = api.metadata.create_or_update_time_series_scope(**request_params)
        return [ScopeCUResponseDTO.from_response_dict(scope_dict) for scope_dict in scope_list]

    def get_default_scope_obj(
        self, default_scope_name=UNGROUP_SCOPE_NAME, include_metrics=True
    ) -> ScopeQueryResponseDTO:
        scope_objs = self.query_time_series_scope(scope_name=default_scope_name, include_metrics=include_metrics)
        default_scope_obj: ScopeQueryResponseDTO | None = None
        for scope_obj in scope_objs:
            if scope_obj.name == default_scope_name:
                default_scope_obj = scope_obj
                break
        if not default_scope_obj:
            raise Exception(_("数据异常，默认分组不存在，请联系管理员处理"))
        return default_scope_obj


@dataclass
class BasicScopeRequestDTO(BaseUnsetDTO):
    id: int
    name: str = field(default=VALUE_UNSET)


@dataclass
class MetricCURequestDTO(BaseUnsetDTO):
    id: int | None
    scope: BasicScopeRequestDTO
    name: str = field(default=VALUE_UNSET)
    dimensions: list[str] = field(default=VALUE_UNSET)
    config: MetricConfigRequestDTO = field(default=VALUE_UNSET)
    label: str = field(default=VALUE_UNSET)
    field_scope: str = field(default=DEFAULT_FIELD_SCOPE)  # 创建时有效

    LOCAL_TO_REMOTE_MAP: ClassVar[dict[str, str]] = {
        "name": "field_name",
        "dimensions": "tag_list",
        "label": "label",
        "field_scope": "field_scope",
    }

    def __post_init__(self):
        super().__post_init__()
        if self.id is None:
            if self.name is VALUE_UNSET or not self.name:
                raise ValueError(_("新建指标时，必须指定非空的指标名称"))

    def to_request_dict(self) -> dict[str, Any]:
        metric_dict = super()._get_remote_dict()
        metric_dict["scope_id"] = self.scope.id
        metric_dict["field_scope"] = self.field_scope
        if self.id is not None:
            metric_dict["field_id"] = self.id
        if getattr(self, "config", None) is not VALUE_UNSET:
            metric_dict["field_config"] = self.config.to_request_dict()
        return metric_dict


class MetricQueryConverter(BaseQueryConverter):
    def create_or_update_time_series_metric(self, metrics: list[MetricCURequestDTO]):
        if not metrics:
            return
        metric_list = [metric_obj.to_request_dict() for metric_obj in metrics]
        api.metadata.create_or_update_time_series_metric(group_id=self.time_series_group_id, metrics=metric_list)
