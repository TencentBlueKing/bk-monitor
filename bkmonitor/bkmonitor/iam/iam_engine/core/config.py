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

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProviderConfig:
    """Provider 目录中的一个候选后端。"""

    name: str
    cls: str
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReadConfig:
    """读鉴权路径的后端集合、策略名及策略私有参数。"""

    providers: tuple[str, ...] = ()
    policy: str = "single"
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WriteConfig:
    """通用权限写路径配置。"""

    providers: tuple[str, ...] = ()
    on_failure: str = "log"


@dataclass(frozen=True)
class BypassRuleConfig:
    """单条鉴权豁免规则配置。"""

    cls: str
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MigrationConfig:
    """Schema 迁移配置。"""

    mode: str = "manual"
    directory: str = ""
    allow_destructive: bool = False
    auto_makemigrations: bool = False
    database: str = "default"
    table_name: str = "iam_migration_state"


@dataclass(frozen=True)
class FrameworkConfig:
    """iam_engine 在加载期解析后的强类型配置。

    ``provider_catalog`` 描述所有候选后端；``enabled_providers`` 决定当前进程
    实际装配哪些后端。READ 与 WRITE 的交叉引用在 Provider 实例构造后校验。
    """

    actions_module: str = ""
    resource_types_module: str = ""
    roles_module: str = ""
    provider_catalog: tuple[ProviderConfig, ...] = ()
    enabled_providers: tuple[str, ...] = ()
    read: ReadConfig = field(default_factory=ReadConfig)
    write: WriteConfig = field(default_factory=WriteConfig)
    migration: MigrationConfig = field(default_factory=MigrationConfig)
    bypass_rules: tuple[BypassRuleConfig, ...] = ()

    @classmethod
    def from_dict(cls, raw: dict) -> FrameworkConfig:
        """从 settings.IAM_FRAMEWORK 构建强类型配置。

        Provider 列表允许使用逗号分隔字符串（环境变量来源）或 list/tuple
        （直接 Python settings）。default.py 仅传递原始意图，语义校验在本方法
        与后续 ``load_framework`` 中完成。
        """
        if not isinstance(raw, dict):
            raise ValueError("IAM_FRAMEWORK must be a dict")

        provider_catalog = _parse_provider_catalog(raw.get("PROVIDER_CATALOG", {}))
        enabled_providers = _parse_provider_names(
            raw.get("ENABLED_PROVIDERS"), "IAM_FRAMEWORK.ENABLED_PROVIDERS", allow_missing=True
        )

        read_raw = raw.get("READ", {})
        if not isinstance(read_raw, dict):
            raise ValueError("IAM_FRAMEWORK.READ must be a dict")
        read = ReadConfig(
            providers=_parse_provider_names(
                read_raw.get("PROVIDERS"), "IAM_FRAMEWORK.READ.PROVIDERS", allow_missing=True
            ),
            policy=_parse_identifier(read_raw.get("POLICY", "single"), "IAM_FRAMEWORK.READ.POLICY"),
            options=_parse_options(read_raw.get("OPTIONS"), "IAM_FRAMEWORK.READ.OPTIONS"),
        )

        write_raw = raw.get("WRITE", {})
        if not isinstance(write_raw, dict):
            raise ValueError("IAM_FRAMEWORK.WRITE must be a dict")
        write = WriteConfig(
            providers=_parse_provider_names(
                write_raw.get("PROVIDERS"), "IAM_FRAMEWORK.WRITE.PROVIDERS", allow_missing=True
            ),
            on_failure=_parse_identifier(write_raw.get("ON_FAILURE", "log"), "IAM_FRAMEWORK.WRITE.ON_FAILURE"),
        )

        migration_raw = raw.get("MIGRATION", {})
        if not isinstance(migration_raw, dict):
            raise ValueError("IAM_FRAMEWORK.MIGRATION must be a dict")
        migration = MigrationConfig(
            mode=migration_raw.get("mode", "manual"),
            directory=migration_raw.get("directory", ""),
            allow_destructive=migration_raw.get("allow_destructive", False),
            auto_makemigrations=migration_raw.get("auto_makemigrations", False),
            database=migration_raw.get("database", "default"),
            table_name=migration_raw.get("table_name", "iam_migration_state"),
        )

        bypass_rules: list[BypassRuleConfig] = []
        for item in raw.get("BYPASS_RULES", []):
            if isinstance(item, str):
                bypass_rules.append(BypassRuleConfig(cls=item))
                continue
            if not isinstance(item, dict) or not item.get("class"):
                raise ValueError("Each BYPASS_RULES item must be a dotted path or {'class': ..., 'options': {...}}")
            options = item.get("options", {})
            if not isinstance(options, dict):
                raise ValueError("BYPASS_RULES item options must be a dict")
            bypass_rules.append(BypassRuleConfig(cls=item["class"], options=options))

        return cls(
            actions_module=raw.get("ACTIONS", ""),
            resource_types_module=raw.get("RESOURCE_TYPES", ""),
            roles_module=raw.get("ROLES", ""),
            provider_catalog=provider_catalog,
            enabled_providers=enabled_providers,
            read=read,
            write=write,
            migration=migration,
            bypass_rules=tuple(bypass_rules),
        )


