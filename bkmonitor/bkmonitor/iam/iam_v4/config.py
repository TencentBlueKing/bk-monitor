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
# V4 Provider 配置契约
#
# 这个文件是 V4PermissionProvider 的"配置说明书"：
#   * 用户在 settings.IAM_FRAMEWORK.PROVIDERS[*].options 里传什么字段，
#     直接来这里查 V4Options / V4Credentials / V4SystemInfo。
#   * V4PermissionProvider.__init__ 里调用 V4Options.from_dict(options) 完成
#     强类型解析 + 缺字段/类型错误的启动期校验，出错时立刻 fail fast。
#
# 设计规则：
#   1. 所有配置都从 options 里来，Provider 不读任何 django.conf.settings。
#   2. credentials / system 结构是 V4 私有的（v3 有 v3 自己的 config.py），
#      框架层不做统一。
#   3. dataclass frozen=True，构造后不可变。
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class V4Credentials:
    """V4 Provider 凭据契约。

    Attributes:
        app_code:   蓝鲸应用 ID（走 APIGW 时的 bk_app_code）
        app_secret: 蓝鲸应用密钥（走 APIGW 时的 bk_app_secret）
    """

    app_code: str
    app_secret: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> V4Credentials:
        try:
            return cls(app_code=raw["app_code"], app_secret=raw["app_secret"])
        except KeyError as exc:
            raise ValueError(
                f"V4 credentials missing required field {exc.args[0]!r}; expected keys: app_code, app_secret"
            ) from exc


@dataclass(frozen=True)
class V4SystemInfo:
    """V4 Provider 的接入系统信息契约。

    Attributes:
        id:           系统唯一标识（如 "bk_monitor_v4"）
        name:         系统展示名
        description:  系统描述
        callback_url: 权限中心资源回调地址
        managers:     系统管理员用户名列表
        clients:      允许调用该系统权限的蓝鲸应用列表
    """

    id: str
    name: str
    description: str = ""
    callback_url: str = ""
    managers: tuple[str, ...] = ()
    clients: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> V4SystemInfo:
        try:
            return cls(
                id=raw["id"],
                name=raw["name"],
                description=raw.get("description", ""),
                callback_url=raw.get("callback_url", ""),
                managers=tuple(raw.get("managers", ())),
                clients=tuple(raw.get("clients", ())),
            )
        except KeyError as exc:
            raise ValueError(
                f"V4 system missing required field {exc.args[0]!r}; "
                f"expected keys: id, name (optional: description, callback_url, managers, clients)"
            ) from exc


@dataclass(frozen=True)
class V4Options:
    """V4 Provider 完整配置契约，即 IAM_FRAMEWORK.PROVIDERS[*].options 的强类型表示。

    使用方式：
        cfg = V4Options.from_dict(options)
        client = V4Client(
            base_url=cfg.base_url,
            system_id=cfg.system.id,
            app_code=cfg.credentials.app_code,
            app_secret=cfg.credentials.app_secret,
            timeout=cfg.timeout,
            bk_tenant_id=cfg.bk_tenant_id,
        )

    Attributes:
        base_url:      IAM v4 APIGW 基础地址，必填
        credentials:   凭据（app_code / app_secret）
        system:        系统信息（id / name / callback_url 等）
        bk_tenant_id:  租户 ID，传给客户端构造器（多租户请求头 X-Bk-Tenant-Id 使用）
        timeout:       HTTP 请求超时（秒），默认 30
        chunk_size:    批量鉴权分片大小（v4 单次上限 20）
        max_workers:   批量鉴权分片的并发工作线程数，1 表示串行
    """

    base_url: str
    credentials: V4Credentials
    system: V4SystemInfo
    bk_tenant_id: str = "system"
    timeout: int = 30
    chunk_size: int = 20
    max_workers: int = 1
    # 预留：Provider 私有扩展字段（未识别的 options 会被收纳到此，方便调试/演进）
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> V4Options:
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
        }
        try:
            base_url = raw["base_url"]
            credentials_raw = raw["credentials"]
            system_raw = raw["system"]
        except KeyError as exc:
            raise ValueError(
                f"V4Options missing required field {exc.args[0]!r}; expected keys: base_url, credentials, system"
            ) from exc

        if not isinstance(credentials_raw, dict):
            raise ValueError("V4Options.credentials must be a dict")
        if not isinstance(system_raw, dict):
            raise ValueError("V4Options.system must be a dict")

        extra = {k: v for k, v in raw.items() if k not in known}

        return cls(
            base_url=str(base_url),
            credentials=V4Credentials.from_dict(credentials_raw),
            system=V4SystemInfo.from_dict(system_raw),
            bk_tenant_id=str(raw.get("bk_tenant_id", "system")),
            timeout=int(raw.get("timeout", 30)),
            chunk_size=int(raw.get("chunk_size", 20)),
            max_workers=int(raw.get("max_workers", 1)),
            extra=extra,
        )
