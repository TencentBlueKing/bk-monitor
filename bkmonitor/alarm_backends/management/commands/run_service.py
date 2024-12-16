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

from django.core import signals

from alarm_backends.management.base.base import BaseCommand
from alarm_backends.management.base.loaders import load_handler_cls

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    _SERVICE_TYPE_ = ""  # access/detect/trigger/event/action/recovery/preparation .etc
    _HANDLER_TYPE_ = ""  # process/celery

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument(
            "-s",
            "--service-type",
            help="Which service to run.",
        )
        parser.add_argument(
            "-H",
            "--handler-type",
            default="process",
            choices=["process", "celery"],
            help="Which handler does the process use?",
        )
        parser.add_argument("args", nargs="*", help="extra args")

    def on_start(self, *args, **kwargs):
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
                handler = handler_cls(*args, **kwargs)
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
