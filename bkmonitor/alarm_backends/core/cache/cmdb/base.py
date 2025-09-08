# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


import abc
import json
import time

import six.moves.cPickle as pickle
from django.core.cache import caches

from alarm_backends.constants import CONST_ONE_DAY
from alarm_backends.core.cache.base import CacheManager
from alarm_backends.core.storage.redis import Cache
from core.drf_resource import api
from core.prometheus import metrics

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


class RefreshByBizMixin(object):
    @classmethod
    def get_biz_cache_key(cls):
        return "{}.biz".format(cls.CACHE_KEY)

    @classmethod
    @abc.abstractmethod
    def refresh_by_biz(cls, bk_biz_id):
        """
        按业务获取对象信息，由子类补全
        :param bk_biz_id: 业务ID
        :return: {"cache_key": obj}
        """
        raise NotImplementedError

    @classmethod
    def refresh(cls):
        """
        刷新缓存
        """
        from alarm_backends.core.i18n import i18n

        cls.logger.info("refresh CMDB data started.")

        start_time = time.time()
        business_list = api.cmdb.get_business()

        if not business_list:
            return

        biz_ids = [business.bk_biz_id for business in business_list]

        biz_cache_key = cls.get_biz_cache_key()

        for bk_biz_id in biz_ids:
            biz_start_time = time.time()
            exc = None
            try:
                i18n.set_biz(bk_biz_id)
                objs = cls.refresh_by_biz(bk_biz_id)
            except Exception as e:
                # 如果接口调用异常，则不更新
                cls.logger.exception("get data by biz fail, bk_biz_id: {}, {}".format(bk_biz_id, e))
                exc = e
            else:
                # 更新对象缓存
                cls.cache_by_biz(bk_biz_id, objs, force=True)

            metrics.ALARM_CACHE_TASK_TIME.labels(str(bk_biz_id), cls.type, str(exc)).observe(
                time.time() - biz_start_time
            )

        old_biz_ids = set(cls.cache.hkeys(biz_cache_key))
        new_biz_ids = {str(biz_id) for biz_id in biz_ids}
        deleted_biz_ids = old_biz_ids - new_biz_ids
        if deleted_biz_ids:
            cls.cache.hdel(biz_cache_key, *deleted_biz_ids)
        cls.cache.expire(biz_cache_key, cls.CACHE_TIMEOUT)

        # 清理已被删除的业务数据
        biz_cache_keys = cls.cache.hgetall(biz_cache_key) or {}
        # biz_cache_key 存储的就是最新的Keys列表，在后面与old keys做差量比对
        # 存储结构
        # {
        #   '2': ['127.0.0.1|0', '127.0.0.2|0'],
        #   '3': ['127.0.0.3|0'],
        # }
        new_keys = []
        for keys in list(biz_cache_keys.values()):
            new_keys.extend(json.loads(keys))

        # 清理业务下已被删除的对象数据
        # hkeys 已经删除的key，依然会在大hash map中。 因此需要清理
        old_keys = cls.cache.hkeys(cls.CACHE_KEY)
        deleted_keys = set(old_keys) - set(new_keys)
        if deleted_keys:
            cls.cache.hdel(cls.CACHE_KEY, *deleted_keys)
        cls.cache.expire(cls.CACHE_KEY, cls.CACHE_TIMEOUT)

        metrics.ALARM_CACHE_TASK_TIME.labels("0", cls.type, "None").observe(time.time() - start_time)

        cls.logger.info(
            "cache_key({}) refresh CMDB data finished, amount: updated: {}, removed: {}, "
            "removed_biz: {}".format(cls.CACHE_KEY, len(new_keys), len(deleted_keys), len(deleted_biz_ids))
        )

    @classmethod
    def cache_by_biz(cls, bk_biz_id: str, objs_dict: dict, force: bool = False) -> None:
        if not force:
            if not cls.can_cache(bk_biz_id):
                return

        # 更新对象缓存
        pipeline = cls.cache.pipeline()
        batch_objs = {}
        key_list = []
        for index, key in enumerate(objs_dict):
            batch_objs[key] = cls.serialize(objs_dict[key])
            key_list.append(key)
            if (index + 1) % 1000 == 0:
                cls.cache.hmset(cls.CACHE_KEY, batch_objs)
                batch_objs = {}
        if batch_objs:
            cls.cache.hmset(cls.CACHE_KEY, batch_objs)

        pipeline.expire(cls.CACHE_KEY, cls.CACHE_TIMEOUT)
        # 按业务设置key列表，用于差量更新
        pipeline.hset(cls.get_biz_cache_key(), str(bk_biz_id), json.dumps(key_list))
        pipeline.execute()

    @classmethod
    def can_cache(cls, bk_biz_id: str) -> bool:
        return bool(cls.cache.set(f"{cls.CACHE_KEY}.{bk_biz_id}.updated", int(time.time()), nx=True, ex=60))

    @classmethod
    def clear(cls):
        """
        清理缓存
        """
        cls.cache.delete(cls.CACHE_KEY, cls.get_biz_cache_key())
