"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import functools
import json
import logging
import time
import zlib
from time import monotonic
from typing import Any
from collections.abc import Callable

from django.conf import settings
from django.core.cache import cache, caches
from django.utils import translation
from django.utils.encoding import force_bytes

from bkmonitor.utils.common_utils import count_md5
from bkmonitor.utils.local import local
from bkmonitor.utils.request import get_request

logger = logging.getLogger(__name__)


try:
    mem_cache = caches["locmem"]
except Exception:
    mem_cache = cache


class UsingCache:
    min_length = 15
    preset = 6
    key_prefix = "web_cache"

    def __init__(
        self,
        cache_type,
        backend_cache_type=None,
        user_related=None,
        compress=True,
        is_cache_func=lambda res: True,
        func_key_generator=lambda func: f"{func.__module__}.{func.__name__}",
    ):
        """
        :param cache_type: 缓存类型
        :param user_related: 是否与用户关联
        :param compress: 是否进行压缩
        :param is_cache_func: 缓存函数，当函数返回true时，则进行缓存
        :param func_key_generator: 函数标识key的生成逻辑
        """
        self.cache_type = cache_type
        self.backend_cache_type = backend_cache_type
        self.compress = compress
        self.is_cache_func = is_cache_func
        self.func_key_generator = func_key_generator
        # 先看用户是否提供了user_related参数
        # 若无，则查看cache_type是否提供了user_related参数
        # 若都没有定义，则user_related默认为True
        if user_related is not None:
            self.user_related = user_related
        elif getattr(cache_type, "user_related", None) is not None:
            self.user_related = self.cache_type.user_related
        else:
            self.user_related = True

        self.using_cache_type = self._get_using_cache_type()
        self.local_cache_enable = settings.ROLE == "web"

    def _get_username(self):
        username = "backend"
        if self.user_related:
            try:
                username = get_request().user.username
            except Exception:
                username = "backend"
        return username

    def _get_using_cache_type(self):
        using_cache_type = self.cache_type
        if self._get_username() == "backend":
            using_cache_type = self.backend_cache_type or self.cache_type
        if using_cache_type:
            if not isinstance(using_cache_type, CacheTypeItem):
                raise TypeError("param 'cache_type' must be aninstance of <utils.cache.CacheTypeItem>")
        return using_cache_type

    def _cache_key(self, task_definition, args, kwargs):
        # 新增根据用户openid设置缓存key
        lang = "en" if translation.get_language() == "en" else "zh-hans"
        if self.using_cache_type:
            return f"{self.key_prefix}:{self.using_cache_type.key}:{self.func_key_generator(task_definition)}:{count_md5(args)},{count_md5(kwargs)}[{self._get_username()}]{lang}"
        return None

    def get_value(self, cache_key, default=None):
        """
        新增一级内存缓存（local）。在同一个请求(线程)中，优先使用内存缓存。
        一级缓存： local（web服务单次请求中生效）
        二级缓存： cache（60s生效）
        机制：
        local (miss), cache(miss): cache <- result
        local (miss), cache(hit): local <- result
        """
        if self.local_cache_enable:
            value = getattr(local, cache_key, None)
            if value:
                return json.loads(value)

        value = mem_cache.get(cache_key, default=None) or cache.get(cache_key, default=None)
        if value is None:
            return default
        if self.compress:
            try:
                value = zlib.decompress(value)
            except Exception:
                pass
            try:
                value = json.loads(force_bytes(value))
            except Exception:
                value = default
        if value and self.local_cache_enable:
            setattr(local, cache_key, json.dumps(value))
        return value

    def set_value(self, key, value, timeout=60):
        if self.compress:
            try:
                value = json.dumps(value)
            except Exception:
                logger.exception(f"[Cache]不支持序列化的类型: {type(value)}")
                return False

            if len(value) > self.min_length:
                value = zlib.compress(value.encode("utf-8"))

        try:
            if mem_cache is not cache:
                mem_cache.set(key, value, 60)
            cache.set(key, value, timeout)
        except Exception as e:
            try:
                request_path = get_request().path
            except Exception:
                request_path = ""
            # 缓存出错不影响主流程
            logger.exception(f"存缓存[key:{key}]时报错：{e}\n value: {value!r}\nurl: {request_path}")

    def _cached(self, task_definition, args, kwargs):
        """
        【默认缓存模式】
        先检查是否缓存是否存在
        若存在，则直接返回缓存内容
        若不存在，则执行函数，并将结果回写到缓存中
        """
        if settings.ENVIRONMENT == "development":
            cache_key = None
        else:
            cache_key = self._cache_key(task_definition, args, kwargs)
        if cache_key:
            return_value = self.get_value(cache_key, default=None)

            if return_value is None:
                return_value = self._refresh(task_definition, args, kwargs)
        else:
            return_value = self._cacheless(task_definition, args, kwargs)
        return return_value

    def _refresh(self, task_definition, args, kwargs):
        """
        【强制刷新模式】
        不使用缓存的数据，将函数执行返回结果回写缓存
        """
        cache_key = self._cache_key(task_definition, args, kwargs)

        return_value = self._cacheless(task_definition, args, kwargs)

        # 设置了缓存空数据
        # 或者不缓存空数据且数据为空时
        # 需要进行缓存
        if self.is_cache_func(return_value):
            self.set_value(cache_key, return_value, self.using_cache_type.timeout)

        return return_value

    def _cacheless(self, task_definition, args, kwargs):
        """
        【忽略缓存模式】
        忽略缓存机制，直接执行函数，返回结果不回写缓存
        """
        # 执行真实函数
        return task_definition(*args, **kwargs)

    def __call__(self, task_definition):
        @functools.wraps(task_definition)
        def cached_wrapper(*args, **kwargs):
            return_value = self._cached(task_definition, args, kwargs)
            return return_value

        @functools.wraps(task_definition)
        def refresh_wrapper(*args, **kwargs):
            return_value = self._refresh(task_definition, args, kwargs)
            return return_value

        @functools.wraps(task_definition)
        def cacheless_wrapper(*args, **kwargs):
            return_value = self._cacheless(task_definition, args, kwargs)
            return return_value

        # 为函数设置各种调用模式
        default_wrapper = cached_wrapper
        default_wrapper.cached = cached_wrapper
        default_wrapper.refresh = refresh_wrapper
        default_wrapper.cacheless = cacheless_wrapper

        return default_wrapper


