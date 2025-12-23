"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any, ClassVar, TypeAlias
from dataclasses import dataclass, field, asdict
from itertools import chain

from django.utils.functional import cached_property

from monitor_web.custom_report.constants import DEFAULT_FIELD_SCOPE
from monitor_web.custom_report.handlers.metric.base import VALUE_UNSET, BaseUnsetDTO
from monitor_web.custom_report.handlers.metric.query import (
    ScopeQueryConverter,
    BasicScopeRequestDTO,
    DimensionConfigRequestDTO,
    MetricQueryConverter,
    ScopeQueryResponseDTO,
    MetricCURequestDTO,
    ScopeCURequestDTO,
    MetricConfigRequestDTO,
)


@dataclass
class ModifyMetricConfig(BaseUnsetDTO):
    alias: str = field(default=VALUE_UNSET)
    unit: str = field(default=VALUE_UNSET)
    hidden: bool = field(default=VALUE_UNSET)
    aggregate_method: str = field(default=VALUE_UNSET)
    function: str = field(default=VALUE_UNSET)
    interval: int = field(default=VALUE_UNSET)
    disabled: bool = field(default=VALUE_UNSET)

    LOCAL_TO_REMOTE_MAP: ClassVar[dict[str, str]] = {
        "alias": "alias",
        "unit": "unit",
        "hidden": "hidden",
        "aggregate_method": "aggregate_method",
        "function": "function",
        "interval": "interval",
        "disabled": "disabled",
    }

    def to_dict(self) -> dict[str, Any]:
        return super()._get_remote_dict()


@dataclass
class ModifyMetric(BaseUnsetDTO):
    id: int | None
    scope_id: int
    config: ModifyMetricConfig = field(default=VALUE_UNSET)
    name: str = field(default=VALUE_UNSET)
    dimensions: list[str] = field(default=VALUE_UNSET)
    field_scope: str = field(default=DEFAULT_FIELD_SCOPE)

    LOCAL_TO_REMOTE_MAP: ClassVar[dict[str, str]] = {
        "id": "id",
        "name": "name",
        "dimensions": "dimensions",
        "field_scope": "field_scope",
    }

    def __post_init__(self):
        super().__post_init__()
        if self.id is None and not getattr(self, "name", None):
            raise ValueError("新建分组时，必须指定 name")

    def to_metric_cu_request_dto(self) -> MetricCURequestDTO:
        dto_dict = super()._get_remote_dict()
        scope = BasicScopeRequestDTO(id=self.scope_id)
        dto_dict["scope"] = scope
        if self.config is not VALUE_UNSET:
            dto_dict["config"] = MetricConfigRequestDTO(**self.config.to_dict())
        return MetricCURequestDTO(**dto_dict)


@dataclass
class ModifyDimensionConfig(BaseUnsetDTO):
    alias: str = field(default=VALUE_UNSET)
    common: bool = field(default=VALUE_UNSET)
    hidden: bool = field(default=VALUE_UNSET)

    LOCAL_TO_REMOTE_MAP: ClassVar[dict[str, str]] = {
        "alias": "alias",
        "common": "common",
        "hidden": "hidden",
    }

    def to_dict(self) -> dict[str, Any]:
        return super()._get_remote_dict()


@dataclass
class ModifyDimension(BaseUnsetDTO):
    scope_id: int
    name: str
    config: ModifyDimensionConfig = field(default=VALUE_UNSET)


ScopeID: TypeAlias = int


class FieldsModifyService:
    def __init__(self, time_series_group_id: int):
        self.time_series_group_id = time_series_group_id
        self.scope_converter = ScopeQueryConverter(time_series_group_id)
        self.metric_converter = MetricQueryConverter(time_series_group_id)
        self._create_metrics: list[ModifyMetric] = []
        self._update_metrics: list[ModifyMetric] = []
        self._update_dimensions: list[ModifyDimension] = []
        self._delete_dimensions: list[ModifyDimension] = []

    def add_metric(self, metric_obj: ModifyMetric):
        if metric_obj.id is None:
            self._create_metrics.append(metric_obj)
        else:
            self._update_metrics.append(metric_obj)

    def delete_metric(self, metric_obj: ModifyMetric):
        metric_obj.config = ModifyMetricConfig(disabled=True)
        self._update_metrics.append(metric_obj)

    def add_dimension(self, dimension_obj: ModifyDimension):
        self._update_dimensions.append(dimension_obj)

    def delete_dimension(self, dimension_obj: ModifyDimension):
        self._delete_dimensions.append(dimension_obj)

    @cached_property
    def _scope_obj_by_id(self) -> dict[ScopeID, ScopeQueryResponseDTO]:
        # 维度 -> 查出对应的 scope_id 的数据
        scope_ids: set[int] = {
            dimension_obj.scope_id for dimension_obj in chain(self._delete_dimensions, self._update_dimensions)
        }
        scopes = self.scope_converter.query_time_series_scope(scope_ids=list(scope_ids))
        return {scope_obj.id: scope_obj for scope_obj in scopes}

    def _sync_metrics(self):
        metrics: list[MetricCURequestDTO] = []
        for metric_obj in chain(self._create_metrics, self._update_metrics):
            metrics.append(metric_obj.to_metric_cu_request_dto())
        self.metric_converter.create_or_update_time_series_metric(metrics)

    def _validate_dimensions(self):
        for dimension_obj in chain(self._update_dimensions, self._delete_dimensions):
            if dimension_obj.scope_id not in self._scope_obj_by_id:
                raise ValueError(f"维度 {dimension_obj.name} 所属的 scope_id {dimension_obj.scope_id} 不存在")

    def _sync_dimensions(self):
        scope_cu_request_by_id: dict[ScopeID, ScopeCURequestDTO] = {}

        def _get_or_create_scope_cu_request_obj(_scope_id: ScopeID) -> ScopeCURequestDTO:
            _scope_cu_request_obj: ScopeCURequestDTO | None = scope_cu_request_by_id.get(_scope_id)
            if not _scope_cu_request_obj:
                _scope_obj: ScopeQueryResponseDTO = self._scope_obj_by_id[_scope_id]
                dimension_config: dict[str, DimensionConfigRequestDTO] = {}
                for _dimension_name, _dimension_config_obj in _scope_obj.dimension_config.items():
                    dimension_config[_dimension_name] = DimensionConfigRequestDTO(**asdict(_dimension_config_obj))
                _scope_cu_request_obj = ScopeCURequestDTO(id=_scope_id, dimension_config=dimension_config)
                scope_cu_request_by_id[_scope_id] = _scope_cu_request_obj
            return _scope_cu_request_obj

        for modify_obj in self._update_dimensions:
            scope_cu_request_obj = _get_or_create_scope_cu_request_obj(modify_obj.scope_id)
            update_config_dict: dict[str, Any] = modify_obj.config.to_dict()
            dimension_config_obj = scope_cu_request_obj.dimension_config.get(modify_obj.name)
            if dimension_config_obj:
                dimension_config_obj.update_from_dict(update_config_dict)
            else:
                scope_cu_request_obj.dimension_config[modify_obj.name] = DimensionConfigRequestDTO(**update_config_dict)
        for modify_obj in self._delete_dimensions:
            scope_request_obj = _get_or_create_scope_cu_request_obj(modify_obj.scope_id)
            scope_request_obj.dimension_config.pop(modify_obj.name, None)

        self.scope_converter.create_or_update_time_series_scope(list(scope_cu_request_by_id.values()))

    def apply_change(self):
        self._validate_dimensions()
        self._sync_metrics()
        self._sync_dimensions()