def _parse_provider_catalog(value: Any) -> tuple[ProviderConfig, ...]:
    if not isinstance(value, dict):
        raise ValueError("IAM_FRAMEWORK.PROVIDER_CATALOG must be a dict")

    entries: list[ProviderConfig] = []
    names: set[str] = set()
    for raw_name, spec in value.items():
        name = _parse_identifier(raw_name, "IAM_FRAMEWORK.PROVIDER_CATALOG key")
        if name in names:
            raise ValueError(f"IAM_FRAMEWORK.PROVIDER_CATALOG contains duplicate provider name {name!r}")
        if not isinstance(spec, dict) or not isinstance(spec.get("class"), str) or not spec["class"].strip():
            raise ValueError(f"IAM_FRAMEWORK.PROVIDER_CATALOG[{name!r}] requires non-empty 'class'")
        options = spec.get("options", {})
        if not isinstance(options, dict):
            raise ValueError(f"IAM_FRAMEWORK.PROVIDER_CATALOG[{name!r}].options must be a dict")
        names.add(name)
        entries.append(ProviderConfig(name=name, cls=spec["class"], options=options))
    return tuple(entries)


def _parse_provider_names(value: Any, field_name: str, *, allow_missing: bool = False) -> tuple[str, ...]:
    # 迁移命令只读取 MIGRATION 配置，允许它们以最小 IAM_FRAMEWORK 配置启动；
    # 真正创建运行时框架时，load_framework 会要求三组 Provider 引用完整存在。
    if value is None and allow_missing:
        return ()
    if isinstance(value, str):
        raw_names = value.split(",")
    elif isinstance(value, list | tuple):
        raw_names = value
    else:
        raise ValueError(f"{field_name} must be a comma-separated string, list, or tuple of provider names")
    names = tuple(_parse_identifier(name, field_name) for name in raw_names)
    if not names:
        raise ValueError(f"{field_name} must contain at least one provider name")
    if len(set(names)) != len(names):
        raise ValueError(f"{field_name} must not contain duplicate provider names: {list(names)}")
    return names


def _parse_identifier(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip().lower()


def _parse_options(value: Any, field_name: str) -> dict[str, Any]:
    """解析一个策略的私有参数。

    default.py 通过环境变量传入 JSON 字符串；直接 Python settings 则可传 dict。
    参数的具体含义由被选择的 CompositionPolicy 自己在框架加载期校验。
    """
    if value in (None, ""):
        return {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{field_name} must be valid JSON when configured by environment variable") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a dict or JSON object")
    return dict(value)