using_cache = UsingCache


class CacheTypeItem:
    """
    缓存类型定义
    """

    def __init__(self, key, timeout, user_related=None, label=""):
        """
        :param key: 缓存名称
        :param timeout: 缓存超时，单位：s
        :param user_related: 是否用户相关
        :param label: 详细说明
        """
        self.key = key
        self.timeout = timeout
        self.label = label
        self.user_related = user_related

    def __call__(self, timeout):
        return CacheTypeItem(self.key, timeout, self.user_related, self.label)


class CacheType:
    """
    缓存类型选项
    >>>@using_cache(CacheType.DATA(60 * 60))
    >>>@using_cache(CacheType.BIZ)
    """

    BIZ = CacheTypeItem(key="biz", timeout=settings.CACHE_BIZ_TIMEOUT, label="业务及人员相关", user_related=True)

    HOST = CacheTypeItem(key="host", timeout=settings.CACHE_HOST_TIMEOUT, label="主机信息相关", user_related=False)

    CC = CacheTypeItem(key="cc", timeout=settings.CACHE_CC_TIMEOUT, label="CC模块和Set相关", user_related=True)

    DATA = CacheTypeItem(key="data", timeout=settings.CACHE_DATA_TIMEOUT, label="计算平台接口相关", user_related=False)
    OVERVIEW = CacheTypeItem(
        key="overview", timeout=settings.CACHE_OVERVIEW_TIMEOUT, label="首页接口相关", user_related=False
    )
    USER = CacheTypeItem(key="user", timeout=settings.CACHE_USER_TIMEOUT, user_related=False)
    GSE = CacheTypeItem(key="gse", timeout=60 * 5, user_related=False)
    BCS = CacheTypeItem(key="bcs", timeout=60 * 5, user_related=False)
    METADATA = CacheTypeItem(key="metadata", timeout=60 * 10, user_related=False)
    APM = CacheTypeItem(key="apm", timeout=60 * 10, user_related=False)
    APM_EBPF = CacheTypeItem(key="apm_ebpf", timeout=60 * 10, user_related=False)
    APM_ENDPOINTS = CacheTypeItem(key="apm_endpoints", timeout=60 * 10, user_related=False)
    CC_BACKEND = CacheTypeItem(key="cc_backend", timeout=60 * 10, user_related=False)
    LOG_SEARCH = CacheTypeItem(key="log_search", timeout=60 * 5, label="日志平台相关", user_related=False)
    NODE_MAN = CacheTypeItem(key="node_man", timeout=60 * 30, label="节点管理相关", user_related=False)
    # 重要： 此类型表示所有resource调用均大概率命中缓存，因为缓存失效时间较长。缓存刷新由后台周期任务进行
    # 详细参看： from alarm_backends.core.api_cache.library import cmdb_api_list
    # 当出现cmdb数据变更长时间未生效，考虑后台进程缓存任务失败的可能：bk-monitor-alarm-api-cron-worker
    CC_CACHE_ALWAYS = CacheTypeItem(key="cc_cache_always", timeout=60 * 60, user_related=False)
    HOME = CacheTypeItem(key="home", timeout=settings.CACHE_HOME_TIMEOUT, label="自愈统计数据相关", user_related=False)
    DEVOPS = CacheTypeItem(key="devops", timeout=60 * 5, label="蓝盾接口相关", user_related=False)
    GRAFANA = CacheTypeItem(key="grafana", timeout=60 * 5, label="仪表盘相关", user_related=False)
    SCENE_VIEW = CacheTypeItem(key="scene_view", timeout=60 * 1, label="观测场景相关", user_related=False)
    DB_CACHE = CacheTypeItem(key="db_cache", timeout=60 * 3, label="db缓存", user_related=False)


