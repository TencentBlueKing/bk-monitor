"""Monitor product metadata and backend construction, without a framework singleton."""

from functools import lru_cache

from django.conf import settings
from config.tools.iam_credentials import get_saas_setting
from bkmonitor.iam.definitions.actions import Actions
from bkmonitor.iam.definitions.resource_types import ResourceTypes
from bkmonitor.iam.definitions.roles import Roles
from iam_engine.schema.registry import SchemaRegistry
from iam_engine.schema.loaders import load_from_class
from iam_engine.settings import resolve_iam_gateway_url
from iam_engine.v4.gateway import resolve_v4_gateway_url


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
            "base_url": resolve_iam_gateway_url(
                settings.BK_COMPONENT_API_URL,
                settings.BK_IAM_V3_API_BASE_URL,
                settings.BK_IAM_APIGATEWAY_URL,
                version="v3",
            ),
            "bk_tenant_id": tenant_id,
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
            "base_url": resolve_v4_gateway_url(),
            "bk_tenant_id": tenant_id,
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


def build_provider(name, tenant_id="system", *, username="", schema=None, options=None):
    """Explicitly inject native capabilities, codecs and clients, as in BKLog."""
    if name not in {"v3", "v4"}:
        raise ValueError(f"Unknown IAM provider: {name!r}")
    from threading import RLock
    from bkmonitor.iam.handlers.resolver import MonitorResourceResolver

    options = options if options is not None else provider_options(name, tenant_id)
    schema = schema if schema is not None else get_schema()
    clients = {}
    lock = RLock()
    if name == "v3":
        from bkmonitor.iam.backends.v3.provider import V3PermissionProvider
        from bkmonitor.iam.backends.v3.compat import is_v1_compat_enabled
        from bkmonitor.iam.backends.v3.config import V3Options
        from bkmonitor.iam.backends.v3.client import V3Client
        from bkmonitor.iam.backends.v3.codec import MonitorV3Codec

        cfg = V3Options.from_dict(options)
        codec = MonitorV3Codec(**options.get("codec_kwargs", {}))

        def client_factory(request_tenant):
            tid = request_tenant or cfg.bk_tenant_id
            code, secret = str(cfg.credentials.app_code), str(cfg.credentials.app_secret)
            key = (tid, code, secret)
            with lock:
                if key not in clients:
                    clients[key] = V3Client(
                        code,
                        secret,
                        cfg.base_url,
                        cfg.system.id,
                        codec,
                        bk_tenant_id=tid,
                        enable_v1_compat=options.get("enable_v1_compat", is_v1_compat_enabled),
                    )
                return clients[key]

        return V3PermissionProvider(
            None,
            cfg.system.id,
            codec=codec,
            schema=schema,
            resolver=MonitorResourceResolver(),
            client_factory=client_factory,
            configuration=cfg,
            tenant_id=cfg.bk_tenant_id,
            username=username,
        )
    else:
        from bkmonitor.iam.backends.v4.provider import V4PermissionProvider
        from bkmonitor.iam.backends.v4.codec import MonitorV4Codec
        from bkmonitor.iam.backends.v4.config import V4Options, make_client_options
        from bkmonitor.iam.backends.v4.client import V4Client
        from iam_engine.v4.config import load_v4_paths
        from dataclasses import replace

        options = {"api_paths": load_v4_paths(settings), **options}
        cfg = V4Options.from_dict(options)

        def client_factory(request_tenant):
            tid = request_tenant or cfg.bk_tenant_id
            code, secret = str(cfg.credentials.app_code), str(cfg.credentials.app_secret)
            key = (tid, code, secret)
            with lock:
                if key not in clients:
                    clients[key] = V4Client(
                        replace(make_client_options(cfg), app_code=code, app_secret=secret),
                        username=username,
                        bk_tenant_id=tid,
                    )
                return clients[key]

        return V4PermissionProvider(
            None,
            codec=MonitorV4Codec(),
            schema=schema,
            resolver=MonitorResourceResolver(),
            client_factory=client_factory,
            configuration=cfg,
            tenant_id=cfg.bk_tenant_id,
            username=username,
            batch_chunk_size=cfg.chunk_size,
            batch_max_workers=cfg.max_workers,
        )


def build_providers(tenant_id="system", *, username="", mode=None):
    from bkmonitor.iam.mode import get_mode_provider
    from iam_engine.core.config import DEFAULT_DUAL_STACK

    mode = mode if mode is not None else get_mode_provider().get_mode()
    return {
        target.value: build_provider(target.value, tenant_id, username=username)
        for target in DEFAULT_DUAL_STACK.modes_for(mode)
    }
