import logging
import os
import random
from typing import Literal

import redis
from redis.sentinel import Sentinel

from bk_monitor_base.metadata.config import settings

logger = logging.getLogger(__name__)


class Singleton:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls._instance, cls):
            cls._instance = object.__new__(cls, *args, **kwargs)
        return cls._instance


class RedisClient(Singleton):
    def __init__(self):
        self.client = redis.StrictRedis(
            host=settings.metadata.django_redis_host,
            port=settings.metadata.django_redis_port,
            password=settings.metadata.django_redis_password,
            db=settings.metadata.django_redis_db,
        )

    def __getattr__(self, item):
        return getattr(self.client, item)

    @classmethod
    def from_envs(
        cls, prefix: str = "BK_MONITOR", prefer_type: Literal["sentinel", "standalone"] = "sentinel"
    ) -> redis.StrictRedis:
        """从环境变量中获取 Redis Client
        :param prefix: 配置前缀
        :param prefer_type: 倾向模式，优先使用哨兵
        :return: redis.StrictRedis
        """
        # sentinel or standalone
        type_ = os.environ.get(f"{prefix}_REDIS_MODE", prefer_type)

        if type_ == "sentinel":
            password = os.environ[f"{prefix}_REDIS_SENTINEL_PASSWORD"]
            sentinel_host = os.environ[f"{prefix}_REDIS_SENTINEL_HOST"]
            sentinel_port = os.environ[f"{prefix}_REDIS_SENTINEL_PORT"]
            # sentinel host支持多个sentinel节点，以分号分隔
            sentinel_params = {
                "sentinels": [(h, int(sentinel_port)) for h in sentinel_host.split(";") if h],
                "sentinel_kwargs": {"password": password},
            }
            # 随机打乱顺序，避免每次都是同一个节点
            random.shuffle(sentinel_params["sentinels"])
            host, port = Sentinel(**sentinel_params).discover_master(os.environ[f"{prefix}_REDIS_SENTINEL_MASTER_NAME"])
            redis_password = os.environ[f"{prefix}_REDIS_PASSWORD"]
            configs = {
                "host": host,
                "port": port,
                "password": redis_password,
            }
        else:
            configs = {
                "host": os.environ[f"{prefix}_REDIS_HOST"],
                "port": os.environ[f"{prefix}_REDIS_PORT"],
                "password": os.environ[f"{prefix}_REDIS_PASSWORD"],
                "db": os.environ.get(f"{prefix}_REDIS_DB", 0),
            }

        return redis.StrictRedis(**configs)
