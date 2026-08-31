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
# V3 Provider 配置契约
#
# 风格对齐 V4Options，frozen dataclass + from_dict() 启动期校验。
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class V3Credentials:
    """V3 Provider 凭据契约。

    Attributes:
        app_code:   蓝鲸应用 ID（IAM SDK app_code）
        app_secret: 蓝鲸应用密钥（IAM SDK app_secret）
    """

    app_code: str
    app_secret: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> V3Credentials:
        try:
            return cls(app_code=raw["app_code"], app_secret=raw["app_secret"])
        except KeyError as exc:
            raise ValueError(f"V3 credentials 缺少必填字段 {exc.args[0]!r}; 需要: app_code, app_secret") from exc


@dataclass(frozen=True)
class V3SystemInfo:
    """V3 Provider 的接入系统信息契约（对齐平台 system 模型字段）。

    Attributes:
        id:             系统唯一标识（如 "bk_monitorv3"）
        name:           系统展示名
        description:    系统描述
        name_en:        系统英文名；空串 = 未配置（系统迁移不管理，保留远端值）
        description_en: 系统英文描述；空串 = 未配置（同上）
        clients:        允许调用该系统权限的蓝鲸应用列表

    注：平台 system 模型无 managers 字段（老版本迁移 json 亦无），
    故配置契约中不提供；老 json 的 name_en/description_en 由远端保留，
    本地为空串时不参与比较与更新。
    """

    id: str
    name: str
    description: str = ""
    name_en: str = ""
    description_en: str = ""
    clients: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> V3SystemInfo:
        try:
            return cls(
                id=raw["id"],
                name=raw["name"],
                description=raw.get("description", ""),
                name_en=raw.get("name_en", ""),
                description_en=raw.get("description_en", ""),
                clients=tuple(raw.get("clients", ())),
            )
        except KeyError as exc:
            raise ValueError(
                f"V3 system 缺少必填字段 {exc.args[0]!r}; "
                "需要: id, name (可选: description, name_en, description_en, clients)"
            ) from exc


@dataclass(frozen=True)
class V3Options:
    """V3 Provider 完整配置契约，即 IAM_FRAMEWORK.PROVIDERS[*].options 的强类型表示。

    使用方式：
        cfg = V3Options.from_dict(options)
        client = V3Client(
            cfg.credentials.app_code,
            cfg.credentials.app_secret,
            cfg.base_url,
            system_id=cfg.system.id,
            codec=codec_instance,
            bk_tenant_id=cfg.bk_tenant_id,
        )

    Attributes:
        base_url:     IAM V3 APIGW 基础地址，必填
        credentials:  凭据（app_code / app_secret）
        system:       系统信息（id / name 等）
        bk_tenant_id: 租户 ID，传给客户端构造器
        timeout:      HTTP 请求超时（秒），默认 30
        chunk_size:   批量鉴权分片大小，默认 20
        max_workers:  批量鉴权分片的并发工作线程数，1 表示串行
        fallback_apply_url: 平台生成申请页 URL 失败/为空时的兜底跳转地址。
            为空则维持既有降级契约（`_get_apply_url_dialect` 返回 ""）；
            非空则返回该地址，让前端至少能给用户一个可点击的兜底链接
            （典型值：IAM SaaS 站点根 URL，如 `BK_IAM_SAAS_HOST`）。
    """

    base_url: str
    credentials: V3Credentials
    system: V3SystemInfo
    bk_tenant_id: str = "system"
    timeout: int = 30
    chunk_size: int = 20
    max_workers: int = 1
    #: 资源类型注册时的 provider_config.path（bkmonitor 资源实例回调 API）。
    #: 老版本在部署下发的 iam_migrations json 中配置
    provider_config_path: str = "/rest/v2/iam/resource/"
    #: 平台生成申请 URL 失败时的兜底跳转地址；默认空 = 维持既有行为（返回 ""）。
    fallback_apply_url: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> V3Options:
        """从 IAM_FRAMEWORK.PROVIDERS[*].options 字典构建强类型配置。

        约定：
            * 必填字段缺失或类型错误 → 抛 ValueError（fail fast）
            * 未知字段收纳到 extra，不报错但可供调试
        """
        known = {
            "base_url",
            "credentials",
            "system",
            "bk_tenant_id",
            "timeout",
            "chunk_size",
            "max_workers",
            "provider_config_path",
            "fallback_apply_url",
        }
        try:
            base_url = raw["base_url"]
            credentials_raw = raw["credentials"]
            system_raw = raw["system"]
        except KeyError as exc:
            raise ValueError(f"V3Options 缺少必填字段 {exc.args[0]!r}; 需要: base_url, credentials, system") from exc

        if not isinstance(credentials_raw, dict):
            raise ValueError("V3Options.credentials 必须是 dict")
        if not isinstance(system_raw, dict):
            raise ValueError("V3Options.system 必须是 dict")

        extra = {k: v for k, v in raw.items() if k not in known}

        return cls(
            base_url=str(base_url),
            credentials=V3Credentials.from_dict(credentials_raw),
            system=V3SystemInfo.from_dict(system_raw),
            bk_tenant_id=raw.get("bk_tenant_id", "system"),
            timeout=int(raw.get("timeout", 30)),
            chunk_size=int(raw.get("chunk_size", 20)),
            max_workers=int(raw.get("max_workers", 1)),
            provider_config_path=raw.get("provider_config_path", "/rest/v2/iam/resource/"),
            fallback_apply_url=str(raw.get("fallback_apply_url", "") or ""),
            extra=extra,
        )
