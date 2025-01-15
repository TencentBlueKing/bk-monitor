# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import os
import random

import redis
from django.conf import settings
from redis.sentinel import Sentinel
from typing_extensions import Literal

from bkmonitor.utils.common_utils import ignored

logger = logging.getLogger(__name__)


class Singleton(object):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls._instance, cls):
            cls._instance = object.__new__(cls, *args, **kwargs)
        return cls._instance


class RedisClient(Singleton):
    def __init__(self):
        self.client = redis.StrictRedis(
            host=settings.DJANGO_REDIS_HOST,
            port=settings.DJANGO_REDIS_PORT,
            password=settings.DJANGO_REDIS_PASSWORD,
            db=settings.DJANGO_REDIS_DB,
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


class Redis2Mysql(Singleton):
    @staticmethod
    def get_key(key, member):
        return key + "-" + member

    @staticmethod
    def get_member(key):
        return key.split("-")[1]

    def get_dict_by_key(self, key):
        from monitor.models import GlobalConfig

        objs = GlobalConfig.objects.filter(key__startswith=key)
        result = {}
        for obj in objs:
            result[self.get_member(obj.key)] = obj.value
        return result

    def zscore(self, key, member):
        from monitor.models import GlobalConfig

        # 如果找不到指定key对应的value 则返回None
        try:
            result = GlobalConfig.objects.get(key=self.get_key(key, member)).value
            return result.encode("utf8")
        except Exception:
            return None

    def zadd(self, key, mapping):
        from monitor.models import GlobalConfig

        with ignored(Exception):
            # 不存在则新建
            for member, score in mapping.items():
                obj, result = GlobalConfig.objects.get_or_create(key=self.get_key(key, member))
                obj.value = score
                obj.save()

    def zrem(self, key, members):
        from monitor.models import GlobalConfig

        with ignored(Exception):
            # zrem方法可一次性剔除多个member
            for member in members:
                GlobalConfig.objects.get(key=self.get_key(key, member)).delete()

    def zrange(self, key, start, end, withscores=True):
        with ignored(Exception):
            # 如果找不到指定key对应的value 则返回None
            _data = self.get_dict_by_key(key)
            sorted_data = sorted(list(_data.items()), key=lambda d: d[1])
            # start = 0 & end = -1  返回全部
            slice_data = sorted_data if ((start == 0) and (end == -1)) else sorted_data[start : end + 1]
            # if withscores = True 则连同score值一起返回，反之只返回member
            if withscores:
                return slice_data
            else:
                return [data[0] for data in slice_data]

    def zrevrangebyscore(self, key, max, min, withscores=False):
        with ignored(Exception):
            # 如果找不到指定key对应的value 则返回None
            _data = self.get_dict_by_key(key)

            result = [(k, v) for k, v in list(_data.items()) if max >= v >= min]
            result = sorted(result, key=lambda d: d[1], reverse=True)

            return result if withscores else [i[0] for i in result]

    def hset(self, key, field, value):
        self.zadd(key, {field: value})

    def hget(self, key, field):
        return self.zscore(key, field)


if settings.USE_DJANGO_CACHE_REDIS:
    redis_cli = RedisClient()
else:
    redis_cli = Redis2Mysql()
