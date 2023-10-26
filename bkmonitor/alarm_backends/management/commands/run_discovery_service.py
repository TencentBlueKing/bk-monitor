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

from django.conf import settings
from django.core import signals

from alarm_backends.core.cluster import get_cluster
from alarm_backends.management.base.loaders import load_handler_cls
from alarm_backends.management.base.service_discovery import ConsulServiceDiscoveryMixin
from alarm_backends.management.commands.run_service import Command as ServiceCommand

logger = logging.getLogger(__name__)


class Command(ServiceCommand, ConsulServiceDiscoveryMixin):
    __COMMAND_NAME__ = __name__.split(".")[-1]

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)
        ConsulServiceDiscoveryMixin.__init__(self, *args, **kwargs)
        self._PATH_PREFIX_ = "{}_{}_{}_{}/{}".format(
            settings.APP_CODE, settings.PLATFORM, settings.ENVIRONMENT, get_cluster().name, self.__COMMAND_NAME__
        )

    def on_start(self, *args, **kwargs):
        self._PATH_PREFIX_ = "{}-{}".format(self._PATH_PREFIX_, self._SERVICE_TYPE_)
        try:
            signals.request_started.send(sender=self.__class__, environ=kwargs)
            handler_cls = load_handler_cls(self._SERVICE_TYPE_, self._HANDLER_TYPE_)
        except Exception:  # noqa
            logger.exception(
                "Error loading Handler, service_type({}),"
                " handler_type({})".format(self._SERVICE_TYPE_, self._HANDLER_TYPE_)
            )
            raise
        else:
            try:
                self.register()
                handler = handler_cls(service=self, *args, **kwargs)
                handler.handle()
            except Exception as exc:
                always_raise = getattr(exc, "always_raise", False)
                if always_raise:
                    raise exc
                logger.exception(
                    "Error executing Handler, service_type({}), "
                    "handler_type({})".format(self._SERVICE_TYPE_, self._HANDLER_TYPE_)
                )
            finally:
                signals.request_finished.send(sender=self.__class__)

    def on_destroy(self, *args, **kwargs):
        self.unregister()
