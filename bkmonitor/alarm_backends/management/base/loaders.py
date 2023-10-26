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


import inspect

from celery.loaders.base import find_related_module

from alarm_backends.core.handlers import base
from bkmonitor.utils.common_utils import package_contents

HANDLER_ROOT_MODULE = "alarm_backends.service"


def autodiscover_handlers():
    service_handlers = {}
    for service_type in package_contents(HANDLER_ROOT_MODULE):
        pkg = "{}.{}".format(HANDLER_ROOT_MODULE, service_type)
        handler_module = find_related_module(pkg, "handler")
        if handler_module is None:
            continue

        for attr, val in list(handler_module.__dict__.items()):
            if inspect.isclass(val) and issubclass(val, base.BaseHandler):
                if attr.endswith("CeleryHandler"):
                    service_handlers.setdefault(service_type, {})["celery"] = val
                else:
                    service_handlers.setdefault(service_type, {})["process"] = val
    return service_handlers


SERVICE_HANDLERS = autodiscover_handlers()


def load_handler_cls(service_type, handler_type):
    handlers = SERVICE_HANDLERS.get(service_type)
    if not handlers:
        raise Exception("Unknown Service Type(%s)." % str(service_type))

    if handler_type not in handlers:
        raise Exception("Handler Type(%s) is not supported." % str(handler_type))

    return handlers.get(handler_type)
