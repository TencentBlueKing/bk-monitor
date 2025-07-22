from abc import ABC, abstractmethod
from typing import Any

from alarm_backends.core.cache.key import PUBLIC_KEY_PREFIX
from alarm_backends.core.storage.redis import Cache
from constants.common import DEFAULT_TENANT_ID


class CMDBCacheManager(ABC):
    cache = Cache("cache-cmdb")
    cache_type: str
    CACHE_TIMEOUT = 60 * 60 * 24

    @staticmethod
    def _get_cache_key_prefix(bk_tenant_id: str) -> str:
        """
        获取缓存key前缀（兼容非多租户环境）
        :param bk_tenant_id: 租户ID
        :return: 缓存key前缀
        """
        if bk_tenant_id == DEFAULT_TENANT_ID:
            return f"{PUBLIC_KEY_PREFIX}.cache.cmdb"
        return f"{bk_tenant_id}.{PUBLIC_KEY_PREFIX}.cache.cmdb"

    @classmethod
    def get_cache_key(cls, bk_tenant_id: str) -> str:
        """
        获取缓存key
        :param bk_tenant_id: 租户ID
        :return: 缓存key
        """
        return f"{cls._get_cache_key_prefix(bk_tenant_id)}.{cls.cache_type}"

    @abstractmethod
    @classmethod
    def get(cls, *args, **kwargs) -> Any:
        """
        获取缓存
        :param bk_tenant_id: 租户ID
        :param kwargs: 其他参数
        :return: 缓存
        """
        raise NotImplementedError
