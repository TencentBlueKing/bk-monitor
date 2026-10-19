"""Monitor product metadata and backend construction, without a framework singleton."""

import json
from threading import RLock

from cachetools import LRUCache
from django.conf import settings
from config.tools.iam_credentials import get_saas_setting, saas_setting
from bkmonitor.iam import definitions
from iam_engine.settings import resolve_iam_gateway_url
from iam_engine.v4.config import V4Options


# Cache only clients, never per-user providers or a dynamic mode snapshot.
_v3_clients = LRUCache(maxsize=128)
_v3_clients_lock = RLock()


def get_system_clients():
    """Keep V3 and V4 system callers aligned; resolve the SaaS identity at use time."""
    return [get_saas_setting("SAAS_APP_CODE"), "bk_monitorv3", "bkci", "bk_paas3", "paasv3cli"]


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
                "clients": get_system_clients(),
                "provider_config": {"host": settings.BK_IAM_RESOURCE_API_HOST, "auth": "basic"},
            },
        }
    if name == "v4":
        return V4Options.from_settings(
            global_credentials=(saas_setting("SAAS_APP_CODE"), saas_setting("SAAS_SECRET_KEY"))
        )
    raise ValueError(f"Unknown IAM provider: {name!r}")


def build_provider(name, tenant_id="system", *, username="", schema=None, options=None):
    """Explicitly inject native capabilities, codecs and clients, as in BKLog."""
    if name not in {"v3", "v4"}:
        raise ValueError(f"Unknown IAM provider: {name!r}")
    from bkmonitor.iam.handlers.resolver import MonitorResourceResolver

    options = options if options is not None else provider_options(name, tenant_id)
    schema = schema if schema is not None else definitions
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
        codec_key = json.dumps(options.get("codec_kwargs", {}), sort_keys=True)
        compat = options.get("enable_v1_compat", is_v1_compat_enabled)

        def client_factory(request_tenant):
            tid = request_tenant or cfg.bk_tenant_id
            code, secret = str(cfg.credentials.app_code), str(cfg.credentials.app_secret)
            key = (tid, code, secret, cfg.base_url, cfg.system.id, codec_key, compat)
            with _v3_clients_lock:
                if key not in _v3_clients:
                    _v3_clients[key] = V3Client(
                        code,
                        secret,
                        cfg.base_url,
                        cfg.system.id,
                        codec,
                        bk_tenant_id=tid,
                        enable_v1_compat=compat,
                    )
                return _v3_clients[key]

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
        from bkmonitor.iam.backends.v4.client import V4Client
        from dataclasses import replace

        if not isinstance(options, V4Options):
            raise TypeError("IAM V4 uses the shared V4Options contract")
        cfg = options

        def client_factory(request_tenant):
            tid = request_tenant or tenant_id
            current = replace(cfg, app_code=str(cfg.app_code), app_secret=str(cfg.app_secret))
            key = (tid, current)
            with lock:
                if key not in clients:
                    clients[key] = V4Client(
                        current,
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
            system_id=cfg.system_id,
            tenant_id=tenant_id,
            username=username,
            batch_chunk_size=cfg.batch_chunk_size,
            batch_max_workers=cfg.batch_max_workers,
        )


def build_providers(tenant_id="system", *, username="", mode=None):
    from bkmonitor.iam.mode import get_mode_provider
    from iam_engine.core.config import DEFAULT_DUAL_STACK

    mode = mode if mode is not None else get_mode_provider().get_mode()
    return {
        target.value: build_provider(target.value, tenant_id, username=username)
        for target in DEFAULT_DUAL_STACK.modes_for(mode)
    }
