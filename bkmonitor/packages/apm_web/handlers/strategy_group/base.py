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
import logging
from typing import Dict, List, Set, Tuple, Type

from apm_web.handlers.strategy_group.typing import StrategyKeyT, StrategyT
from apm_web.models import Application

logger = logging.getLogger(__name__)


class StrategyGroupRegistry:
    _GROUPS: Dict[str, Type["BaseStrategyGroup"]] = {}

    @classmethod
    def register(cls, invocation_cls):
        try:
            group_name: str = invocation_cls.Meta.name
        except AttributeError as e:
            raise AttributeError(f"lost attrs -> {e}")

        cls._GROUPS[group_name] = invocation_cls

    @classmethod
    def get(cls, group_name: str, bk_biz_id: int, app_name: str, **kwargs):
        if group_name not in cls._GROUPS:
            raise ValueError("{} not found".format(group_name))
        return cls._GROUPS[group_name](bk_biz_id, app_name, **kwargs)


class StrategyGroupMeta(type):
    def __new__(cls, name, bases, dct):
        parents = [b for b in bases if isinstance(b, StrategyGroupMeta)]
        if not parents:
            return super().__new__(cls, name, bases, dct)

        new_cls = super().__new__(cls, name, bases, dct)

        try:
            StrategyGroupRegistry.register(new_cls)
        except AttributeError:
            raise AttributeError("Meta class is required")

        return new_cls


class BaseStrategyGroup(metaclass=StrategyGroupMeta):
    """声明式告警策略管理框架"""

    def __init__(self, bk_biz_id: int, app_name: str, **kwargs):
        self.bk_biz_id: int = bk_biz_id
        self.app_name: str = app_name

        try:
            self.application: Application = Application.objects.get(bk_biz_id=bk_biz_id, app_name=app_name)
        except Application.DoesNotExist:
            raise ValueError(
                "Application ({bk_biz_id}-{app_name}) not found".format(bk_biz_id=bk_biz_id, app_name=app_name)
            )

    def apply(self, *args, **kwargs):
        def _format(_strategies: List[StrategyT]) -> Tuple[Set[StrategyKeyT], Dict[StrategyKeyT, StrategyT]]:
            _strategies_map: Dict[StrategyKeyT, StrategyT] = {
                self._get_key(_strategy): _strategy for _strategy in _strategies
            }
            return set(_strategies_map.keys()), _strategies_map

        # 拉取同个管理范围，本地、远端的数据
        local_keys, local_strategies_map = _format(self._list_local())
        remote_keys, remote_strategies_map = _format(self._list_remote())
        logger.info("[apply] local -> %s, remote -> %s", len(local_keys), len(remote_keys))

        # 调谐过程，计算变更
        to_be_added_keys: Set[str] = local_keys - remote_keys
        to_be_update_keys: Set[str] = local_keys & remote_keys
        to_be_deleted_keys: Set[str] = remote_keys - local_keys
        logger.info(
            "[apply] to_be_added_keys -> %s, to_be_update_keys -> %s, to_be_deleted_keys -> %s",
            to_be_added_keys,
            to_be_update_keys,
            to_be_deleted_keys,
        )

        # 执行变更
        self._handle_delete([remote_strategies_map[key] for key in to_be_deleted_keys])
        self._handle_update(
            {key: local_strategies_map[key] for key in to_be_update_keys},
            {key: remote_strategies_map[key] for key in to_be_update_keys},
        )
        self._handle_add([local_strategies_map[key] for key in to_be_added_keys])

    @abc.abstractmethod
    def _get_key(self, strategy: StrategyT) -> StrategyKeyT:
        raise NotImplementedError

    @abc.abstractmethod
    def _list_remote(self, *args, **kwargs) -> List[StrategyT]:
        raise NotImplementedError

    @abc.abstractmethod
    def _list_local(self, *args, **kwargs) -> List[StrategyT]:
        raise NotImplementedError

    @abc.abstractmethod
    def _handle_add(self, strategies: List[StrategyT]):
        raise NotImplementedError

    @abc.abstractmethod
    def _handle_delete(self, strategies: List[StrategyT]):
        raise NotImplementedError

    @abc.abstractmethod
    def _handle_update(
        self, local_strategies_map: Dict[StrategyKeyT, StrategyT], remote_strategies_map: Dict[StrategyKeyT, StrategyT]
    ):
        raise NotImplementedError
