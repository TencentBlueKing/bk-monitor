from functools import lru_cache

from django.conf import settings

from apps.iam.iam_engine.core.config import DynamicModeConfigProvider

IAM_PERMISSION_MODE_CONFIG_ID = "IAM_PERMISSION_MODE"
DEFAULT_MODE_CACHE_TTL = 30


def _load_mode_from_global_config():
    from apps.log_search.models import GlobalConfig

    return (
        GlobalConfig.objects.filter(config_id=IAM_PERMISSION_MODE_CONFIG_ID).values_list("configs", flat=True).first()
    )


@lru_cache(maxsize=1)
def get_mode_provider() -> DynamicModeConfigProvider:
    return DynamicModeConfigProvider(
        loader=_load_mode_from_global_config,
        ttl_seconds=getattr(settings, "IAM_PERMISSION_MODE_CACHE_TTL", DEFAULT_MODE_CACHE_TTL),
    )
