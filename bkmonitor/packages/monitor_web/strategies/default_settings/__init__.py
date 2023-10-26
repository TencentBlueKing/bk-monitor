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

from importlib import import_module

from django.conf import settings
from django.utils.module_loading import import_string

DEFAULTS = {
    "DEFAULT_OS_STRATEGIES_LIST": [
        {
            "version": "v1",
            "module_path": "monitor_web.strategies.default_settings.os.v1",
        },
    ],
    "DEFAULT_GSE_PROCESS_EVENT_STRATEGIES_LIST": [
        {
            "version": "v1",
            "module_path": "monitor_web.strategies.default_settings.gse.v1",
        },
    ],
    "DEFAULT_K8S_STRATEGIES_LIST": [
        {
            "version": "v1",
            "module_path": "monitor_web.strategies.default_settings.k8s.v1",
        },
        {
            "version": "v2",
            "module_path": "monitor_web.strategies.default_settings.k8s.v2",
        },
    ],
}

IMPORT_STRINGS = set()
VERSION_STRINGS = {
    "DEFAULT_OS_STRATEGIES_LIST",
    "DEFAULT_GSE_PROCESS_EVENT_STRATEGIES_LIST",
    "DEFAULT_K8S_STRATEGIES_LIST",
}


class DefaultStrategySettings:
    def __init__(self, defaults=None, import_strings=None, version_strings=None):
        self.defaults = defaults
        self.import_strings = import_strings
        self.version_strings = version_strings

    def __getattr__(self, attr):
        if attr not in self.defaults:
            raise AttributeError("Invalid build-in strategy setting: '%s'" % attr)

        try:
            # Check if present in user settings
            val = getattr(settings, attr)
        except AttributeError:
            # Fall back to defaults
            val = self.defaults[attr]

        # Coerce import strings into classes
        if attr in self.import_strings:
            if isinstance(val, str):
                val = import_string(val)
            elif isinstance(val, (list, tuple)):
                val = [import_string(item) for item in val]

        if attr in self.version_strings:
            for item in val:
                module_path = item["module_path"]
                item["module"] = import_module(module_path)

        return val


default_strategy_settings = DefaultStrategySettings(DEFAULTS, IMPORT_STRINGS, VERSION_STRINGS)
