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
)
from ...provider.base import PermissionProvider

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
        """创建者授权由主 Provider 执行。"""
        self.primary().grant_creator_action(resource_type, resource_id, creator, expired_at, tenant_id)

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
