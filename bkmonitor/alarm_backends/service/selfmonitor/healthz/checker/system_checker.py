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
import time

import psutil as raw_psutil

from bkmonitor.utils.call_cache import CallCache

from .checker import CheckerRegister
from .utils import simple_check

register = CheckerRegister.system
psutil = CallCache(raw_psutil)
logger = logging.getLogger("self_monitor")


@register.status()
def system_status(manager, result):
    """系统状态"""
    result.ok(time.time())


@register.cpu.count(safe=True)
@simple_check
def cpu_count():
    """CPU核数"""
    return psutil.cpu_count()


@register.cpu.percent(safe=True)
@simple_check
def cpu_percent():
    """CPU使用率"""
    return psutil.cpu_percent()


@register.cpu.percent.all(safe=True)
def all_cpu_percent(manager, result):
    """各核CPU使用率"""
    result.ok(psutil.cpu_percent(percpu=True))


@register.mem.process.usage(safe=True)
@simple_check
def mem_proc_usage():
    """应用内存使用率"""
    info = psutil.virtual_memory()
    return 100 - 100.0 * (info.buffers + info.cached + info.free) / info.total


@register.mem.usage(safe=True)
@simple_check
def mem_usage():
    """内存使用率"""
    info = psutil.virtual_memory()
    return info.percent


@register.mem.available(safe=True)
@simple_check
def mem_available():
    """可用内存"""
    info = psutil.virtual_memory()
    return info.available


@register.mem.used(safe=True)
@simple_check
def mem_used():
    """已用内存"""
    info = psutil.virtual_memory()
    return info.used


@register.mem.free(safe=True)
@simple_check
def mem_free():
    """空闲内存"""
    info = psutil.virtual_memory()
    return info.free


@register.mem.total(safe=True)
@simple_check
def mem_total():
    """总内存"""
    info = psutil.virtual_memory()
    return info.total


@register.disk.usage(safe=True)
@simple_check
def disk_usage(path="."):
    """磁盘使用率"""
    info = psutil.disk_usage(path)
    return info.percent


@register.disk.free(safe=True)
@simple_check
def disk_free(path="."):
    """磁盘空闲量"""
    info = psutil.disk_usage(path)
    return info.free


@register.disk.used(safe=True)
@simple_check
def disk_used(path="."):
    """磁盘使用量"""
    info = psutil.disk_usage(path)
    return info.used


@register.disk.total(safe=True)
@simple_check
def disk_total(path="."):
    """磁盘总量"""
    info = psutil.disk_usage(path)
    return info.total


@register.disk.ioutil(safe=True)
@simple_check
def disk_ioutil(name=None, delay=0.1):
    """磁盘IO使用率"""
    disk_io_counters = raw_psutil.disk_io_counters
    if name:

        def patched_disk_io_counters():
            return raw_psutil.disk_io_counters(True)[name]

        disk_io_counters = patched_disk_io_counters

    info1 = disk_io_counters()
    time1 = time.time()
    time.sleep(delay)
    info2 = raw_psutil.disk_io_counters()
    time2 = time.time()

    return (info2.write_time + info2.read_time - info1.write_time - info1.read_time) / (time2 - time1) / 10
