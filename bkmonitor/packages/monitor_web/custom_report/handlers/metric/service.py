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
from dataclasses import dataclass, field, fields, asdict
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
    ScopeQueryMetricResponseDTO,
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

    def to_dict(self) -> dict[str, Any]:
        return {_field.name: v for _field in fields(self) if (v := getattr(self, _field.name, None)) is not VALUE_UNSET}


@dataclass
class ModifyMetric(BaseUnsetDTO):
    id: int | None
    scope_id: int
    config: ModifyMetricConfig = field(default=VALUE_UNSET)
    name: str = field(default=VALUE_UNSET)
    dimensions: list[str] = field(default=VALUE_UNSET)

    def __post_init__(self):
        super().__post_init__()
        if self.id is None and not getattr(self, "name", None):
            raise ValueError("新建分组时，必须指定 name")

    def to_metric_cu_request_dto(self) -> MetricCURequestDTO:
        scope = BasicScopeRequestDTO(id=self.scope_id)
        dto_dict: dict[str, Any] = {"id": self.id, "scope": scope}

        if self.name is not VALUE_UNSET:
            dto_dict["name"] = self.name
        if self.config is not VALUE_UNSET or self.config:
            dto_dict["config"] = MetricConfigRequestDTO(**self.config.to_dict())
        if self.dimensions is not VALUE_UNSET:
            dto_dict["dimensions"] = self.dimensions
        return MetricCURequestDTO(**dto_dict)


@dataclass
class ModifyDimensionConfig(BaseUnsetDTO):
    alias: str = field(default=VALUE_UNSET)
    common: bool = field(default=VALUE_UNSET)
    hidden: bool = field(default=VALUE_UNSET)

    def to_dict(self) -> dict[str, Any]:
        return {_field.name: v for _field in fields(self) if (v := getattr(self, _field.name, None)) is not VALUE_UNSET}


@dataclass
class ModifyDimension(BaseUnsetDTO):
    scope_id: int
    name: str
    config: ModifyDimensionConfig = field(default=VALUE_UNSET)


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
    def _scope_objs_map(self) -> dict[int, ScopeQueryResponseDTO]:
        if self._create_metrics:
            # 创建的指标 -> 查出所有的指标 -> 校验和复用
            scopes = self.scope_converter.query_time_series_scope()
        else:
            # 维度 -> 查出对应的 scope_id 的数据
            scope_ids: set[int] = {
                dimension_obj.scope_id for dimension_obj in chain(self._delete_dimensions, self._update_dimensions)
            }
            scopes = self.scope_converter.query_time_series_scope(scope_ids=list(scope_ids))
        return {scope_obj.id: scope_obj for scope_obj in scopes}

    @cached_property
    def _metric_obj_map(self) -> dict[tuple[str, str], ScopeQueryMetricResponseDTO]:
        """指标对象映射

        key: (field_scope, metric_name)
        """
        metric_map: dict[tuple[str, str], ScopeQueryMetricResponseDTO] = {}
        for scope_obj in self._scope_objs_map.values():
            for metric_obj in scope_obj.metric_list:
                metric_map[(metric_obj.field_scope, metric_obj.name)] = metric_obj
        return metric_map

    def _merge_create_metrics(self):
        """复用已存在的禁用指标，同时校验指标名称是否重复"""

        if not self._create_metrics:
            return
        merged_create_metrics: list[ModifyMetric] = []
        for metric_obj in self._create_metrics:
            same_name_metric = self._metric_obj_map.get((DEFAULT_FIELD_SCOPE, metric_obj.name))
            if same_name_metric:
                if not same_name_metric.config.disabled:
                    raise ValueError(f"指标 {metric_obj.name} 已存在，无法创建")
                metric_obj.id = same_name_metric.id
                metric_obj.config.disabled = False
                self._update_metrics.append(metric_obj)
            else:
                merged_create_metrics.append(metric_obj)
        self._create_metrics = merged_create_metrics

    def _sync_metrics(self):
        metrics: list[MetricCURequestDTO] = []
        for metric_obj in chain(self._create_metrics, self._update_metrics):
            metrics.append(metric_obj.to_metric_cu_request_dto())
        self.metric_converter.create_or_update_time_series_metric(metrics)

    def _validate_dimensions(self):
        for dimension_obj in chain(self._update_dimensions, self._delete_dimensions):
            if dimension_obj.scope_id not in self._scope_objs_map:
                raise ValueError(f"维度 {dimension_obj.name} 所属的 scope_id {dimension_obj.scope_id} 不存在")

    def _sync_dimensions(self):
        scope_request_by_id: dict[int, ScopeCURequestDTO] = {}

        def _get_or_create_scope_request_obj(_scope_id: int) -> ScopeCURequestDTO:
            _scope_request_obj: ScopeCURequestDTO | None = scope_request_by_id.get(_scope_id)
            if not _scope_request_obj:
                _scope_obj = self._scope_objs_map[_scope_id]
                # TODO: 改代码，类型错误
                dimension_config: dict[str, DimensionConfigRequestDTO] = {}
                for _dimension_name, _dimension_config_obj in _scope_obj.dimension_config.items():
                    dimension_config[_dimension_name] = DimensionConfigRequestDTO(**asdict(_dimension_config_obj))
                _scope_request_obj = ScopeCURequestDTO(id=_scope_id, dimension_config=dimension_config)
                scope_request_by_id[_scope_id] = _scope_request_obj
            return _scope_request_obj

        for modify_obj in self._update_dimensions:
            scope_request_obj = _get_or_create_scope_request_obj(modify_obj.scope_id)
            update_config_dict: dict[str, Any] = modify_obj.config.to_dict()
            dimension_config_obj = scope_request_obj.dimension_config.get(modify_obj.name)
            if dimension_config_obj:
                dimension_config_obj.update_from_dict(update_config_dict)
            else:
                scope_request_obj.dimension_config[modify_obj.name] = DimensionConfigRequestDTO(**update_config_dict)
        for modify_obj in self._delete_dimensions:
            scope_request_obj = _get_or_create_scope_request_obj(modify_obj.scope_id)
            scope_request_obj.dimension_config.pop(modify_obj.name, None)

        self.scope_converter.create_or_update_time_series_scope(list(scope_request_by_id.values()))

    def apply_change(self):
        self._merge_create_metrics()
        self._validate_dimensions()
        self._sync_metrics()
        self._sync_dimensions()
