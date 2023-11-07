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


import functools
import time
from contextlib import contextmanager

from alarm_backends.core.cluster import get_cluster
from alarm_backends.core.lock import MultiRedisLock, RedisLock
from alarm_backends.core.storage.redis import Cache
from core.errors.alarm_backends import LockError


@contextmanager
def service_lock(key_instance, **kwargs):
    lock = None
    lock_key = key_instance.get_key(**kwargs)
    try:
        lock = RedisLock(lock_key, key_instance.ttl)
        if lock.acquire(0.1):
            yield lock
        else:
            raise LockError(msg="{} is already locked".format(lock_key))
    except LockError as err:
        raise err

    finally:
        if lock is not None:
            lock.release()


@contextmanager
def multi_service_lock(key_instance, keys):
    lock = None
    try:
        lock = MultiRedisLock(keys, key_instance.ttl)
        lock.acquire()
        yield lock
    finally:
        if lock is not None:
            lock.release()


def share_lock(ttl=600, identify=None):
    def wrapper(func):
        @functools.wraps(func)
        def _inner(*args, **kwargs):
            token = str(time.time())
            # 防止函数重名导致方法失效，增加一个ID参数，可以通过ID参数屏蔽多模块函数名重复的问题
            # 例如，可以为`${module}_${method_used_for}`
            name = func.__name__ if identify is None else identify
            cache_key = f"{get_cluster().name}_celery_lock_{name}"
            client = Cache("cache")
            lock_success = client.set(cache_key, token, ex=ttl, nx=True)
            if not lock_success:
                return

            try:
                return func(*args, **kwargs)
            finally:
                if client.get(cache_key) == token:
                    client.delete(cache_key)

        return _inner

    return wrapper
