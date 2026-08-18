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
# FrameworkConfig —— 框架配置的强类型表示
#
# 把 Django settings.IAM_FRAMEWORK 字典转成结构化的 frozen dataclass，
# 放在 core/ 而非 django/，保持零 Django 依赖。
#
# django/conf.py:load_framework() 负责：
#   1. 读 settings.IAM_FRAMEWORK 原始 dict
#   2. 构建 FrameworkConfig 实例
#   3. 用 import_class 解析 dotted path → 组装 IAMFramework
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProviderConfig:
    """单个 Provider 的配置。

    Attributes:
        cls: Provider 类的 dotted path（如 "bkmonitor.iam.iam_v4.provider.V4PermissionProvider"）
        options: 实例化参数。完全由 Provider 自己定义结构，包含业务配置
            （如 base_url）、凭据（credentials 字子典）、系统信息（system
            子字典）等。框架不解析 options 内部结构，直接透传给 Provider。
    """

    cls: str
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CompositionConfig:
    """组合策略配置。

    Attributes:
        policy: 策略名称（"single"/"any_of"/"all_of"/"primary"）
        options: 策略参数（max_workers/strict_errors/fallback_on_error 等）
    """

    policy: str = "single"
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MigrationConfig:
    """Schema 迁移配置。

    Attributes:
        mode: 迁移触发模式
            - "manual":    仅 CLI 触发（生产推荐）；破坏性变更由
                           `iam_engine_migrate --allow-destructive` 显式启用
            - "semi_auto": 挂 Django post_migrate 信号，跟随 `manage.py migrate`
                           部署脚本触发；破坏性变更由 `allow_destructive: True`
                           配置项启用（与 CLI flag 语义完全对齐）
        directory: 系统级迁移文件目录（所有 Provider 共用）
        allow_destructive: 全局破坏性开关。
            semi_auto 模式下直接生效；manual 模式下作为 CLI --allow-destructive 的默认值
            （命令行显式传入时优先）。默认 False，破坏性变更（DELETE / 方言 id 变更重建）
            会被 skip 并告警。
        auto_makemigrations: 保留字段（当前不使用）
    """

    mode: str = "manual"
    directory: str = ""
    allow_destructive: bool = False
    auto_makemigrations: bool = False


@dataclass(frozen=True)
class FrameworkConfig:
    """iam_engine 全局配置。

    由 django/conf.py:load_framework() 从 settings.IAM_FRAMEWORK 构建，
    再驱动 IAMFramework 的装配。

    Attributes:
        actions_module: ActionDef 定义的 dotted path
        resource_types_module: ResourceTypeDef 定义的 dotted path
        roles_module: RoleDef 定义的 dotted path（可选）
        providers: Provider 配置列表
        composition: 组合策略配置
        migration: 迁移配置
        bypass_rules: BypassRule 类的 dotted path 列表
    """

    actions_module: str = ""
    resource_types_module: str = ""
    roles_module: str = ""
    providers: tuple[ProviderConfig, ...] = ()
    composition: CompositionConfig = field(default_factory=CompositionConfig)
    migration: MigrationConfig = field(default_factory=MigrationConfig)
    bypass_rules: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, raw: dict) -> FrameworkConfig:
        """从 settings.IAM_FRAMEWORK 字典构建强类型配置。

        settings dict key 使用 UPPER_CASE，此方法完成映射。
        """
        providers = tuple(
            ProviderConfig(
                cls=item["class"],
                options=item.get("options", {}),
            )
            for item in raw.get("PROVIDERS", [])
        )
        composition = CompositionConfig(
            policy=raw.get("COMPOSITION", {}).get("policy", "single"),
            options=raw.get("COMPOSITION", {}).get("options", {}),
        )
        migration_raw = raw.get("MIGRATION", {})
        migration = MigrationConfig(
            mode=migration_raw.get("mode", "manual"),
            directory=migration_raw.get("directory", ""),
            allow_destructive=migration_raw.get("allow_destructive", False),
            auto_makemigrations=migration_raw.get("auto_makemigrations", False),
        )
        return cls(
            actions_module=raw.get("ACTIONS", ""),
            resource_types_module=raw.get("RESOURCE_TYPES", ""),
            roles_module=raw.get("ROLES", ""),
            providers=providers,
            composition=composition,
            migration=migration,
            bypass_rules=tuple(raw.get("BYPASS_RULES", [])),
        )
