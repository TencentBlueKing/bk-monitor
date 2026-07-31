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
class SystemConfig:
    """单个 Provider 的 IAM 系统元信息配置。

    Attributes:
        id: 系统唯一标识（如 "bk_monitor"）
        name: 系统展示名称
        name_en: 英文名（可选）
        description: 系统描述
        managers: 管理员列表
        clients: 可调用该系统权限的应用列表（v4 独有）
        callback_url: 权限回调地址
        extensions: 额外扩展字段
    """

    id: str
    name: str
    name_en: str = ""
    description: str = ""
    managers: tuple[str, ...] = ()
    clients: tuple[str, ...] = ()
    callback_url: str = ""
    extensions: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderConfig:
    """单个 Provider 的配置。

    Attributes:
        cls: Provider 类的 dotted path（如 "iam_engine.builtin.v4.provider.V4PermissionProvider"）
        options: 实例化参数（system/base_url/credentials_key/timeout 等
    """

    cls: str
    options: dict[str, Any] = field(default_factory=dict)

    @property
    def system(self) -> SystemConfig | None:
        raw = self.options.get("system")
        if raw is None:
            return None
        if isinstance(raw, SystemConfig):
            return raw
        return SystemConfig(**raw)


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
        mode: 迁移模式
            - "auto": AppConfig.ready() 时自动 plan + apply（CREATE+UPDATE，不含 DELETE）
            - "auto_full": 同上但包含 DELETE（生产不建议）
            - "semi_auto": Django post_migrate 信号触发；DELETE 只警告不执行
            - "manual": 仅通过 CLI 触发（生产推荐）
        allow_destructive: 是否允许破坏性变更（删除、字段收窄等），默认 False
        soft_delete: deprecated=True 的 action 软删除（加 [已废弃] 前缀），默认 True
        continue_on_error: 单条 change 失败是否继续，默认 False
        log_to_file: 是否将 MigrationReport 落文件
    """

    mode: str = "auto"
    allow_destructive: bool = False
    soft_delete: bool = True
    continue_on_error: bool = False
    log_to_file: bool = True


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
        credentials_provider: 凭据解析 callable 的 dotted path
        migration: 迁移配置
        bypass_rules: BypassRule 类的 dotted path 列表
    """

    actions_module: str = ""
    resource_types_module: str = ""
    roles_module: str = ""
    providers: tuple[ProviderConfig, ...] = ()
    composition: CompositionConfig = field(default_factory=CompositionConfig)
    credentials_provider: str = ""
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
        migration = MigrationConfig(**raw.get("MIGRATION", {}))
        return cls(
            actions_module=raw.get("ACTIONS", ""),
            resource_types_module=raw.get("RESOURCE_TYPES", ""),
            roles_module=raw.get("ROLES", ""),
            providers=providers,
            composition=composition,
            credentials_provider=raw.get("CREDENTIALS_PROVIDER", ""),
            migration=migration,
            bypass_rules=tuple(raw.get("BYPASS_RULES", [])),
        )
