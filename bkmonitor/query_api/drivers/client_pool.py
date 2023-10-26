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


from collections import OrderedDict

import six

try:
    from threading import RLock
except ImportError:  # Platform-specific: No threads available

    class RLock:
        def __enter__(self):
            pass

        def __exit__(self, exc_type, exc_value, traceback):
            pass


class BaseClientFactory(object):
    def client_key(self, **request_context):
        raise NotImplementedError

    def new_client(self, **request_context):
        raise NotImplementedError

    @staticmethod
    def client_close_fn(client):
        if hasattr(client, "close"):
            client.close()


class ClientPoolManage(object):
    def __init__(self, client_factory, max_poll_size=10):
        self.max_poll_size = max_poll_size
        self.client_factory = client_factory
        self.lock = RLock()
        self.__client_pool = OrderedDict()

    def get_client(self, **context):
        client_id = self.client_factory.client_key(**context)
        if client_id in self.__client_pool:
            if self.is_full:
                client = self._refresh_client(client_id)
                if client is not None:
                    return client
                return self._create_client(client_id, context)

            return self.__client_pool[client_id]

        return self._create_client(client_id, context)

    def _create_client(self, client_id, context):
        with self.lock:
            while self.is_full:
                client_key_to_del = next(six.iterkeys(self.__client_pool))
                self._on_delete_client(self.__client_pool[client_key_to_del])
                del self.__client_pool[client_key_to_del]

            self.__client_pool[client_id] = self.client_factory.new_client(**context)

        return self.__client_pool[client_id]

    def _refresh_client(self, client_id):
        with self.lock:
            if client_id in self.__client_pool:
                client = self.__client_pool.pop(client_id)
                self.__client_pool[client_id] = client
                self._on_delete_client(client)
                return client
        return None

    def _on_delete_client(self, client):
        self.client_factory.client_close_fn(client)

    @property
    def size(self):
        return len(self.__client_pool)

    @property
    def is_full(self):
        return self.size >= self.max_poll_size
