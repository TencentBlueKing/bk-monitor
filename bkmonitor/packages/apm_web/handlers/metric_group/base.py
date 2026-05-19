"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import abc
import copy
from typing import Any
from collections.abc import Mapping

from django.db.models import Q

from apm_web.handlers.metric_group.helper import MetricHelper, PreCalculateHelper
from bkmonitor.data_source import dict_to_q, filter_dict_to_conditions


class MetricGroupRegistry:
    _GROUPS: dict[str, type["BaseMetricGroup"]] = {}

    @classmethod
    def register(cls, invocation_cls):
        try:
            group_name: str = invocation_cls.Meta.name
        except AttributeError as e:
            raise AttributeError(f"lost attrs -> {e}")

        cls._GROUPS[group_name] = invocation_cls

    @classmethod
    def get(
        cls,
        group_name: str,
        bk_biz_id: int,
        app_name: str,
        group_by: list[str] | None = None,
        filter_dict: dict[str, Any] | None = None,
        **kwargs,
    ):
        if group_name not in cls._GROUPS:
            raise ValueError(f"{group_name} not found")
        return cls._GROUPS[group_name](bk_biz_id, app_name, group_by, filter_dict, **kwargs)


class MetricGroupMeta(abc.ABCMeta):
    def __new__(cls, name, bases, dct):
        parents = [b for b in bases if isinstance(b, MetricGroupMeta)]
        if not parents:
            return super().__new__(cls, name, bases, dct)

        new_cls = super().__new__(cls, name, bases, dct)

        try:
            MetricGroupRegistry.register(new_cls)
        except AttributeError:
            raise AttributeError("Meta class is required")

        return new_cls


class BaseMetricGroup(abc.ABC, metaclass=MetricGroupMeta):
    def __init__(
        self,
        bk_biz_id: int,
        app_name: str,
        group_by: list[str] | None = None,
        filter_dict: dict[str, Any] | None = None,
        metric_helper: MetricHelper | None = None,
        pre_calculate_helper: PreCalculateHelper | None = None,
        **kwargs,
    ):
        self.group_by: list[str] = copy.deepcopy(group_by or [])
        self.filter_dict: dict[str, Any] = copy.deepcopy(filter_dict or {})
        self.metric_helper: MetricHelper = metric_helper or MetricHelper(bk_biz_id, app_name)
        self.pre_calculate_helper: PreCalculateHelper | None = pre_calculate_helper

    @abc.abstractmethod
    def handle(self, calculation_type: str, **kwargs) -> list[dict[str, Any]]:
        raise NotImplementedError

    def query_config(self, calculation_type: str, **kwargs) -> dict[str, Any]:
        raise NotImplementedError

    @staticmethod
    def _export_qs(qs, raw: bool = False) -> dict[str, Any]:
        if not raw:
            return qs.query_config

        config: dict[str, Any] = qs.config
        for query_config in config.get("query_configs", []):
            query_config["where"] = filter_dict_to_conditions(
                query_config.pop("filter_dict", {}), query_config.get("where") or []
            )
        return config

    def _filter_dict_to_q(self) -> Q:
        is_nested: bool = False
        for val in self.filter_dict.values():
            if isinstance(val, Mapping):
                is_nested = True
                break

        if not is_nested:
            return Q(**self.filter_dict)
        return dict_to_q(self.filter_dict) or Q()
