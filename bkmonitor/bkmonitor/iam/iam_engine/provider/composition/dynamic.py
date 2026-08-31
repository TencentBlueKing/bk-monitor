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

# ---------------------------------------------------------------------------
# DynamicCompositionPolicy —— 运行时按 selector 动态委托的组合策略
#
# 设计原则：
#   * 框架层**不感知任何具体 mode 名字**（"v3"/"v4"/"union" 等业务字符串禁止
#     出现在本文件里）。selector 返回什么 key、候选池里放什么策略，全部由
#     业务侧（config/default.py + bkmonitor/iam/*）在装配时决定。
#   * 动态是能力，不是核心：selector 是**依赖注入的无参 callable**
#     （Callable[[], str]），框架不关心 selector 从哪读值（Django settings、
#     环境变量、etcd、apollo 都行）。测试时可注入 lambda: "a" 完全绕开 django。
#   * 读鉴权路径（is_allowed / batch_by_* / filter_visible_resources /
#     query_policies / has_any_permission）走当前 selector 命中的子策略；
#   * 写授权路径（grant_creator_action）与展示路径（get_apply_url /
#     get_apply_data）与 mode 无关，直接沿用基类 CompositionPolicy 的固定语义
#     （对所有已装配的 provider 扇出 / 走 primary()），不再受 selector 影响。
# ---------------------------------------------------------------------------

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ...core.types import (
    AuthRequest,
    BatchAuthResult,
    BatchByActionRequest,
    BatchByResourceRequest,
    ResourceInstance,
    Subject,
    VisibleResult,
)
from ...provider.base import PermissionProvider
from ...provider.composition.base import CompositionPolicy

if TYPE_CHECKING:
    from ...policy.expression import PolicyExpression
    from ...schema.definitions import ActionDef


