"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import abc
import json
import pickle

from django.core.cache import caches

from alarm_backends.constants import CONST_ONE_DAY
from alarm_backends.core.cache.base import CacheManager
from alarm_backends.core.storage.redis import Cache

mem_cache = caches["locmem"]


class CMDBCacheManager(CacheManager):
    """
    CMDB 缓存管理基类
    """

    type = "cmdb"
    CACHE_KEY = ""
    CACHE_TIMEOUT = 7 * CONST_ONE_DAY
    ObjectClass = None
    cache = Cache("cache-cmdb")

    @classmethod
    def serialize(cls, obj):
        """
        序列化数据
        """
        return pickle.dumps(obj).decode("latin1")

    @classmethod
    def deserialize(cls, string):
        """
        反序列化数据
        """
        if cls.ObjectClass and string.startswith("{"):
            return cls.ObjectClass(**json.loads(string))
        return pickle.loads(string.encode("latin1"))

    @classmethod
    @abc.abstractmethod
    def key_to_internal_value(cls, *args, **kwargs):
        """
        生成用于存储的key
        """
        raise NotImplementedError

    @classmethod
    def key_to_representation(cls, origin_key):
        """
        取出key时进行转化
        """
        return origin_key

    @classmethod
    def multi_get(cls, keys):
        """
        获取多个对象，生成列表
        :param list keys: cache key
        :return: list
        """
        if not keys:
            return []
        keys = list(keys)

        objs = cls.cache.hmget(cls.CACHE_KEY, keys)
        result = []
        for obj in objs:
            if obj:
                result.append(cls.deserialize(obj))
            else:
                result.append(None)
        return result

    @classmethod
    def get(cls, *args, **kwargs):
        """
        获取单个对象
        """
        key = cls.key_to_internal_value(*args, **kwargs)
        local_key = f"{cls.CACHE_KEY}_{key}"
        if local_key in mem_cache:
            return mem_cache.get(local_key)

        obj = cls.cache.hget(cls.CACHE_KEY, key)

        if not obj:
            cls.logger.warning("unknown {}: {}".format(cls.__name__.replace("Manager", ""), key))
        else:
            obj = cls.deserialize(obj)
        mem_cache.set(local_key, obj)
        return obj

    @classmethod
    def multi_get_with_dict(cls, keys):
        """
        获取多个对象，生成Key的字典
        """
        if not keys:
            return {}
        keys = list(keys)

        objs = cls.multi_get(keys)

        result = {}
        for index, obj in enumerate(objs):
            if not obj:
                result[keys[index]] = None
            else:
                result[keys[index]] = obj

        return result

    @classmethod
    def keys(cls):
        keys = cls.cache.hkeys(cls.CACHE_KEY)
        return [cls.key_to_representation(key) for key in keys]

    @classmethod
    def all(cls):
        """
        获取缓存列表
        """
        origin_obj_list = cls.cache.hgetall(cls.CACHE_KEY) or {}
        obj_list = []
        for obj in list(origin_obj_list.values()):
            obj_list.append(cls.deserialize(obj))
        return obj_list

    @classmethod
    @abc.abstractmethod
    def refresh(cls):
        """
        刷新缓存
        """
        raise NotImplementedError

    @classmethod
    def clear(cls):
        """
        清理缓存
        """
        cls.cache.delete(cls.CACHE_KEY)
