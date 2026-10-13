"""Monitor product metadata and backend construction, without a framework singleton."""

import os
from functools import lru_cache

from django.conf import settings
from config.tools.iam_credentials import get_saas_setting
from ..definitions.actions import Actions
from ..definitions.resource_types import ResourceTypes
from ..definitions.roles import Roles
from iam_engine.schema.registry import SchemaRegistry
from iam_engine.schema.loaders import load_from_class


@lru_cache(maxsize=1)
def get_schema():
    schema = SchemaRegistry()
    for definitions in (Actions, ResourceTypes, Roles):
        load_from_class(schema, definitions)
    schema.freeze()
    return schema


def provider_options(name, tenant_id="system"):
    if name == "v3":
        return {
            "codec_class": "bkmonitor.iam.adapters.v3.codec.MonitorV3Codec",
            "resolver_class": "bkmonitor.iam.adapters.resolver.MonitorResourceResolver",
            "base_url": settings.BK_IAM_V3_API_BASE_URL,
            "bk_tenant_id": tenant_id,
            "provider_config_path": os.getenv("BK_IAM_V3_RESOURCE_PATH", "/rest/v2/iam/resource/"),
            "fallback_apply_url": settings.BK_IAM_V3_FALLBACK_APPLY_URL,
            "credentials": {
                "app_code": get_saas_setting("SAAS_APP_CODE"),
                "app_secret": get_saas_setting("SAAS_SECRET_KEY"),
            },
            "system": {
                "id": settings.BK_IAM_SYSTEM_ID,
                "name": "监控平台",
                "description": (
                    "蓝鲸监控平台是一款针对主机和互联网应用进行监控的产品，监控服务可用于收集主机资源"
                    "（系统性能、组件服务、数据库、日志等）的监控指标，探测互联网应用服务的可用性，"
                    "并对指标进行告警设置。"
                ),
                "name_en": "BKMonitor",
                "description_en": (
                    "BKMonitor is a product that monitors the host and Internet applications. "
                    "The monitoring service can be used to collect monitoring metrics of host "
                    "(system performance, component services, databases, logs, etc.), detect the "
                    "availability of Internet application services, and set alarms for metrics."
                ),
                "clients": [get_saas_setting("SAAS_APP_CODE"), "bk_monitorv3", "bkci", "bk_paas3", "paasv3cli"],
                "provider_config": {"host": settings.BK_IAM_RESOURCE_API_HOST, "auth": "basic"},
            },
        }
    if name == "v4":
        return {
            "codec_class": "bkmonitor.iam.adapters.v4.codec.MonitorV4Codec",
            "resolver_class": "bkmonitor.iam.adapters.resolver.MonitorResourceResolver",
            "base_url": settings.BK_IAM_V4_APIGATEWAY_URL,
            "bk_tenant_id": tenant_id,
            "fallback_apply_url": settings.BK_IAM_SAAS_HOST,
            "credentials": {
                "app_code": get_saas_setting("SAAS_APP_CODE"),
                "app_secret": get_saas_setting("SAAS_SECRET_KEY"),
            },
            "system": {
                "id": settings.BK_IAM_V4_SYSTEM_ID or settings.BK_IAM_SYSTEM_ID,
                "name": "蓝鲸监控平台",
                "description": "蓝鲸监控平台-IAMv4 权限系统",
                "callback_url": settings.BK_IAM_V4_CALLBACK_URL
                or f"{settings.BK_IAM_RESOURCE_API_HOST.rstrip('/')}/rest/v2/iam/v4/callback/",
                "managers": [m.strip() for m in settings.BK_IAM_V4_MODEL_MANAGERS.split(",") if m.strip()],
                "clients": [get_saas_setting("SAAS_APP_CODE")],
            },
            "timeout": settings.BK_IAM_V4_TIMEOUT,
            "chunk_size": settings.BK_IAM_V4_BATCH_CHUNK_SIZE,
            "max_workers": settings.BK_IAM_V4_BATCH_MAX_WORKERS,
        }
    raise ValueError(f"Unknown IAM provider: {name!r}")


def build_provider(name, tenant_id="system"):
    options = provider_options(name, tenant_id)
    if name == "v3":
        from .v3.provider import V3PermissionProvider
        from ..adapters.v3.config import is_v1_compat_enabled

        options["enable_v1_compat"] = is_v1_compat_enabled
        cls = V3PermissionProvider
    else:
        from .v4.provider import V4PermissionProvider
        from iam_engine.v4.config import load_v4_paths

        options["api_paths"] = load_v4_paths(settings)
        cls = V4PermissionProvider
    return cls(get_schema(), **options)


def build_providers(tenant_id="system"):
    names = ("v3", "v4") if settings.BK_IAM_V4_APIGATEWAY_URL else ("v3",)
    return {name: build_provider(name, tenant_id) for name in names}
