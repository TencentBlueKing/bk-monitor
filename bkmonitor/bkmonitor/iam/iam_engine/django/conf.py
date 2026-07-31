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

from bkmonitor.iam.iam_engine.core.config import (
    CompositionConfig,
    ProviderConfig,
)
from bkmonitor.iam.iam_engine.core.context import ProviderContext
from bkmonitor.iam.iam_engine.core.framework import IAMFramework
from bkmonitor.iam.iam_engine.core.utils import import_class
from bkmonitor.iam.iam_engine.django.facade import _set_framework
from bkmonitor.iam.iam_engine.schema.definitions import SystemDef
from bkmonitor.iam.iam_engine.schema.loaders import load_from_class as schema_load_from_class
from bkmonitor.iam.iam_engine.schema.registry import SchemaRegistry

logger = logging.getLogger("iam_engine.django")


# --------------------------------------------------------------------------
# CompositionPolicy 类名 → 类的映射
#
# 用户配置 composition.policy = "any_of" 时，框架查此表定位具体类。
# --------------------------------------------------------------------------

_POLICY_CLASS_MAP: dict[str, str] = {
    "single": "bkmonitor.iam.iam_engine.provider.composition.single.SinglePolicy",
    "any_of": "bkmonitor.iam.iam_engine.provider.composition.any_of.AnyOfPolicy",
    "all_of": "bkmonitor.iam.iam_engine.provider.composition.all_of.AllOfPolicy",
    "primary": "bkmonitor.iam.iam_engine.provider.composition.primary.PrimaryPolicy",
}


def _resolve_policy_class(policy_name: str) -> type:
    """根据策略名（如 "any_of"）返回 CompositionPolicy 子类。"""
    dotted = _POLICY_CLASS_MAP.get(policy_name)
    if dotted is None:
        raise ValueError(f"Unknown composition policy {policy_name!r}. Available: {sorted(_POLICY_CLASS_MAP)}")
    return import_class(dotted)


def _build_system_def(raw: dict) -> SystemDef:
    """从 settings dict 构建 SystemDef。"""
    return SystemDef(
        id=raw["id"],
        name=raw["name"],
        name_en=raw.get("name_en", ""),
        description=raw.get("description", ""),
        managers=tuple(raw.get("managers", [])),
        clients=tuple(raw.get("clients", [])),
        callback_url=raw.get("callback_url", ""),
    )


def _resolve_credentials(credentials_dotted: str, key: str) -> dict:
    """解析凭据。支持多套凭据（多 Provider 时用不同的 credentials_key）。"""
    if not credentials_dotted:
        return {}
    fn = import_class(credentials_dotted) if "." in credentials_dotted else None
    if fn is None:
        from django.utils.module_loading import import_string

        fn = import_string(credentials_dotted)
    return fn(key=key)


def _build_provider(provider_cfg: ProviderConfig, credentials_dotted: str, schema: SchemaRegistry):
    """从配置实例化一个 Provider。"""
    cls = import_class(provider_cfg.cls)
    options = dict(provider_cfg.options)
    credentials_key = options.pop("credentials_key", "default")
    credentials = _resolve_credentials(credentials_dotted, credentials_key)

    system_raw = options.pop("system", None)
    system = _build_system_def(system_raw) if system_raw else None

    ctx = ProviderContext(
        schema=schema,
        credentials=credentials,
        logger=logging.getLogger(f"iam_engine.provider.{cls.name}"),
        cache=None,
    )

    return cls(ctx, system=system, **options)


def _build_bypass_rules(raw_rules: tuple[str, ...]):
    """从 dotted path 列表实例化 bypass 规则。"""
    rules = []
    for dotted in raw_rules:
        rule_cls = import_class(dotted)
        rules.append(rule_cls())
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

    # 1. 构建 SchemaRegistry
    registry = SchemaRegistry()
    for key in ("ACTIONS", "RESOURCE_TYPES", "ROLES"):
        dotted = raw.get(key)
        if not dotted:
            continue
        cls = import_class(dotted) if "." in dotted else None
        if cls is None:
            from django.utils.module_loading import import_string

            cls = import_string(dotted)
        schema_load_from_class(registry, cls)
    registry.freeze()
    logger.info("schema registry frozen: %d action(s)", len(registry._actions))

    # 2. 构建 Provider 列表
    provider_configs = raw.get("PROVIDERS", [])
    credentials_dotted = raw.get("CREDENTIALS_PROVIDER", "")

    providers = []
    for cfg_dict in provider_configs:
        provider_cfg = ProviderConfig(
            cls=cfg_dict["class"],
            options=cfg_dict.get("options", {}),
        )
        provider = _build_provider(provider_cfg, credentials_dotted, registry)
        providers.append(provider)
        logger.info("provider loaded: %s", provider.name)
    if not providers:
        raise RuntimeError("IAM_FRAMEWORK.PROVIDERS must contain at least one provider")

    # 3. 构建 CompositionPolicy
    composition_raw = raw.get("COMPOSITION", {})
    composition_cfg = CompositionConfig(
        policy=composition_raw.get("policy", "single"),
        options=composition_raw.get("options", {}),
    )
    policy_cls = _resolve_policy_class(composition_cfg.policy)
    composition = policy_cls(providers, **composition_cfg.options)
    logger.info("composition policy: %s", composition_cfg.policy)

    # 4. 构建 BypassRules
    bypass_rules_raw: tuple[str, ...] = tuple(raw.get("BYPASS_RULES", []))
    bypass_rules = _build_bypass_rules(bypass_rules_raw)

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
