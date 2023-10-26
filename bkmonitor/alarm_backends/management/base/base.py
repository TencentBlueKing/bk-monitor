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


import logging
import signal
import sys
import time

import six
from django.conf import settings
from django.core.management.base import BaseCommand as DjangoBaseCommand
from django.db import close_old_connections

from alarm_backends.core.cluster import filter_bk_biz_ids, get_cluster
from alarm_backends.management.base import dispatch, protocol, service_discovery
from bkmonitor import models

logger = logging.getLogger(__name__)


class BaseCommand(DjangoBaseCommand, protocol.AbstractLifecycleMixin, protocol.AbstractWorker):

    # options
    _MIN_INTERVAL_ = 1  # seconds
    _MAX_CYCLES_ = 10000
    _MAX_UPTIME_ = 3600  # seconds

    # status
    __CYCLES__ = 0
    __EXC_INFO__ = None
    __LAST_TIMESTAMP__ = None
    __SHUTDOWN_RECEIVED__ = False
    __UPTIME__ = time.time()

    def add_arguments(self, parser):
        super(BaseCommand, self).add_arguments(parser)
        parser.add_argument(
            "--min-interval",
            type=int,
            default=1,
        )
        parser.add_argument(
            "--max-cycles",
            type=int,
            default=1000,
        )
        parser.add_argument(
            "--max-uptime",
            type=int,
            default=3600,
        )
        parser.add_argument(
            "--pdb",
            type=int,
            default=0,
        )

    def _onsignal(self, signum, frame):
        self.__SHUTDOWN_RECEIVED__ = True
        logger.info("shutdown received.")

    def break_loop(self):
        if self.__SHUTDOWN_RECEIVED__:
            return True
        else:
            self.__CYCLES__ += 1

    def can_continue(self):
        if self.__SHUTDOWN_RECEIVED__ or self.__EXC_INFO__ is not None:
            return False

        if isinstance(self.__LAST_TIMESTAMP__, float):
            interval = time.time() - self.__LAST_TIMESTAMP__
            if interval < self._MIN_INTERVAL_:
                time.sleep(self._MIN_INTERVAL_ - interval)
        self.__LAST_TIMESTAMP__ = time.time()

        return True

    def execute(self, *args, **options):
        if options.get("pdb"):
            import pdb

            pdb.set_trace()

        super(BaseCommand, self).execute(*args, **options)

    def handle(self, *args, **options):
        signal.signal(signal.SIGTERM, self._onsignal)
        signal.signal(signal.SIGINT, self._onsignal)

        for option, value in six.iteritems(options):
            if option not in ("no_color", "pythonpath", "settings", "traceback", "verbosity") and value is not None:
                attr = "_{}_".format(option.upper())
                setattr(self, attr, options[option])

        #
        # Worker Lifecycle
        #
        #                     ....can_continue....
        #                     v                  :
        # +-----------+     +----------+       +---------+     +------------+
        # | on_create | --> | on_start | ----> | on_stop | --> | on_destroy |
        # +-----------+     +----------+       +---------+     +------------+
        #

        self.on_create(*args)

        while self.can_continue():
            try:
                self.on_start(*args)
                self.on_stop(*args)
            except Exception as e:
                self.__EXC_INFO__ = (e.__class__, None, sys.exc_info()[2])
            finally:
                self.__CYCLES__ += 1
                if self.__CYCLES__ >= self._MAX_CYCLES_:
                    logger.info("maximum cycles reached.")
                    break
                if time.time() - self.__UPTIME__ >= self._MAX_UPTIME_:
                    logger.info("maximum uptime reached.")
                    break

        self.on_destroy(*args)

        if self.__EXC_INFO__ is not None:
            six.reraise(*self.__EXC_INFO__)

    def on_start(self, *args, **kwargs):
        pass

    def on_create(self, *args, **kwargs):
        close_old_connections()

    def on_stop(self, *args, **kwargs):
        pass

    def on_destroy(self, *args, **kwargs):
        pass


class ConsulDispatchCommand(dispatch.DefaultDispatchMixin, service_discovery.ConsulServiceDiscoveryMixin, BaseCommand):
    def add_arguments(self, parser):
        super(ConsulDispatchCommand, self).add_arguments(parser)
        parser.add_argument(
            "--path-prefix",
        )
        parser.add_argument(
            "--session-ttl",
            type=int,
            default=60,
        )

    __COMMAND_NAME__ = None

    def __init__(self, *args, **kwargs):
        super(ConsulDispatchCommand, self).__init__(*args, **kwargs)

        self._PATH_PREFIX_ = "{}_{}_{}_{}/{}".format(
            settings.APP_CODE, settings.PLATFORM, settings.ENVIRONMENT, get_cluster().name, self.__COMMAND_NAME__
        )

    def dispatch(self):
        self.register()

        hosts, instances = self.query_for_instances()
        hosts_targets, instance_targets = self.dispatch_for_instance(hosts, instances)
        self.update_registration_info(instance_targets)

        return hosts_targets, instance_targets

    def dispatch_status(self):
        registry = dict(self._registry)

        result = []
        for host_addr, instances in six.iteritems(registry):
            for instance in instances:
                path = "/".join([self._PATH_PREFIX_, host_addr, instance])
                info = self.get_registration_info(path)
                if info:
                    result.append(("{}/{}".format(host_addr, instance), info))

        return result

    def on_destroy(self, *args, **kwargs):
        self.unregister()

    def query_host_targets(self):
        data = list(models.StrategyModel.objects.filter(is_enabled=True).values_list("bk_biz_id", flat=True).distinct())
        data.extend(settings.BKMONITOR_WORKER_INCLUDE_LIST)
        data = filter_bk_biz_ids(data)
        data.sort()
        return data
