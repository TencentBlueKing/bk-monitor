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
import time

from consul import NotFound
from django.utils.functional import cached_property
from six.moves import map

from alarm_backends.management.base.protocol import AbstractServiceDiscoveryMixin
from bkmonitor.utils import consul


class ConsulServiceDiscoveryMixin(AbstractServiceDiscoveryMixin):

    # status
    __SESSION_ID__ = None

    # options
    _PATH_PREFIX_ = None
    _SESSION_TTL_ = 120

    def __init__(self, *args, **kwargs):
        super(ConsulServiceDiscoveryMixin, self).__init__(*args, **kwargs)
        self.last_renew_session_time = 0

    @cached_property
    def _client(self):
        return consul.BKConsul()

    @cached_property
    def _registration_path(self):
        return "/".join(map(str, [self._PATH_PREFIX_, self.host_addr, self.pid]))

    @property
    def _registry(self):
        _, node_list = self._client.kv.get(self._PATH_PREFIX_, keys=True)
        node_list = node_list or {}

        registry = {}
        for node in node_list:
            host_addr, pid = node[len(self._PATH_PREFIX_) + 1 :].split("/")
            registry.setdefault(host_addr, []).append(pid)

        return registry

    def _renew_or_create_session_id(self):
        session = consul.BKConsul.Session(self._client.agent.agent)

        if self.__SESSION_ID__:
            try:
                session.renew(self.__SESSION_ID__)
            except NotFound:
                self.__SESSION_ID__ = None

        if self.__SESSION_ID__ is None:
            self.__SESSION_ID__ = session.create(behavior="delete", lock_delay=0, ttl=self._SESSION_TTL_)

        return self.__SESSION_ID__

    def get_registration_info(self, registration_path=None):
        if registration_path is None:
            registration_path = self._registration_path

        _, result = self._client.kv.get(registration_path)

        if result:
            return json.loads(result["Value"])

    def update_registration_info(self, value=None):
        now = time.time()
        if now - self.last_renew_session_time < self._SESSION_TTL_ / 2:
            return
        self.last_renew_session_time = now

        try:
            info = json.dumps(value)
        except:  # noqa
            info = b""

        session_id = self._renew_or_create_session_id()
        assert session_id, "session_id should not be {!r}".format(type(session_id))

        self._client.kv.put(self._registration_path, info, acquire=session_id)

    def register(self, registration_info=None):
        self.update_registration_info(registration_info)

    def unregister(self):
        if self.__SESSION_ID__:
            self._client.session.destroy(self.__SESSION_ID__)

    def query_for_hosts(self):
        return list(self._registry.keys())

    def query_for_instances(self, host_addr=None):
        if host_addr is None:
            host_addr = self.host_addr

        registry = dict(self._registry)
        return (list(registry.keys()), ["{}/{}".format(host_addr, pid) for pid in registry.get(host_addr, [])])
