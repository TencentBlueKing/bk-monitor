from bk_monitor_base.config import get_config


class ControllerTaskEngine:
    CELERY = "celery"


REDIS_KEY_PREFIX = f"{get_config().common.redis_key_prefix}meta:"