class InstanceCache:
    @classmethod
    def instance(cls, *args, **kwargs):
        if not hasattr(cls, "_instance"):
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.__cache = {}

    def clear(self):
        self.__cache = {}

    def set(self, key, value, timeout=0):
        """
        :param key:
        :param value:
        :param timeout:
        :return:
        """
        if not timeout:
            timeout = 0
        else:
            if not timeout:
                timeout = time.time() + timeout
        self.__cache[key] = (value, timeout)

    def __get_raw(self, key):
        value = self.__cache.get(key)
        if not value:
            return None
        if value[1] and time.time() > value[1]:
            del self.__cache[key]
            return None
        return value

    def has_key(self, key, version=None):
        return self.exists(key)

    def exists(self, key):
        value = self.__get_raw(key)
        return value is not None

    def get(self, key):
        value = self.__get_raw(key)
        return value and value[0]

    def delete(self, key):
        try:
            del self.__cache[key]
        except KeyError:
            pass


def lru_cache_with_ttl(
    maxsize: int = 128, ttl: int = 60, decision_to_drop_func: Callable[[Any], bool] = lambda _: False
):
    """带有过期时间的 LRU Cache
    原理：lru_cache 维护缓存对象的引用，通过包装 Result 注入期望过期时间，达到淘汰过期 Key 的效果。
    :param maxsize: 最大容量
    :param ttl: 过期时间，单位为秒
    :param decision_to_drop_func: 缓存丢弃决策函数
    :return:
    """

    class _Result:
        __slots__ = ("value", "expired")

        def __init__(self, value: Any, expired: int):
            self.value: Any = value
            self.expired: int = expired

    def decorator(func):
        @functools.lru_cache(maxsize=maxsize)
        def cached_func(*args, **kwargs):
            value: Any = func(*args, **kwargs)
            # monotonic 提供了不受系统时间影响的稳定秒数增长基准。
            expired: int = int(monotonic()) + ttl
            return _Result(value, expired)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result: _Result = cached_func(*args, **kwargs)
            if result.expired < monotonic() or decision_to_drop_func(result.value):
                result.value = func(*args, **kwargs)
                result.expired = int(monotonic()) + ttl
            return result.value

        wrapper.cache_clear = cached_func.cache_clear
        return wrapper

    return decorator
