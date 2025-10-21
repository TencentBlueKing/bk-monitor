import json
import logging
import time
from contextlib import contextmanager

from django.conf import settings

from apm.constants import (
    APM_ENDPOINT,
    APM_TOPO_INSTANCE,
    DEFAULT_APM_CACHE_EXPIRE,
)
from bkmonitor.utils.common_utils import uniqid4
from core.errors.alarm_backends import LockError

logger = logging.getLogger("apm_topo")


class ApmCacheHandler:
    def __init__(self):
        self.redis_client = self.get_redis_client()

    @staticmethod
    def get_redis_client():
        from metadata.utils.redis_tools import RedisTools

        return RedisTools().client

    @staticmethod
    def decode_redis_value(value):
        """
        解码后的字符串或默认值
        """
        if value is None:
            return None

        if isinstance(value, bytes):
            return value.decode("utf-8")
        else:
            return str(value)

    def get_cache_data(self, name: str) -> dict:
        """
        获取应用 topoinstance 缓存数据
        """
        json_res = self.redis_client.get(name)
        if json_res:
            return json.loads(json_res)
        return {}

    @staticmethod
    def get_topo_instance_cache_key(bk_biz_id, app_name):
        """
        组装 key 值
        """
        return APM_TOPO_INSTANCE.format(settings.PLATFORM, settings.ENVIRONMENT, bk_biz_id, app_name)

    @staticmethod
    def get_endpoint_cache_key(bk_biz_id, app_name):
        return APM_ENDPOINT.format(settings.PLATFORM, settings.ENVIRONMENT, bk_biz_id, app_name)

    def refresh_data(self, name: str, update_map: dict, ex: int = DEFAULT_APM_CACHE_EXPIRE):
        """
        更新、删除数据
        """
        if not update_map:
            return

        self.redis_client.set(name, json.dumps(update_map), ex=ex)
        logger.info(f"[InstanceDiscover] {name} update {len(update_map)}")

    def get_lock_key(self, lock_type: str, **kwargs) -> str:
        """
        生成锁的key，仿造原有的key格式
        """
        if lock_type == "topo_discover":
            return f"apm.tasks.topo.discover.{kwargs.get('app_id')}"
        elif lock_type == "datasource_discover":
            return f"apm.tasks.datasource.discover.{kwargs.get('app_id')}"
        elif lock_type == "profile_discover":
            return f"apm_profile.tasks.discover.{kwargs.get('bk_biz_id')}:{kwargs.get('app_name')}"
        else:
            # 通用格式
            key_parts = ["apm", "tasks", lock_type]
            for key, value in kwargs.items():
                key_parts.append(f"{key}_{value}")
            return ".".join(key_parts)

    @contextmanager
    def distributed_lock(self, lock_type: str, ttl: int = 600, **kwargs):
        """
        分布式锁上下文管理器，仿造service_lock的实现方式

        Args:
            lock_type: 锁类型，如 'topo_discover', 'datasource_discover'
            ttl: 锁的过期时间（秒），默认10分钟
            **kwargs: 用于生成锁key的参数
        """
        lock = None
        lock_key = self.get_lock_key(lock_type, **kwargs)

        try:
            lock = ApmLock(lock_key, ttl, self.redis_client)
            if lock.acquire(0.1):
                yield lock
            else:
                raise LockError(msg=f"{lock_key} is already locked")
        except LockError as err:
            raise err
        finally:
            if lock is not None:
                lock.release()


class ApmLock:
    """APM分布式锁实现，仿造RedisLock的实现方式"""

    def __init__(self, name, ttl=600, redis_client=None):
        self.name = name
        self.ttl = ttl  # 默认10分钟过期
        self.redis_client = redis_client
        self.__token = None

    def acquire(self, wait_time=0.1):
        """获取锁"""
        token = uniqid4()
        wait_until = time.time() + wait_time

        while not self.redis_client.set(self.name, token, ex=self.ttl, nx=True):
            if time.time() < wait_until:
                time.sleep(0.01)
            else:
                return False

        self.__token = token
        return True

    def release(self):
        """释放锁"""
        if not self.__token:
            return False

        token = self.redis_client.get(self.name)
        if not token:
            # 锁已经不存在（可能已过期），直接返回True
            return True

        token_str = ApmCacheHandler.decode_redis_value(token)
        if token_str is None or token_str != self.__token:
            return False

        return self.redis_client.delete(self.name)
