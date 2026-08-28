"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any

from ...core.exceptions import ProviderNotFound
from ...core.types import (
    ApplyURLRequest,
    AuthRequest,
    BatchAuthResult,
    BatchByActionRequest,
    BatchByResourceRequest,
    ResourceInstance,
    Subject,
    VisibleResult,
)
from ...provider.base import PermissionProvider

logger = logging.getLogger("iam_engine.composition")

# ---------------------------------------------------------------------------
# CompositionPolicy —— 多 Provider 鉴权决策组合策略基类
#
# 组合策略用**具体类**建模，不用魔法字符串："mode": "any_of" —— 拒绝。
# 四种内置策略（见同目录其它文件）：
#   * SinglePolicy    单 Provider（默认）
#   * AnyOfPolicy     任一 allow 即 allow（宽松，双写迁移期）
#   * AllOfPolicy     全部 allow 才 allow（严格，敏感操作）
#   * PrimaryPolicy   主决策 + 主故障时 fallback（v4 挂了降级到 v3）
#
# 职责边界：
#   CompositionPolicy 只关心**鉴权决策的组合**（is_allowed / batch_by_resource
#   / batch_by_action）。数据查询（query_policy）不在此层做合并——框架仅遍历收集，
#   原样返回给调用方自行处理。
# ---------------------------------------------------------------------------

if TYPE_CHECKING:
    from ...policy.expression import PolicyExpression
    from ...schema.definitions import ActionDef, ResourceTypeDef


