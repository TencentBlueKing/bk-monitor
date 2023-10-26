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
from typing import List, Optional, Set

from django.conf import settings
from django.db.utils import IntegrityError

from bkmonitor.models import DefaultStrategyBizAccessModel

logger = logging.getLogger(__name__)

__all__ = ["DefaultAlarmStrategyLoaderBase"]


class DefaultAlarmStrategyLoaderBase(metaclass=abc.ABCMeta):
    STRATEGY_ATTR_NAME = None

    def __init__(self, bk_biz_id: int) -> None:
        self.bk_biz_id = bk_biz_id
        self.notice_group_cache = {}

    @abc.abstractmethod
    def has_default_strategy_for_v1(self) -> bool:
        """获得已经加载默认告警配置的业务配置 ."""
        raise NotImplementedError

    def get_versions_of_access(self) -> Set:
        """获得已经接入的版本 ."""
        versions = DefaultStrategyBizAccessModel.objects.filter(
            bk_biz_id=self.bk_biz_id, access_type=self.LOADER_TYPE
        ).values_list("version", flat=True)
        return set(versions)

    @abc.abstractmethod
    def check_before_set_cache(self) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def get_default_strategy(self) -> List:
        """获得默认告警策略 ."""
        raise NotImplementedError

    @abc.abstractmethod
    def load_strategies(self, strategies: List) -> None:
        """加载默认配置 ."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_notice_group(self, config_type: Optional[str] = None) -> List:
        """获得告警通知组 ."""
        raise NotImplementedError

    def run(self) -> None:
        if not settings.ENABLE_DEFAULT_STRATEGY:
            return

        # 从缓存中判断业务是否已经导入默认策略
        if self.bk_biz_id in self.CACHE:
            return
        # 缓存前置校验
        if not self.check_before_set_cache():
            return
        # 每次版本发布，每个业务只运行一次
        self.CACHE.add(self.bk_biz_id)

        # 判断第一个版本的内置策略是否已经接入
        is_access_for_v1 = self.has_default_strategy_for_v1()
        # 从接入历史中获取接入版本，可能不包含第一个版本
        versions_of_access = self.get_versions_of_access()
        if is_access_for_v1 and "v1" not in versions_of_access:
            # 添加第一个版本的接入记录
            try:
                DefaultStrategyBizAccessModel.objects.create(
                    **{
                        "create_user": "admin",
                        "bk_biz_id": self.bk_biz_id,
                        "version": "v1",
                        "access_type": self.LOADER_TYPE,
                    }
                )
            except IntegrityError:
                pass
            versions_of_access.add("v1")

        # 获得默认告警策略
        strategies_list = self.get_default_strategy()
        if not strategies_list:
            return
        # 获得版本
        versions = [item["version"] for item in strategies_list if item["version"]]
        if not versions:
            return

        # 添加默认告警策略
        for item in strategies_list:
            version = item["version"]
            module = item["module"]
            # 判断此版本的默认策略是否已经加载
            if version in versions_of_access:
                continue
            try:
                DefaultStrategyBizAccessModel.objects.get_or_create(
                    bk_biz_id=self.bk_biz_id,
                    access_type=self.LOADER_TYPE,
                    version=version,
                    defaults={"create_user": "admin"},
                )
            except IntegrityError:
                pass
            try:
                strategies = getattr(module, self.STRATEGY_ATTR_NAME)
                self.load_strategies(strategies)
            except Exception as exc_info:
                logger.error("create default %s strategy failed: %s", self.LOADER_TYPE, exc_info)
