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
import logging

from django.conf import settings
from django.db import transaction
from django.db.utils import IntegrityError

from bkmonitor.models import DefaultStrategyBizAccessModel
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id

logger = logging.getLogger(__name__)

__all__ = ["DefaultAlarmStrategyLoaderBase"]


class DefaultAlarmStrategyLoaderBase(metaclass=abc.ABCMeta):
    CACHE = set()
    LOADER_TYPE = "default"
    STRATEGY_ATTR_NAME: str = ""

    def __init__(self, bk_biz_id: int) -> None:
        self.bk_biz_id = bk_biz_id
        self.bk_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)
        self.notice_group_cache = {}

    @abc.abstractmethod
    def has_default_strategy_for_v1(self) -> bool:
        """获得已经加载默认告警配置的业务配置 ."""
        raise NotImplementedError

    def get_versions_of_access(self) -> set:
        """获得已经接入的版本 ."""
        versions = DefaultStrategyBizAccessModel.objects.filter(
            bk_biz_id=self.bk_biz_id, access_type=self.LOADER_TYPE
        ).values_list("version", flat=True)
        return set(versions)

    @abc.abstractmethod
    def check_before_set_cache(self) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def get_default_strategy(self) -> list:
        """获得默认告警策略 ."""
        raise NotImplementedError

    @abc.abstractmethod
    def load_strategies(self, strategies: list) -> list:
        """加载默认配置，返回实际创建的策略配置列表 ."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_notice_group(self, config_type: str | None = None) -> list:
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
        # pending_retry 标记本轮是否存在“待重试”的版本（指标未就绪而产出 0 条，或加载异常）。
        # 只要有待重试版本，就不写内存 CACHE，使同进程后续运行仍可重试。
        pending_retry = False
        for item in strategies_list:
            version = item["version"]
            module = item["module"]
            # 判断此版本的默认策略是否已经加载
            if version in versions_of_access:
                continue
            try:
                strategies = getattr(module, self.STRATEGY_ATTR_NAME)
                # 单个版本的策略创建与接入记录写入放在同一事务内：部分创建后异常时整体回滚，
                # 避免残留半套策略导致下次重试撞已存在策略而永久失败（save_strategy_v2 非幂等）。
                with transaction.atomic():
                    created_strategies = self.load_strategies(strategies)
                    # 仅在实际创建出策略后才登记接入记录：避免指标尚未就绪时产出 0 条策略却被标记为
                    # 已接入、后续因幂等跳过而永久漏建（多租户系统事件依赖的 custom 指标可能异步晚于
                    # 业务激活就绪）。本身无需创建任何策略的空版本（strategies 为空）也登记，避免反复重试。
                    if strategies and not created_strategies:
                        pending_retry = True
                    else:
                        DefaultStrategyBizAccessModel.objects.get_or_create(
                            bk_biz_id=self.bk_biz_id,
                            access_type=self.LOADER_TYPE,
                            version=version,
                            defaults={"create_user": "admin"},
                        )
            except Exception as exc_info:
                logger.error("create default %s strategy failed: %s", self.LOADER_TYPE, exc_info)
                # 加载/登记异常时不登记接入记录、不写 CACHE，下次运行整体重试
                pending_retry = True
                # 本版本 atomic 已回滚：load_strategies 内可能已创建并缓存了通知组（notice_group_cache
                # 是 loader 实例级、跨版本存活），但其 DB 行随回滚消失。若不清缓存，同一 run() 的后续版本会
                # 复用已失效的通知组 id，建出的策略 notice.user_groups 指向不存在的组（JSON 列表、非外键，
                # 不报错而静默指向空组）导致告警发不出。清空后让后续版本重新解析（命中已提交的或重建被回滚的）。
                self.notice_group_cache = {}
                continue

        # 仅当本轮所有待处理版本都已成功登记（无待重试）时，才将该业务标记为本进程已处理；
        # 否则保持未缓存状态，让指标就绪后的下一次运行能在同进程内补建缺失的版本策略。
        if not pending_retry:
            self.CACHE.add(self.bk_biz_id)
