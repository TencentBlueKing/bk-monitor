"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json

from django.conf import settings
from django.core.cache import caches
from django.utils.functional import empty

from bkmonitor.utils.cache import InstanceCache


locmem_cache = None
redis_cache = None

# 初始化 locmem 缓存（内存缓存，第一层）
try:
    if "locmem" in settings.CACHES:
        locmem_cache = caches["locmem"]
except (KeyError, Exception):
    pass

# 初始化 redis 缓存（第二层）
try:
    if "redis" in settings.CACHES:
        redis_cache = caches["redis"]
except (KeyError, Exception):
    pass

# 如果 locmem 不可用，使用 InstanceCache 作为内存缓存
if locmem_cache is None:
    locmem_cache = InstanceCache()


class DynamicSettings:
    __cache_expires__ = 180
    __name_list__ = set()

    def __init__(self, wrapped, global_config_model):
        self._wrapped = wrapped
        self._global_config_model = global_config_model

        from bkmonitor.define import global_config

        self.__name_list__ = set(global_config.GLOBAL_CONFIGS)
        self.has_redis_cache = redis_cache is not None

    @property
    def _locmem_cache(self):
        """第一层缓存：内存缓存（locmem）"""
        return locmem_cache

    @property
    def _redis_cache(self):
        """第二层缓存：Redis 缓存"""
        return redis_cache if self.has_redis_cache else None

    def serialize(self, value):
        """序列化值（仅用于 Redis）"""
        return json.dumps(value)

    def deserialize(self, value):
        """反序列化值（仅用于 Redis）"""
        return json.loads(value)

    def __getattr__(self, name):
        value = getattr(self._wrapped, name)
        if name not in self.__name_list__:
            return value

        locmem = self._locmem_cache
        redis = self._redis_cache

        # 第一层：从 locmem 缓存获取
        if locmem and locmem.has_key(name):
            value = locmem.get(name)
            if value is not None:
                return value

        # 第二层：从 redis 缓存获取
        if redis and redis.has_key(name):
            value = redis.get(name)
            if value is not None:
                # 反序列化并回填到 locmem 缓存
                deserialized_value = self.deserialize(value)
                if locmem:
                    locmem.set(name, deserialized_value, self.__cache_expires__)
                return deserialized_value

        # 第三层：从数据库获取
        value = self._global_config_model.get(name, value)

        # 同时写入两层缓存
        if locmem:
            locmem.set(name, value, self.__cache_expires__)
        if redis:
            redis.set(name, self.serialize(value), self.__cache_expires__)

        return value

    def __setattr__(self, name, value):
        if name in self.__name_list__:
            self._global_config_model.set(name, value)
            # 同时删除两层缓存
            locmem = self._locmem_cache
            redis = self._redis_cache
            if locmem:
                locmem.delete(name)
            if redis:
                redis.delete(name)
        elif name.isupper():
            setattr(self._wrapped, name, value)
        else:
            super().__setattr__(name, value)

    def __delattr__(self, name):
        # 从缓存中删除
        locmem = self._locmem_cache
        redis = self._redis_cache
        if locmem:
            locmem.delete(name)
        if redis:
            redis.delete(name)

        # 从名称列表中移除
        self.__name_list__.discard(name)

        # 从包装的对象中删除属性
        if hasattr(self._wrapped, name):
            delattr(self._wrapped, name)

    def __dir__(self):
        return dir(self._wrapped)


def hack_settings(global_config_model, settings_=None):
    if not settings.USE_DYNAMIC_SETTINGS:
        # 不启动动态配置
        return
    from django.conf import LazySettings

    LazySettings.__getattr__ = lazy__getattr__
    settings_ = settings_ or settings
    wrapped = settings_._wrapped
    settings_._wrapped = DynamicSettings(wrapped, global_config_model)  # type: ignore[assignment]


def lazy__getattr__(self, name):
    """
    Return the value of a setting and cache it in self.__dict__.
    """
    if self._wrapped is empty:
        self._setup(name)
    val = getattr(self._wrapped, name)
    if name not in self._wrapped.__name_list__:
        self.__dict__[name] = val
    return val
