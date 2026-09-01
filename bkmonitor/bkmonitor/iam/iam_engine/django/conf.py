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

from ..core.config import BypassRuleConfig, FrameworkConfig, ProviderConfig, ReadConfig
from ..core.framework import IAMFramework
from ..core.utils import import_class
from ..django.facade import _set_framework
from ..provider import composition as _composition  # noqa: F401
from ..provider.base import PermissionProvider
from ..provider.composition.base import CompositionPolicy
from ..provider.composition.resolver import resolve_policy_class
from ..provider.permission_writer import PermissionWriter
from ..schema.loaders import load_from_class as schema_load_from_class
from ..schema.registry import SchemaRegistry

logger = logging.getLogger("iam_engine.django")


def _build_composition(
    providers: list[PermissionProvider],
    policy_name: str,
    options: dict,
) -> CompositionPolicy:
    """从已选择的读 Provider 构建组合策略。"""
    policy_cls = resolve_policy_class(policy_name)
    return policy_cls.from_options(providers, **options)


def _build_provider(provider_cfg: ProviderConfig, schema: SchemaRegistry) -> PermissionProvider:
    """Provider 的 options 原样透传，由 Provider 自己校验地址、凭据等细节。"""
    cls = import_class(provider_cfg.cls)
    return cls(schema, **provider_cfg.options)


def _build_bypass_rules(raw_rules: tuple[BypassRuleConfig, ...]):
    rules = []
    for rule_config in raw_rules:
        rule_cls = import_class(rule_config.cls)
        rules.append(rule_cls(**rule_config.options))
    return rules


def _select_provider_configs(config: FrameworkConfig) -> tuple[ProviderConfig, ...]:
    """从完整目录中选择当前进程实际启用的 Provider 配置。"""
    catalog = {provider.name: provider for provider in config.provider_catalog}
    if not config.enabled_providers:
        raise RuntimeError("IAM_FRAMEWORK.ENABLED_PROVIDERS must contain at least one provider name")
    missing = [name for name in config.enabled_providers if name not in catalog]
    if missing:
        raise RuntimeError(
            "IAM_FRAMEWORK.ENABLED_PROVIDERS references providers not present in IAM_FRAMEWORK.PROVIDER_CATALOG: "
            f"{missing}; available: {sorted(catalog)}"
        )
    return tuple(catalog[name] for name in config.enabled_providers)


def _build_enabled_providers(config: FrameworkConfig, schema: SchemaRegistry) -> list[PermissionProvider]:
    providers: list[PermissionProvider] = []
    for provider_cfg in _select_provider_configs(config):
        provider = _build_provider(provider_cfg, schema)
        if provider.name != provider_cfg.name:
            raise RuntimeError(
                "Provider catalog name "
                f"{provider_cfg.name!r} does not match instantiated provider.name {provider.name!r}"
            )
        providers.append(provider)
        logger.info("provider loaded: %s", provider.name)
    return providers


def _select_providers(
    providers_by_name: dict[str, PermissionProvider],
    names: tuple[str, ...],
    field_name: str,
) -> list[PermissionProvider]:
    """选择读或写路径目标，并拒绝引用未启用的 Provider。"""
    if not names:
        raise RuntimeError(f"{field_name} must contain at least one provider name")
    missing = [name for name in names if name not in providers_by_name]
    if missing:
        raise RuntimeError(
            f"{field_name} references providers not enabled by IAM_FRAMEWORK.ENABLED_PROVIDERS: {missing}; "
            f"available: {sorted(providers_by_name)}"
        )
    return [providers_by_name[name] for name in names]


def _build_read_policy(read_config: ReadConfig, providers: list[PermissionProvider]) -> CompositionPolicy:
    """将 READ 的通用字段和策略私有 OPTIONS 交给策略工厂。"""
    return _build_composition(providers, read_config.policy, read_config.options)


def load_framework() -> IAMFramework:
    """从 settings.IAM_FRAMEWORK 构建并安装 IAMFramework 单例。"""
    from django.conf import settings

    raw: dict = getattr(settings, "IAM_FRAMEWORK", {})
    if not raw:
        raise RuntimeError(
            "IAM_FRAMEWORK is not configured in Django settings. Add IAM_FRAMEWORK = {...} to your settings.py."
        )
    config = FrameworkConfig.from_dict(raw)

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

    providers = _build_enabled_providers(config, registry)
    if not providers:
        raise RuntimeError("IAM_FRAMEWORK.ENABLED_PROVIDERS must contain at least one provider")
    if len({provider.name for provider in providers}) != len(providers):
        raise RuntimeError(f"Enabled Provider names must be unique, got {[provider.name for provider in providers]}")
    providers_by_name = {provider.name: provider for provider in providers}

    read_providers = _select_providers(providers_by_name, config.read.providers, "IAM_FRAMEWORK.READ.PROVIDERS")
    read_policy = _build_read_policy(config.read, read_providers)
    logger.info("read policy: %s", config.read.policy)

    write_providers = _select_providers(providers_by_name, config.write.providers, "IAM_FRAMEWORK.WRITE.PROVIDERS")
    permission_writer = PermissionWriter(write_providers, on_failure=config.write.on_failure)
    logger.info("permission writer targets: %s", [provider.name for provider in write_providers])

    fw = IAMFramework(
        schema=registry,
        providers=providers,
        read_policy=read_policy,
        permission_writer=permission_writer,
        bypass_rules=_build_bypass_rules(config.bypass_rules),
    )
    _set_framework(fw)
    return fw
