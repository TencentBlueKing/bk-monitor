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


import os
from abc import ABCMeta, abstractmethod

import six
from django.utils.functional import cached_property

from alarm_backends.management.utils import get_host_addr


class AbstractWorker(six.with_metaclass(ABCMeta, object)):
    @cached_property
    def host_addr(self):
        return get_host_addr()

    @cached_property
    def pid(self):
        return os.getpid()

    @abstractmethod
    def handle(self):
        raise NotImplementedError


class AbstractLifecycleMixin(six.with_metaclass(ABCMeta, object)):
    """
    Worker Lifecycle:

                        ....can_continue....
                        v                  :
    +-----------+     +----------+       +---------+     +------------+
    | on_create | --> | on_start | ----> | on_stop | --> | on_destroy |
    +-----------+     +----------+       +---------+     +------------+
    """

    @abstractmethod
    def can_continue(self):
        raise NotImplementedError

    @abstractmethod
    def on_create(self):
        raise NotImplementedError

    @abstractmethod
    def on_start(self):
        raise NotImplementedError

    @abstractmethod
    def on_stop(self):
        raise NotImplementedError

    @abstractmethod
    def on_destroy(self):
        raise NotImplementedError


class AbstractServiceDiscoveryMixin(six.with_metaclass(ABCMeta, object)):
    @abstractmethod
    def get_registration_info(self):
        raise NotImplementedError

    @abstractmethod
    def update_registration_info(self):
        raise NotImplementedError

    @abstractmethod
    def register(self):
        raise NotImplementedError

    @abstractmethod
    def unregister(self):
        raise NotImplementedError

    @abstractmethod
    def query_for_hosts(self):
        raise NotImplementedError

    @abstractmethod
    def query_for_instances(self):
        raise NotImplementedError


class AbstractDispatchMixin(six.with_metaclass(ABCMeta, object)):
    @abstractmethod
    def dispatch(self):
        raise NotImplementedError

    @abstractmethod
    def dispatch_for_host(self):
        raise NotImplementedError

    @abstractmethod
    def dispatch_for_instance(self):
        raise NotImplementedError

    @abstractmethod
    def dispatch_status(self):
        raise NotImplementedError

    @abstractmethod
    def query_host_targets(self):
        raise NotImplementedError

    @abstractmethod
    def query_instance_targets(self):
        raise NotImplementedError
