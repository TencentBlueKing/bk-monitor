# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import abc
import copy
from typing import Any, Dict, List, Optional, Type

from apm_web.handlers.metric_group.helper import MetricHelper


class MetricGroupRegistry:

    _GROUPS: Dict[str, Type["BaseMetricGroup"]] = {}

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
        group_by: Optional[List[str]] = None,
        filter_dict: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        if group_name not in cls._GROUPS:
            raise ValueError("{} not found".format(group_name))
        return cls._GROUPS[group_name](bk_biz_id, app_name, group_by, filter_dict, **kwargs)


class MetricGroupMeta(type):
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


class BaseMetricGroup(metaclass=MetricGroupMeta):
    def __init__(
        self,
        bk_biz_id: int,
        app_name: str,
        group_by: Optional[List[str]] = None,
        filter_dict: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        self.group_by: List[str] = copy.deepcopy(group_by or [])
        self.filter_dict: Dict[str, Any] = filter_dict or {}
        self.metric_helper: MetricHelper = MetricHelper(bk_biz_id, app_name)

    @abc.abstractmethod
    def handle(self, calculation_type: str, **kwargs) -> List[Dict[str, Any]]:
        raise NotImplementedError