class CompositionPolicy(ABC):
    """组合多个 Provider 的鉴权决策。

    契约：
      * providers 至少含 1 个元素
      * 鉴权能力（is_allowed / batch_by_resource / batch_by_action）由子类决定组合语义
      * 数据查询（query_policies）由基类提供默认收集实现，子类无需重写
      * 无法合并的操作（get_apply_url）默认走 primary() Provider
    """

    def __init__(self, providers: list[PermissionProvider], **options: Any) -> None:  # noqa: F811
        if not providers:
            raise ValueError("CompositionPolicy requires at least one provider")
        self.providers = providers
        self.options = options

    # ---- Provider 寻址 ----

    def primary(self) -> PermissionProvider:
        """无法合并的操作走主 Provider；默认第一个。"""
        return self.providers[0]

    def get_provider(self, name: str) -> PermissionProvider:
        """按名称获取 Provider。

        用于调用方需要直接访问特定 Provider 的能力（绕过组合策略）时使用。
        """
        for p in self.providers:
            if p.name == name:
                return p
        raise ProviderNotFound(f"Provider {name!r} not found. Available: {[p.name for p in self.providers]}")

    # ---- 执行策略 ----

    def _call_all(
        self,
        method_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> Generator[tuple[Any, bool], None, None]:
        """对所有 Provider 调用同名方法，yield (result, is_error) 元组。

        max_workers=1 时串行（按 providers 顺序）；>1 时用线程池并发。
        调用方只需迭代消费，不感知串行/并发差异。

        用法::

            for result, is_error in self._call_all("is_allowed", request):
                if is_error:
                    ...  # result 是异常实例
                else:
                    ...  # result 是方法的正常返回值
        """
        max_workers: int = int(self.options.get("max_workers", 1))
        if max_workers <= 1:
            yield from self._call_sequential(method_name, *args, **kwargs)
        else:
            yield from self._call_concurrent(method_name, max_workers, *args, **kwargs)

    def _call_sequential(self, method_name: str, *args: Any, **kwargs: Any) -> Generator[tuple[Any, bool], None, None]:
        for provider in self.providers:
            method = getattr(provider, method_name)
            try:
                yield (method(*args, **kwargs), False)
            except Exception as exc:
                yield (exc, True)

    def _call_concurrent(
        self, method_name: str, max_workers: int, *args: Any, **kwargs: Any
    ) -> Generator[tuple[Any, bool], None, None]:
        executor = ThreadPoolExecutor(max_workers=max_workers)
        try:
            futures = {}
            for provider in self.providers:
                method = getattr(provider, method_name)
                futures[executor.submit(method, *args, **kwargs)] = provider
            for future in as_completed(futures):
                try:
                    yield (future.result(), False)
                except Exception as exc:
                    yield (exc, True)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    # ---- 鉴权组合（必选，子类定义 AND/OR/Primary 语义）----

    @abstractmethod
    def is_allowed(self, request: AuthRequest) -> bool:
        """按策略组合各 Provider 的 is_allowed 结果。"""

    @abstractmethod
    def batch_by_resource(self, request: BatchByResourceRequest) -> BatchAuthResult:
        """按策略组合各 Provider 的 batch_by_resource 结果。"""

    @abstractmethod
    def batch_by_action(self, request: BatchByActionRequest) -> BatchAuthResult:
        """按策略组合各 Provider 的 batch_by_action 结果。"""

    # ---- 无法合并的操作 ----

    def get_apply_url(self, request: ApplyURLRequest) -> str:
        """申请 URL 只能由主 Provider 生成（不同平台 URL 语义不同）。"""
        return self.primary().get_apply_url(request)

    def get_apply_data(
        self,
        action_ids: list[str],
        resources: list[ResourceInstance],
        subject: Subject,
    ) -> dict | None:
        """权限申请数据由主 Provider 生成（不同平台格式不同）。"""
        return self.primary().get_apply_data(action_ids, resources, subject)

    def grant_creator_action(
        self,
        resource_type: ResourceTypeDef | str,
        resource_id: str,
        creator: str,
        expired_at: int | None = None,
        tenant_id: str = "",
    ) -> None:
        """创建者授权：迁移期必须写入所有已装配 Provider，不受读鉴权组合策略影响。

        与 is_allowed / batch_by_* 的语义解耦：
          - 读鉴权（single / any_of / all_of / primary）决定"权限判定如何组合"；
          - 写授权固定"多 Provider 全写"：只要装配了 V3 + V4，就两侧都写，
            避免创建者在切换/回滚时失去刚创建资源的权限。

        错误策略：
          - 单 Provider：直接直通，异常照抛。
          - 多 Provider：逐个写入，任一 Provider 抛异常都记录 log，
            只要"至少一侧成功"就返回；"全部失败"时上抛最后一次异常，
            让调用方（Permission.grant_creator_action 会 catch 并 log.exception）
            决定是否 raise_exception。
        """
        if len(self.providers) == 1:
            self.providers[0].grant_creator_action(resource_type, resource_id, creator, expired_at, tenant_id)
            return

        errors: list[tuple[str, BaseException]] = []
        successes: list[str] = []
        for provider in self.providers:
            try:
                provider.grant_creator_action(resource_type, resource_id, creator, expired_at, tenant_id)
                successes.append(provider.name)
            except Exception as exc:  # noqa: BLE001
                errors.append((provider.name, exc))
                logger.exception(
                    "grant_creator_action failed on provider=%s: resource=%s/%s creator=%s",
                    provider.name,
                    resource_type,
                    resource_id,
                    creator,
                )

        if not successes:
            # 全部 Provider 都失败：上抛最后一次异常，行为对齐"单 Provider 抛错"路径
            _, last_exc = errors[-1]
            raise last_exc

        if errors:
            # 部分成功、部分失败：不上抛，但显式告警——迁移期一侧写入失败需要人工补偿
            logger.warning(
                "grant_creator_action partial success: resource=%s/%s creator=%s succeeded=%s failed=%s",
                resource_type,
                resource_id,
                creator,
                successes,
                [name for name, _ in errors],
            )

    # ---- 数据查询：框架只收集，不合并 ----

    def query_policies(
        self,
        subject: Subject,
        action_id: ActionDef | str,
    ) -> list[PolicyExpression]:
        """收集所有 Provider 的 query_policy 结果（非空 AST 列表）。

        不做合并——不同平台 AST 字段/语义不同，框架不预设合并策略。
        调用方自行决定如何消费这些原始 AST。
        """
        results: list[PolicyExpression] = []
        for p in self.providers:
            expr = p.query_policy(subject, action_id)
            if expr is not None:
                results.append(expr)
        return results

    def query_policies_by_actions(
        self,
        subject: Subject,
        action_ids: list[ActionDef | str],
    ) -> dict[str, list[PolicyExpression]]:
        """批量收集：遍历 Provider 调其批量接口，聚合为 dict[str -> list[AST]]。

        优先使用 Provider 的 query_policy_by_actions（一次网络调用）。
        返回 dict 的 key 为字符串化的 action_id。
        """
        result: dict[str, list[PolicyExpression]] = {}
        for p in self.providers:
            batch = p.query_policy_by_actions(subject, action_ids)
            for aid, expr in batch.items():
                if expr is not None:
                    result.setdefault(aid, []).append(expr)
        return result

    def has_any_permission(
        self,
        subject: Subject,
        action_id: ActionDef | str,
    ) -> bool:
        """收集所有 Provider 的 has_any_permission 结果，任一为真即真。"""
        return any(p.has_any_permission(subject, action_id) for p in self.providers)

    def filter_visible_resources(
        self,
        subject: Subject,
        action_id: ActionDef | str,
        candidates: tuple[ResourceInstance, ...],
    ) -> VisibleResult:
        """按策略组合各 Provider 的 filter_visible_resources 结果。

        必须由子类实现，因为不同策略的合并语义完全不同：
          * SinglePolicy   —— 直通唯一 Provider
          * AnyOfPolicy    —— 成功侧合并（all_granted 取 OR，visible_ids 取并集）；
                              非 strict 模式下跳过异常侧，任一 Provider 命中即命中
          * AllOfPolicy    —— 严格交集（all_granted 取 AND，visible_ids 取交集）；
                              strict 模式下任一异常即上抛
          * PrimaryPolicy  —— 主决策，主故障时按 fallback 顺序尝试备

        之所以不在基类里硬编码"遍历 + OR/并集"：那是 AnyOf 的语义，
        直接放在基类会让 AllOf/Primary 也走宽松合并，违反策略契约；同时基类
        的直接遍历没有走 _call_all 的错误容忍分支，Provider 异常会直接冒泡，
        与 is_allowed / batch_by_* 的 strict_errors 语义完全不对齐。
        """
        raise NotImplementedError
