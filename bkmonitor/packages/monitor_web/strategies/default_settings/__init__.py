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
        # 仅在多租户模式注册以下版本（单租户下不注册，列表只剩 v1）：
        # - v2=多租户系统事件（custom 源）：gse 系统事件 AgentLost/DiskReadonly/CoreFile/OOM/PingUnreachable
        #   走 V4 分业务链路（base_{tenant}_{biz}_event）；
        # - v3=多租户主机重启/进程端口（bk_monitor 源伪事件）：底层 system.env / system.proc_port 时序，
        #   由 BaseAlarmMetricCacheManager 在多租户内置目录项，经 os_loader 重定向 + 检测算法命中创建。
        # 为何用 MT 门控、单租户不注册：v2/v3 在单租户下 DEFAULT_OS_STRATEGIES 为空，若不门控、照样注册，
        # 基础 loader 会把空版本当作“无需创建的空版本”直接登记接入记录；日后该业务切到多租户时，这两个
        # 版本因已登记而幂等跳过、永不补建。门控掉即可让多租户首次运行重新注册并补建。
        # 单列 v3 而非并入 v1：v1 把这两条圈在单租户块内、多租户不声明；且 v1 在多租户已因时序策略
        # 被登记接入，若移进 v1 会令存量业务幂等跳过、永不补建（详见 os/v3.py 注释）。
        *(
            [
                {
                    "version": "v2",
                    "module_path": "monitor_web.strategies.default_settings.os.v2",
                },
                {
                    "version": "v3",
                    "module_path": "monitor_web.strategies.default_settings.os.v3",
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
