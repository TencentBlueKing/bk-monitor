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
#   * 创建者授权是独立写通路，由 ProviderRouter 中的 PermissionWriter 负责，
#     不属于 CompositionPolicy；
#   * 展示路径（get_apply_url / get_apply_data）跟随当前读策略的 primary Provider，
#     避免运行时读策略已经切到某后端、展示却仍固定落到 providers[0]。
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

    def primary(self) -> PermissionProvider:
        """展示能力与当前动态读策略使用同一个 primary Provider。"""
        return self._current().primary()

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
        policies: dict[str, dict[str, Any]] | None = None,
        fallback_key: str = "any_of",
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
        * ``policies`` 里每一项形如
          ``{"providers": ["..."], "policy": "<name>", "options": {...}}``；
          每个候选可声明自己的 Provider 子集，因而可动态切换 single_v3 /
          single_v4 等不同单栈策略，而不把策略与全局 providers[0] 耦合。
          调用方通过 ``sub_policy_resolver`` 参数（隐式：走本文件同目录的
          ``_resolve_sub_policy``）解析子策略类；子策略不允许嵌套 dynamic
          （避免无穷递归和调试灾难）。

        参数：
            providers: 已装配的 provider 列表。
            selector: selector 规格 dict 或 callable。
            policies: 可选候选池规格，key 为业务定义的策略名，value 为
                ``{"providers": ["..."], "policy": "<name>", "options": {...}}``。
                未提供时按当前 ``providers`` 自动生成 ``single_<name>``、
                ``any_of``、``all_of`` 和 ``primary_<name>``。
            fallback_key: selector 无法命中时兜底走的 key，必须存在于 policies。
            **_options: 目前透传给父类构造器（保留 kw 兼容性）。
        """
        selector_callable = cls._resolve_selector(selector)
        policies_cfg = cls._default_policies(providers) if policies is None else policies
        policies_pool = cls._build_policies_pool(providers, policies_cfg)
        return cls(
            providers,
            selector=selector_callable,
            policies=policies_pool,
            fallback_key=fallback_key,
            **_options,
        )

    @staticmethod
    def _default_policies(providers: list[PermissionProvider]) -> dict[str, dict[str, Any]]:
        """为未指定候选池的动态读策略生成通用规格。

        只使用 Provider ``name``，不关联任何具体权限系统；每个候选仍明确声明
        自己的 Provider 集合，因此展示主后端和读鉴权会一起随策略切换。
        """
        names = [provider.name for provider in providers]
        return {
            **{f"single_{name}": {"providers": [name], "policy": "single"} for name in names},
            "any_of": {"providers": names, "policy": "any_of"},
            "all_of": {"providers": names, "policy": "all_of"},
            **{
                f"primary_{name}": {
                    "providers": names,
                    "policy": "primary",
                    "options": {"primary_provider": name},
                }
                for name in names
            },
        }

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

        providers_by_name = {provider.name: provider for provider in providers}
        pool: dict[str, CompositionPolicy] = {}
        for key, spec in policies_cfg.items():
            if not isinstance(spec, dict):
                raise ValueError(f"dynamic policies[{key!r}] spec must be a dict, got {type(spec).__name__}")
            sub_policy_name = spec.get("policy") or ""
            sub_options = spec.get("options") or {}
            provider_names = spec.get("providers")
            if not sub_policy_name:
                raise ValueError(f"dynamic policies[{key!r}] missing 'policy' name")
            if not isinstance(provider_names, list | tuple) or not provider_names:
                raise ValueError(f"dynamic policies[{key!r}] requires non-empty 'providers'")
            if any(not isinstance(name, str) or not name for name in provider_names):
                raise ValueError(f"dynamic policies[{key!r}].providers must contain non-empty provider names")
            if len(set(provider_names)) != len(provider_names):
                raise ValueError(f"dynamic policies[{key!r}].providers must not contain duplicates")
            missing = [name for name in provider_names if name not in providers_by_name]
            if missing:
                raise ValueError(
                    f"dynamic policies[{key!r}] references providers not available to dynamic policy: {missing}; "
                    f"available: {sorted(providers_by_name)}"
                )
            if not isinstance(sub_options, dict):
                raise ValueError(f"dynamic policies[{key!r}].options must be a dict")
            if sub_policy_name == "dynamic":
                # 禁止嵌套：DynamicCompositionPolicy 内部再放 DynamicCompositionPolicy
                # 会导致 selector 语义纠缠、错误处理路径爆炸，性价比极低。
                raise ValueError(f"dynamic policies[{key!r}] policy='dynamic' is not allowed (no nesting)")
            sub_cls = resolve_policy_class(sub_policy_name)
            sub_providers = [providers_by_name[name] for name in provider_names]
            pool[key] = sub_cls.from_options(sub_providers, **sub_options)
        return pool

    # 展示接口由 CompositionPolicy 基类实现；基类会调用上面的 primary()，因此
    # get_apply_url / get_apply_data 会随每次 selector 求值而跟随当前读策略。
