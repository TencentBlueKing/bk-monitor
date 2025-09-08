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


import json
import logging
import os
import random
import sys
import time
import uuid

import redis
from django.conf import settings
from kombu.utils.url import parse_url
from redis.exceptions import ConnectionError
from redis.sentinel import Sentinel
from six.moves import map, range

from bkmonitor.utils.cache import InstanceCache

logger = logging.getLogger("core.storage.redis")


"""
redis中的db分配[7，8，9，10]，共4个db
[不重要，可清理, db:7] 日志相关数据使用log配置
[一般，可清理, db:8] 配置相关缓存使用cache配置，例如：cmdb的数据、策略、屏蔽等配置数据
[重要，不可清理, db:9] 各个services之间交互的队列，使用queue配置
[重要，不可清理, db:9] celery的broker，使用celery配置
[重要，不可清理, db:10] service自身的数据，使用service配置
"""


class CacheBackendType(object):
    CELERY = "celery"
    SERVICE = "service"
    QUEUE = "queue"
    CACHE = "cache"
    LOG = "log"


CACHE_BACKEND_CONF_MAP = {
    CacheBackendType.CELERY: settings.REDIS_CELERY_CONF,
    CacheBackendType.SERVICE: settings.REDIS_SERVICE_CONF,
    CacheBackendType.QUEUE: settings.REDIS_QUEUE_CONF,
    CacheBackendType.CACHE: settings.REDIS_CACHE_CONF,
    CacheBackendType.LOG: settings.REDIS_LOG_CONF,
}


def cache_conf_with_router(router_id):
    """
    基于模块的路由
    cache-cmdb: os.getenv("REDIS_CACHE_CMDB_URL")
    cache-strategy: os.getenv("REDIS_CACHE_STRATEGY_URL")
    """
    # 环境变量名模板
    env_tpl = "REDIS_CACHE_{mod}_URL"
    # 路由id格式: 模块-子模块
    mods = router_id.split("-", 1)
    if len(mods) == 1:
        return None
    router_module, sub_mod = mods
    if router_module not in CACHE_BACKEND_CONF_MAP:
        return None
    conf = CACHE_BACKEND_CONF_MAP[router_module]
    env_conf_name = env_tpl.format(mod=sub_mod.upper())
    url = os.getenv(env_conf_name)
    if not url:
        return conf
    # 解析 redis 连接url
    # {'transport': 'redis',
    #  'hostname': '127.0.0.1',
    #  'port': 6379,
    #  'userid': None,
    #  'password': 'admin',
    #  'virtual_host': '0'}
    parts = parse_url(url)
    parts["_cache_type"] = parts.pop("transport")
    parts["host"] = parts.pop("hostname")
    parts["db"] = conf["db"]
    # sentinel 特性
    # sentinel://{master_name}:{redis_pwd}@{sentinel_host}:{sentinel_port}/{sentinel_pwd}
    parts["sentinel_password"] = parts.pop("virtual_host")
    parts["master_name"] = parts.pop("userid")
    return parts


class BaseRedisCache(object):
    def __init__(self, redis_class=None):
        self.redis_class = redis_class or redis.Redis
        self._instance = None
        self._readonly_instance = None
        self.refresh_time = 0
        self.refresh_instance()

    @classmethod
    def instance(cls, backend, conf=None):
        """
        创建或获取缓存实例。

        该函数旨在为给定的后端名称提供一个缓存实例。它首先检查是否已经为该后端创建了一个实例，
        如果没有，它将尝试基于提供的配置或环境变量生成一个实例。

        :param cls: 请求实例化的类。
        :param backend: 字符串，表示缓存后端的名称。
        :param conf: 可选参数，用于为后端提供特定的配置。
        :return:
        """
        # 构建实例属性名称，以避免直接属性访问的不透明度
        _instance = "_%s_instance" % backend

        # 检查是否已经为给定的后端创建了实例,如果创建了直接返回，所以这是一个单例模式
        # 相当于它变成了一个全局的redis工具类
        if not hasattr(cls, _instance):
            # 如果提供了特定的配置，使用它来创建实例
            if conf is not None:
                ins = cls(conf)
                setattr(cls, _instance, ins)
            # 尝试从预定义的映射中获取配置
            elif backend in CACHE_BACKEND_CONF_MAP:
                ins = cls(CACHE_BACKEND_CONF_MAP[backend])
                setattr(cls, _instance, ins)
            else:
                # 尝试从cache_conf_with_router获取config配置，backend格式需要为“[type]-xxx”
                # type 需要被定义在 CACHE_BACKEND_CONF_MAP中，否则config为None
                config = cache_conf_with_router(backend)
                if config is not None:
                    setattr(cls, _instance, Cache.__new__(Cache, backend, config))
                else:
                    raise Exception("unknown redis backend %s" % backend)

        return getattr(cls, _instance)

    @property
    def readonly_instance(self):
        return self._readonly_instance

    def create_instance(self):
        raise NotImplementedError()

    def close_instance(self, instance=None):
        raise NotImplementedError()

    def refresh_instance(self):
        """
        刷新实例。

        此方法旨在关闭当前实例和只读实例（如果已存在），并尝试重新创建新的实例。
        它尝试最多三次创建新实例，如果成功，则更新最后刷新时间。
        """
        # 如果当前实例不为空，则关闭当前实例和只读实例
        if self._instance is not None:
            self.close_instance(self._instance)
            self.close_instance(self._readonly_instance)

        # 尝试最多三次创建新的实例和只读实例
        for _ in range(3):
            try:
                # 成功创建实例后，更新刷新时间，并退出循环
                self._instance, self._readonly_instance = self.create_instance()
                self.refresh_time = time.time()
                break
            # 捕获异常并记录日志
            except Exception as err:
                logger.exception(err)

    def __getattr__(self, name):
        # 从_instance中获取到熟悉，这里的command对应的就是redis中的各种命令，比如set命令
        command = getattr(self._instance, name)

        # 对command进行再包装，然后返回
        def handle(*args, **kwargs):
            exception = None
            for _ in range(3):
                try:
                    return command(*args, **kwargs)
                except ConnectionError as err:
                    exception = err
                    self.refresh_instance()
                except Exception as err:
                    raise err
            if exception:
                raise exception

        return handle

    def delay(self, cmd, queue, *values, **option):
        """
        延时推入队列
        :param cmd:  lpush or rpush
        :param queue: queue name
        :param values: values
        :param option: {'delay':1, 'task_id'}
        :return:

        ex:
        r.delay('rpush', 'queue_name', 'value1', 'value2', ... , delay=1)
        """
        delay = option.get("delay", 0)
        if delay < 0:
            delay = 0
        score = time.time() + delay
        task_id = option.get("task_id", str(uuid.uuid4()))

        message = json.dumps([task_id, cmd, queue, values, score])

        from alarm_backends.core.cache.delay_queue import DelayQueueManager

        self.hset(DelayQueueManager.TASK_STORAGE_QUEUE, task_id, message)
        self.zadd(DelayQueueManager.TASK_DELAY_QUEUE, {task_id: score})


