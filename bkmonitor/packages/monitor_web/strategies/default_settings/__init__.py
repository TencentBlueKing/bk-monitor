"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
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
        # v2=多租户系统事件（custom 源）：gse 系统事件 AgentLost/DiskReadonly/CoreFile/OOM/PingUnreachable
        # 走 V4 分业务链路（base_{tenant}_{biz}_event）。主机重启/进程端口不在此版本——它们底层是
        # system.env / system.proc_port 时序，由 BaseAlarmMetricCacheManager 在多租户内置为 bk_monitor 源
        # 伪事件，经 os/v1（未做租户隔离、本就声明了这两条 bk_monitor 事件策略）命中创建，无需单列版本。
        # 仅在多租户模式注册 v2：否则单租户下空版本会被基础 loader 当作“无需创建的空版本”直接登记
        # DefaultStrategyBizAccessModel，后续切换到多租户时该版本因幂等跳过、永远不会补建。
        *(
            [
                {
                    "version": "v2",
                    "module_path": "monitor_web.strategies.default_settings.os.v2",
                },
            ]
            if settings.ENABLE_MULTI_TENANT_MODE
            else []
        ),
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
            raise AttributeError(f"Invalid build-in strategy setting: '{attr}'")

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
            elif isinstance(val, list | tuple):
                val = [import_string(item) for item in val]

        if attr in self.version_strings:
            for item in val:
                module_path = item["module_path"]
                item["module"] = import_module(module_path)

        return val


default_strategy_settings = DefaultStrategySettings(DEFAULTS, IMPORT_STRINGS, VERSION_STRINGS)
