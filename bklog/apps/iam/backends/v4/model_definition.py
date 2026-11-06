"""BKLog's single model baseline and deployment-specific metadata."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from typing import Any
from urllib.parse import urljoin

from django.conf import settings
from apps.iam.backends.v4.config import resolve_effective_v4_system_id
from iam_engine.model.definition import (
    ModelDefinition as ModelDefinition,
    ModelDefinitionError as ModelDefinitionError,
    ResourceTypeDefinition as ResourceTypeDefinition,
    build_model_definition as build_model_definition,
)

DEFAULT_MODEL_DIR = os.path.join("support-files", "iam", "v4")
CURRENT_MODEL_FILE = "0001_initial.json"
V4_RESOURCE_CALLBACK_PATH = "api/v1/iam/v4/resource/"
ACTIONS_NOT_REGISTERED_IN_V4 = frozenset({"view_dashboard", "manage_dashboard"})


def resolve_model_file_path(file_name: str = CURRENT_MODEL_FILE) -> str:
    model_dir = str(getattr(settings, "BK_IAM_V4_MODEL_DIR", "") or "").strip()
    if not model_dir:
        model_dir = os.path.join(settings.BASE_DIR, DEFAULT_MODEL_DIR)
    return os.path.join(model_dir, file_name)


def load_model_payload(file_name: str = CURRENT_MODEL_FILE) -> dict[str, Any]:
    file_path = resolve_model_file_path(file_name)
    try:
        with open(file_path, encoding="utf-8") as model_file:
            payload = json.load(model_file)
    except FileNotFoundError as error:
        raise ModelDefinitionError(f"IAM V4 model baseline not found: {file_path}") from error
    except json.JSONDecodeError as error:
        raise ModelDefinitionError(f"IAM V4 model baseline is not valid JSON: {file_path}") from error

    if not isinstance(payload, dict):
        raise ModelDefinitionError("IAM V4 model baseline must be a JSON object")
    return payload


def resolve_callback_url() -> str:
    """V4 资源回调地址：优先显式配置，否则由资源回调 Host 拼出 V4 专用路径。"""
    explicit = str(getattr(settings, "BK_IAM_V4_CALLBACK_URL", "") or "").strip()
    if explicit:
        return explicit

    host = str(getattr(settings, "BK_IAM_RESOURCE_API_HOST", "") or "").strip()
    if not host:
        raise ModelDefinitionError(
            "IAM V4 callback url is not resolvable; set BK_IAM_V4_CALLBACK_URL or BK_IAM_RESOURCE_API_HOST"
        )
    return urljoin(host.rstrip("/") + "/", V4_RESOURCE_CALLBACK_PATH)


def resolve_model_managers() -> tuple[str, ...] | None:
    raw = getattr(settings, "BK_IAM_V4_MODEL_MANAGERS", "")
    if raw is None:
        return None
    if isinstance(raw, str):
        managers = [item.strip() for item in raw.split(",")]
    elif isinstance(raw, Iterable):
        managers = [str(item).strip() for item in raw]
    else:
        raise ModelDefinitionError(f"invalid BK_IAM_V4_MODEL_MANAGERS: {raw!r}")

    managers = [manager for manager in managers if manager]
    if not managers:
        return None
    return tuple(dict.fromkeys(managers))


def load_model_definition(file_name: str = CURRENT_MODEL_FILE) -> ModelDefinition:
    """按当前 settings 加载期望态模型。"""
    return build_model_definition(
        load_model_payload(file_name),
        system_id=resolve_effective_v4_system_id(),
        callback_url=resolve_callback_url(),
        managers=resolve_model_managers(),
        extra_clients=[str(getattr(settings, "APP_CODE", "") or "").strip()],
    )
