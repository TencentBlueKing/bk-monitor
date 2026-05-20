"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

ALLOWED_ID_PREFIXES = ("get_", "list_", "query_", "fetch_", "search_", "describe_", "inspect_")
# id 任意位置不得含写动作语义，PR 评审前的语法层防线
BANNED_ID_SUBSTRINGS = (
    "_delete",
    "_create",
    "_update",
    "_remove",
    "_write",
    "_set_",
    "_put_",
    "_patch_",
    "_apply",
    "_start",
    "_stop",
    "_send",
    "_dispatch",
)
VALID_INVOKE_STYLES = ("kwargs", "positional_dict")
VALID_CACHE_BYPASS_METHODS = ("refresh", "cacheless")


@dataclass
class OperationSpec:
    """一个具体的 api.<domain>.<resource> 能力描述。

    handler 永不暴露给 agent；params_schema_override 优先于 RequestSerializer 反射。
    invoke_style 区分 kwargs（默认）与 positional_dict（如 metadata.kafka_tail）。

    handler 必须是 ``api.<domain>.<resource>`` 函数引用。运行时仅校验 callable + 排除 lambda；
    "必须在 api.* 命名空间内" 的强约束由 ``platform_catalog/_lint.py`` AST 守卫与 PR 审查共同把关。

    cache_bypass_method 用于 invoke 阶段在 ``force_refresh=True`` 时切换调用模式：
    - ``"refresh"``：调 ``handler.request.refresh(...)``，刷新并回写缓存
    - ``"cacheless"``：调 ``handler.request.cacheless(...)``，不读不写缓存
    - ``None``：handler 不支持缓存绕过；``force_refresh`` 视为 noop，meta 中带 warning
    """

    id: str
    summary: str
    handler: Callable[..., Any]
    invoke_style: str = "kwargs"
    cache_bypass_method: str | None = None
    params_schema_override: dict[str, Any] | None = None
    example_params: dict[str, Any] = field(default_factory=dict)
    default_fields: list[str] = field(default_factory=list)
    allowed_fields: list[str] = field(default_factory=list)
    response_postprocess: Callable[[Any, list[str] | None], Any] | None = None
    audit_tags: list[str] = field(default_factory=list)
    required_params: list[str] = field(default_factory=list)
    notes: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ValueError("operation id must be a non-empty string")
        if not any(self.id.startswith(p) for p in ALLOWED_ID_PREFIXES):
            raise ValueError(
                f"operation id {self.id!r} must start with one of {ALLOWED_ID_PREFIXES} (readonly enforcement)"
            )
        for banned in BANNED_ID_SUBSTRINGS:
            if banned in self.id:
                raise ValueError(
                    f"operation id {self.id!r} contains banned write-semantic substring "
                    f"{banned!r} (readonly enforcement)"
                )
        if not callable(self.handler):
            raise ValueError("handler must be callable")
        if getattr(self.handler, "__name__", "") == "<lambda>":
            raise ValueError("handler must not be a lambda; use api.<domain>.<resource> reference")
        if self.invoke_style not in VALID_INVOKE_STYLES:
            raise ValueError(f"invalid invoke_style: {self.invoke_style}; must be one of {VALID_INVOKE_STYLES}")
        if self.cache_bypass_method is not None and self.cache_bypass_method not in VALID_CACHE_BYPASS_METHODS:
            raise ValueError(
                f"invalid cache_bypass_method: {self.cache_bypass_method}; "
                f"must be one of {VALID_CACHE_BYPASS_METHODS} or None"
            )


@dataclass
class DomainSpec:
    """一个能力域（cmdb / metadata / gse / ...）。"""

    id: str
    summary: str
    audit_tags: list[str] = field(default_factory=list)
    operations: dict[str, OperationSpec] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if "readonly" not in self.audit_tags:
            raise ValueError(f"domain {self.id!r} audit_tags must contain 'readonly'")


class PlatformSourceCatalog:
    """渐进披露 catalog：domain → operation 注册表，单例。"""

    _domains: dict[str, DomainSpec] = {}
    _revision: str | None = None

    @classmethod
    def reset(cls) -> None:
        cls._domains = {}
        cls._revision = None

    @classmethod
    def register_domain(
        cls,
        *,
        id: str,
        summary: str,
        audit_tags: list[str] | None = None,
        operations: Iterable[OperationSpec] = (),
    ) -> DomainSpec:
        domain_id = (id or "").strip().lower()
        if not domain_id:
            raise ValueError("domain id must be non-empty")
        if domain_id in cls._domains:
            raise ValueError(f"domain already registered: {domain_id}")
        domain = DomainSpec(id=domain_id, summary=summary, audit_tags=list(audit_tags or []))
        for op in operations:
            domain.operations[op.id] = op
        cls._domains[domain_id] = domain
        cls._revision = None
        return domain

    @classmethod
    def list_domain_ids(cls) -> list[str]:
        return sorted(cls._domains.keys())

    @classmethod
    def get_domain(cls, domain_id: str) -> DomainSpec | None:
        return cls._domains.get((domain_id or "").strip().lower())

    @classmethod
    def revision(cls) -> str:
        if cls._revision is None:
            cls._revision = cls._compute_revision()
        return cls._revision

    @classmethod
    def _compute_revision(cls) -> str:
        catalog_dir = os.path.dirname(os.path.abspath(__file__))
        h = hashlib.sha1()
        for name in sorted(os.listdir(catalog_dir)):
            if not name.endswith(".py") or name.startswith("__"):
                continue
            full_path = os.path.join(catalog_dir, name)
            try:
                with open(full_path, "rb") as f:
                    h.update(name.encode("utf-8"))
                    h.update(f.read())
            except OSError:
                continue
        h.update(repr(sorted(cls._domains.keys())).encode("utf-8"))
        return h.hexdigest()[:12]