class DynamicCompositionPolicy(CompositionPolicy):
    """运行时按 selector 结果动态委托到内部候选 policy 之一。

    Args:
        providers: 已装配的 provider 列表（与其它 policy 共用同一组 provider）。
        selector: 无参 callable，每次调用返回一个 key（字符串）。
        policies: 预实例化好的候选 CompositionPolicy 池，key 为业务定义的 mode 名。
        fallback_key: selector 返回未知/异常值时兜底走的 key，必须存在于 policies。
        **_options: 透传给基类的 options（当前不影响 dynamic 自身行为，
            但为了对齐 CompositionPolicy 构造签名保留 kw 兼容性）。

    Raises:
        ValueError: policies 为空，或 fallback_key 不在 policies 中。
    """

    def __init__(
        self,
        providers: list[PermissionProvider],
        selector: Callable[[], str],
        policies: dict[str, CompositionPolicy],
        fallback_key: str,
        **_options: Any,
    ) -> None:
        super().__init__(providers, **_options)
        if not policies:
            raise ValueError("DynamicCompositionPolicy requires at least one candidate policy")
        if fallback_key not in policies:
            raise ValueError(f"fallback_key={fallback_key!r} not in policies pool {sorted(policies)}")
        self._selector: Callable[[], str] = selector
        self._policies: dict[str, CompositionPolicy] = dict(policies)
        self._fallback_key: str = fallback_key

    # ------------------------------------------------------------------
    # 内部：解析当前 selector 命中的子策略
    # ------------------------------------------------------------------

    def _current(self) -> CompositionPolicy:
        """按 selector 结果解析当前生效的候选 policy。

        * selector 抛异常 → 走 fallback（兜底不让上游炸）
        * selector 返回 None / 空串 / 未注册的 key → 走 fallback
        * key 会被 lower() 规范化，避免大小写敏感（对齐业务侧
          settings 通常存原样字符串的实际情况）
        """
        try:
            raw = self._selector()
        except Exception:
            return self._policies[self._fallback_key]
        key = (raw or "").lower()
        return self._policies.get(key, self._policies[self._fallback_key])

    # ------------------------------------------------------------------
    # 读鉴权契约：全部一行委托到 _current()
    # ------------------------------------------------------------------

    def is_allowed(self, request: AuthRequest) -> bool:
        return self._current().is_allowed(request)

    def batch_by_resource(self, request: BatchByResourceRequest) -> BatchAuthResult:
        return self._current().batch_by_resource(request)

    def batch_by_action(self, request: BatchByActionRequest) -> BatchAuthResult:
        return self._current().batch_by_action(request)

    def filter_visible_resources(
        self,
        subject: Subject,
        action_id: ActionDef | str,
        candidates: tuple[ResourceInstance, ...],
    ) -> VisibleResult:
        return self._current().filter_visible_resources(subject, action_id, candidates)

    def query_policies(
        self,
        subject: Subject,
        action_id: ActionDef | str,
    ) -> list[PolicyExpression]:
        return self._current().query_policies(subject, action_id)

    def query_policies_by_actions(
        self,
        subject: Subject,
        action_ids: list[ActionDef | str],
    ) -> dict[str, list[PolicyExpression]]:
        return self._current().query_policies_by_actions(subject, action_ids)

    def has_any_permission(
        self,
        subject: Subject,
        action_id: ActionDef | str,
    ) -> bool:
        return self._current().has_any_permission(subject, action_id)

    # ------------------------------------------------------------------
    # 工厂：把"配置期规格"翻译成运行期对象
    # ------------------------------------------------------------------

    @classmethod
    def from_options(
        cls,
        providers: list[PermissionProvider],
        *,
        selector: dict[str, Any] | Callable[[], str],
        policies: dict[str, dict[str, Any]],
        fallback_key: str,
        **_options: Any,
    ) -> DynamicCompositionPolicy:
        """从配置字典构造 DynamicCompositionPolicy。

        与其它 CompositionPolicy 子类的最大区别：``selector`` 是 callable、
        ``policies`` 是嵌套的 CompositionPolicy 实例池，二者都无法直接
        JSON 序列化。本方法承担这层"配置期规格 → 运行期对象"的翻译：

        * ``selector`` 支持两种形态：
          - dict 规格（推荐）：``{"type": "django_setting", "attr": "...", "default": "..."}``
            按 :mod:`selectors` 里的注册表 / dotted path 构造 callable。
          - 已经是 callable：直接透传（给 Python API / 单测 用）。
        * ``policies`` 里每一项形如 ``{"policy": "<name>", "options": {...}}``，
          调用方通过 ``sub_policy_resolver`` 参数（隐式：走本文件同目录的
          ``_resolve_sub_policy``）解析子策略类；子策略不允许嵌套 dynamic
          （避免无穷递归和调试灾难）。

        参数：
            providers: 已装配的 provider 列表。
            selector: selector 规格 dict 或 callable。
            policies: 候选池规格，key 为业务 mode 名，value 为
                ``{"policy": "<name>", "options": {...}}``。
            fallback_key: selector 无法命中时兜底走的 key，必须存在于 policies。
            **_options: 目前透传给父类构造器（保留 kw 兼容性）。
        """
        selector_callable = cls._resolve_selector(selector)
        policies_pool = cls._build_policies_pool(providers, policies)
        return cls(
            providers,
            selector=selector_callable,
            policies=policies_pool,
            fallback_key=fallback_key,
            **_options,
        )

    @staticmethod
    def _resolve_selector(
        selector: dict[str, Any] | Callable[[], str],
    ) -> Callable[[], str]:
        """把配置里的 selector 规格翻译成无参 callable。

        * dict 走 :func:`selectors.build_selector`（type + kwargs）
        * callable 原样返回，允许 Python API / 单测直接注入 lambda
        """
        if callable(selector):
            return selector
        if isinstance(selector, dict):
            # 延迟导入避免循环依赖（selectors 本身不依赖 dynamic）
            from .selectors import build_selector

            return build_selector(selector)
        raise ValueError(
            f"DynamicCompositionPolicy selector must be a callable or a spec dict, got {type(selector).__name__}"
        )

    @staticmethod
    def _build_policies_pool(
        providers: list[PermissionProvider],
        policies_cfg: dict[str, dict[str, Any]],
    ) -> dict[str, CompositionPolicy]:
        """把候选池的"规格字典"翻译成"CompositionPolicy 实例字典"。

        延迟导入 :mod:`resolver` 里的 ``resolve_policy_class`` 完成
        "策略名 → 策略类"的映射；这样 dynamic.py 不需要枚举其它 policy
        类型，也避免 dynamic ↔ 其它 policy 的循环依赖。
        """
        if not policies_cfg:
            raise ValueError("DynamicCompositionPolicy requires non-empty 'policies'")

        # 延迟导入：resolver 只依赖同目录内的 policy 类，不引入外部依赖
        from .resolver import resolve_policy_class

        pool: dict[str, CompositionPolicy] = {}
        for key, spec in policies_cfg.items():
            if not isinstance(spec, dict):
                raise ValueError(f"dynamic policies[{key!r}] spec must be a dict, got {type(spec).__name__}")
            sub_policy_name = spec.get("policy") or ""
            sub_options = spec.get("options") or {}
            if not sub_policy_name:
                raise ValueError(f"dynamic policies[{key!r}] missing 'policy' name")
            if sub_policy_name == "dynamic":
                # 禁止嵌套：DynamicCompositionPolicy 内部再放 DynamicCompositionPolicy
                # 会导致 selector 语义纠缠、错误处理路径爆炸，性价比极低。
                raise ValueError(f"dynamic policies[{key!r}] policy='dynamic' is not allowed (no nesting)")
            sub_cls = resolve_policy_class(sub_policy_name)
            pool[key] = sub_cls.from_options(providers, **sub_options)
        return pool

    # ------------------------------------------------------------------
    # 写授权 / 展示路径：与 mode 无关，走 CompositionPolicy 基类的固定语义。
    # grant_creator_action / get_apply_url / get_apply_data 都由基类实现，
    # 不需要在这里 override —— 基类的实现直接作用于 self.providers（扇出）
    # 和 self.primary()（默认 providers[0]），与运行时 selector 完全解耦。
    # ------------------------------------------------------------------
