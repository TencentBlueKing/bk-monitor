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


import json
import logging
import random
import sys
import time
import uuid

import redis
from django.conf import settings
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


class BaseRedisCache(object):
    def __init__(self, redis_class=None):
        self.redis_class = redis_class or redis.Redis
        self._instance = None
        self._readonly_instance = None
        self.refresh_time = 0
        self.refresh_instance()

    @classmethod
    def instance(cls, backend, conf=None):
        _instance = "_%s_instance" % backend
        if not hasattr(cls, _instance):
            if conf is not None:
                ins = cls(conf)
                setattr(cls, _instance, ins)
                return ins

            if backend not in CACHE_BACKEND_CONF_MAP:
                raise Exception("unknown redis backend %s" % backend)
            ins = cls(CACHE_BACKEND_CONF_MAP[backend])
            setattr(cls, _instance, ins)
        return getattr(cls, _instance)

    @property
    def readonly_instance(self):
        return self._readonly_instance

    def create_instance(self):
        raise NotImplementedError()

    def close_instance(self, instance=None):
        raise NotImplementedError()

    def refresh_instance(self):
        if self._instance is not None:
            self.close_instance(self._instance)
            self.close_instance(self._readonly_instance)

        for _ in range(3):
            try:
                self._instance, self._readonly_instance = self.create_instance()
                self.refresh_time = time.time()
                break
            except Exception as err:
                logger.exception(err)

    def __getattr__(self, name):
        command = getattr(self._instance, name)

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
        "RedisCache": RedisCache,
        "SentinelRedisCache": SentinelRedisCache,
        "InstanceCache": InstanceCache,
    }

    CacheBackendType = getattr(settings, "CACHE_BACKEND_TYPE", "RedisCache")
    CacheDefaultType = getattr(settings, "CACHE_DEFAULT_TYPE", "InstanceCache")

    def __new__(cls, backend, connection_conf=None):
        if not backend:
            raise
        cache_type = connection_conf and connection_conf.pop("_cache_type") or cls.CacheBackendType
        try:
            type_ = cls.CacheTypes[cache_type]
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
