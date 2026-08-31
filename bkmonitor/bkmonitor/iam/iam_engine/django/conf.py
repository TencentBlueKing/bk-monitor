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

from ..core.config import BypassRuleConfig, FrameworkConfig
from ..core.framework import IAMFramework
from ..core.utils import import_class
from ..django.facade import _set_framework
from ..provider.composition.base import CompositionPolicy
from ..provider.composition.resolver import resolve_policy_class
from ..schema.loaders import load_from_class as schema_load_from_class
from ..schema.registry import SchemaRegistry

# 触发 composition 包的 __init__，把 DynamicCompositionPolicy 注入 resolver 注册表。
# 单独 import 一次即可，后续 resolve_policy_class("dynamic") 就能命中。
from ..provider import composition as _composition  # noqa: F401

logger = logging.getLogger("iam_engine.django")


def _build_composition(
    providers: list,
    policy_name: str,
    options: dict,
) -> CompositionPolicy:
    """从配置构建 CompositionPolicy。

    所有 policy 走**完全相同**的分派路径：``policy_cls.from_options(providers, **options)``。

    * 简单 policy（single / any_of / all_of / primary）继承 CompositionPolicy 的
      默认 from_options（等价于 ``cls(providers, **options)``），零成本对齐。
    * 复杂 policy（dynamic）覆盖 from_options，把配置里的
      ``selector`` 规格翻译成 callable、把嵌套 ``policies`` 规格翻译成实例池，
      集成层无需感知这些差异。
    * 业务侧可以把 policy_name 写成 dotted path 接入自定义 CompositionPolicy 子类。
    """
    policy_cls = resolve_policy_class(policy_name)
    return policy_cls.from_options(providers, **options)


def _build_provider(provider_cfg, schema: SchemaRegistry):
    """从配置实例化一个 Provider。

    框架层不解析 options 内部结构（含 credentials、system 等），
    直接原封不动透传给 Provider，由 Provider 自己校验和消费。
    """
    cls = import_class(provider_cfg.cls)
    return cls(schema, **provider_cfg.options)


def _build_bypass_rules(raw_rules: tuple[BypassRuleConfig, ...]):
    """从配置实例化 bypass 规则。"""
    rules = []
    for rule_config in raw_rules:
        rule_cls = import_class(rule_config.cls)
        rules.append(rule_cls(**rule_config.options))
    return rules


def load_framework() -> IAMFramework:
    """从 settings.IAM_FRAMEWORK 构建 IAMFramework 并存入单例。

    调用方：IamEngineConfig.ready() 或测试代码直接调用。

    Returns:
        已装配的 IAMFramework 实例
    """
    from django.conf import settings

    raw: dict = getattr(settings, "IAM_FRAMEWORK", {})
    if not raw:
        raise RuntimeError(
            "IAM_FRAMEWORK is not configured in Django settings. Add IAM_FRAMEWORK = {...} to your settings.py."
        )

    config = FrameworkConfig.from_dict(raw)

    # 1. 构建 SchemaRegistry
    registry = SchemaRegistry()
    for dotted in (config.actions_module, config.resource_types_module, config.roles_module):
        if not dotted:
            continue
        cls = import_class(dotted) if "." in dotted else None
        if cls is None:
            from django.utils.module_loading import import_string

            cls = import_string(dotted)
        schema_load_from_class(registry, cls)
    registry.freeze()
    logger.info("schema registry frozen: %d action(s)", len(registry.all_actions()))

    # 2. 构建 Provider 列表
    providers = []
    for provider_cfg in config.providers:
        provider = _build_provider(provider_cfg, registry)
        providers.append(provider)
        logger.info("provider loaded: %s", provider.name)
    if not providers:
        raise RuntimeError("IAM_FRAMEWORK.PROVIDERS must contain at least one provider")

    # 3. 构建 CompositionPolicy
    composition = _build_composition(providers, config.composition.policy, dict(config.composition.options))
    logger.info("composition policy: %s", config.composition.policy)

    # 4. 构建 BypassRules
    bypass_rules = _build_bypass_rules(config.bypass_rules)

    # 5. 装配 IAMFramework
    fw = IAMFramework(
        schema=registry,
        providers=providers,
        composition=composition,
        bypass_rules=bypass_rules,
    )

    # 6. 存入模块级单例
    _set_framework(fw)
    return fw
