from __future__ import annotations

from django.conf import settings
from django.core.cache import cache

from apps.iam.backends.v3.client import CompatibleIAM
from apps.iam.backends.v4.client import V4Client
from apps.iam.backends.v4.config import V4Options, resolve_effective_v4_system_id
from apps.utils.log import logger


class V4CallbackIAM(CompatibleIAM):
    """V4 资源回调鉴权客户端：token 从 bkiam(V4) 拉取，而不是 V3 的 bk-iam 网关。"""

    def get_token(self, system):
        if system == resolve_effective_v4_system_id() and getattr(settings, "BK_IAM_V4_APIGATEWAY_URL", ""):
            return self._get_v4_auth_token(system)

        return super().get_token(system)

    def _get_v4_auth_token(self, system_id: str):
        bk_tenant_id = getattr(self._client, "_bk_tenant_id", "") or settings.BK_APP_TENANT_ID
        try:
            options = V4Options.from_settings(bk_tenant_id=bk_tenant_id, for_resource_callback=True)
        except Exception as error:  # pylint: disable=broad-except
            logger.error("[V4CallbackIAM] build V4 options failed: system=%s error=%s", system_id, error)
            return False, str(error), ""
        cache_key = f"bklog:iam:v4:auth-token:{bk_tenant_id}:{system_id}"
        try:
            cached_token = cache.get(cache_key)
        except Exception as error:  # pylint: disable=broad-except
            logger.warning(
                "[V4CallbackIAM] read auth token cache failed: system=%s tenant=%s error=%s",
                system_id,
                bk_tenant_id,
                error,
            )
            cached_token = None
        if cached_token:
            return True, "success", str(cached_token)

        try:
            client = V4Client(
                options,
                bk_tenant_id=bk_tenant_id,
            )
            token = client.retrieve_system_auth_token(system_id)
        except Exception as error:  # pylint: disable=broad-except
            logger.error("[V4CallbackIAM] get V4 auth token failed: system=%s error=%s", system_id, error)
            return False, str(error), ""

        if not token:
            return False, "empty auth_token from IAM V4", ""

        if options.auth_token_cache_seconds > 0:
            try:
                cache.set(cache_key, token, options.auth_token_cache_seconds)
            except Exception as error:  # pylint: disable=broad-except
                # 缓存故障不应使已经成功获取的 token 失效。
                logger.warning(
                    "[V4CallbackIAM] write auth token cache failed: system=%s tenant=%s error=%s",
                    system_id,
                    bk_tenant_id,
                    error,
                )
        return True, "success", token
