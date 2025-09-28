"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import time

from alarm_backends.constants import CONST_MINUTES
from alarm_backends.core.storage.redis import Cache
from bkmonitor.utils.common_utils import uniqid4


class BaseLock:
    def __init__(self, name, ttl=None):
        self.name = name
        # 默认60秒过期
        self.ttl = ttl or CONST_MINUTES

    def acquire(self, _wait=None):
        raise NotImplementedError

    def release(self):
        raise NotImplementedError

    def __exit__(self, t, v, tb):
        self.release()

    def __enter__(self):
        self.acquire()
        return self


class RedisLock(BaseLock):
    __token = None

    def __init__(self, name, ttl=None):
        super().__init__(name, ttl)
        self.client = Cache("service-lock")

    def acquire(self, _wait=0.001):
        token = uniqid4()
        wait_until = time.time() + _wait
        while not self.client.set(self.name, token, ex=self.ttl, nx=True):
            if time.time() < wait_until:
                time.sleep(0.01)
            else:
                return False

        self.__token = token
        return True

    def release(self):
        if not self.__token:
            return False
        token = self.client.get(self.name)
        if not token or token != self.__token:
            return False
        return self.client.delete(self.name)


class MultiRedisLock:
    """
    Redis 批量锁
    """

    def __init__(self, keys: list[str], ttl: int = None):
        self.keys = keys
        self.ttl = ttl or CONST_MINUTES
        self.client = Cache("service-lock")
        self._token = uniqid4()
        self._lock_success_keys = set()

    def acquire(self):
        if not self.keys:
            return []

        keys = list(set(self.keys))

        pipeline = self.client.pipeline(transaction=False)
        for key in keys:
            pipeline.set(key, self._token, ex=self.ttl, nx=True)

        results = pipeline.execute()

        for index, locked in enumerate(results):
            if locked:
                self._lock_success_keys.add(keys[index])

        return self._lock_success_keys

    def release(self):
        if not self._lock_success_keys:
            return

        lock_success_keys = list(self._lock_success_keys)

        results = self.client.mget(lock_success_keys)

        keys_to_delete = []

        for index, token in enumerate(results):
            if token == self._token:
                # 只有当token跟当前实例一致的key才能被删除
                keys_to_delete.append(lock_success_keys[index])

        if keys_to_delete:
            self.client.delete(*keys_to_delete)
        return keys_to_delete

    def is_locked(self, key: str):
        """
        查询某个key是否已经获得锁
        """
        return key in self._lock_success_keys