class RedisCache(BaseRedisCache):
    """ """

    def __init__(self, redis_conf, redis_class=None, decode_responses=True):
        redis_conf.pop("master_name", None)
        redis_conf.pop("sentinel_password", None)

        self.redis_conf = redis_conf
        if decode_responses:
            # 插入默认参数
            self.redis_conf.update({"decode_responses": True, "encoding": "utf-8"})
        super(RedisCache, self).__init__(redis_class)

    def create_instance(self):
        client = self.redis_class(**self.redis_conf)
        return client, client

    def close_instance(self, instance=None):
        if instance:
            instance.connection_pool.disconnect()


class SentinelRedisCache(BaseRedisCache):
    SOCKET_TIMEOUT = getattr(settings, "REDIS_SOCKET_TIMEOUT", 60)
    MASTER_NAME = getattr(settings, "REDIS_MASTER_NAME", "mymaster")
    SENTINEL_PASS = getattr(settings, "REDIS_SENTINEL_PASS", "")

    def __init__(self, conf, redis_class=None, decode_responses=True):
        redis_conf = conf.copy()
        self.sentinel_host = redis_conf.pop("host")
        self.sentinel_port = redis_conf.pop("port")
        self.socket_timeout = int(redis_conf.pop("socket_timeout", self.SOCKET_TIMEOUT))
        self.master_name = redis_conf.pop("master_name", self.MASTER_NAME)
        self.cache_mode = redis_conf.pop("cache_mode", "master")
        self.SENTINEL_PASS = redis_conf.pop("sentinel_password", "") or self.SENTINEL_PASS
        self.redis_conf = redis_conf
        # 插入默认参数
        if decode_responses:
            self.redis_conf.update({"decode_responses": True, "encoding": "utf-8"})
        super(SentinelRedisCache, self).__init__(redis_class)

    def create_instance(self):
        sentinel_kwargs = {
            "socket_connect_timeout": self.socket_timeout,
        }
        if self.SENTINEL_PASS:
            sentinel_kwargs["password"] = self.SENTINEL_PASS

        # sentinel host支持多个sentinel节点，以分号分隔
        sentinel_hosts = self.sentinel_host.split(";")
        # 随机打乱顺序，避免每次都是同一个节点
        random.shuffle(sentinel_hosts)
        redis_sentinel = Sentinel(
            [(h, self.sentinel_port) for h in sentinel_hosts if h],
            sentinel_kwargs=sentinel_kwargs,
        )

        redis_instance_config = self.redis_conf
        redis_instance_config["password"] = getattr(settings, "REDIS_PASSWD", "")

        master = redis_sentinel.master_for(self.master_name, redis_class=self.redis_class, **redis_instance_config)
        slave = redis_sentinel.slave_for(self.master_name, redis_class=self.redis_class, **redis_instance_config)
        list(map(self.close_instance, redis_sentinel.sentinels))
        return master, slave

    def close_instance(self, instance=None):
        if instance:
            instance.connection_pool.disconnect()


class Cache(redis.Redis):
    CacheTypes = {
        "redis": RedisCache,
        "RedisCache": RedisCache,
        "SentinelRedisCache": SentinelRedisCache,
        "sentinel": SentinelRedisCache,
        "InstanceCache": InstanceCache,
    }

    # 从settings中获取CACHE_BACKEND_TYPE的值，如果未设置，则默认使用"RedisCache"
    # 这是为了确定缓存后端的类型，根据应用场景的不同可以选择不同的缓存系统
    CacheBackendType = getattr(settings, "CACHE_BACKEND_TYPE", "RedisCache")

    def __new__(cls, backend, connection_conf=None):
        if not backend:
            raise
        # 根据连接配置获取缓存类型设置，如果没有显式设置，则使用类的默认缓存类型
        cache_type = connection_conf and connection_conf.pop("_cache_type", None) or cls.CacheBackendType
        try:
            type_ = cls.CacheTypes[cache_type]
            # 根据不同的缓存类型，创建缓存实例，通过instance类方法获取缓存实例
            return type_.instance(backend, connection_conf)
        except Exception:
            logger.exception("fail to use %s [%s]", backend, " ".join(sys.argv))
            raise

    def __init__(self, backend, connection_conf=None):
        """hack"""
        pass

    def delay(self, cmd, queue, *values, **option):
        """hack"""
        pass
