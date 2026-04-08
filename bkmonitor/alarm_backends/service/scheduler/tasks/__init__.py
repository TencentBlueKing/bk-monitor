"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from .api_cron import *  # noqa
from .cron import *  # noqa
from .report_cron import *  # noqa


def perform_sharding_task(targets, sharding_task, num_per_task=10):
    """
    任务分片调度： 将targets分片拆分到子任务（sharding_task）中执行
    :param targets: 目标任务列表
    :param sharding_task: 分片任务函数
    :param num_per_task:
    :return:
    """
    idx = 0
    while idx < len(targets) // num_per_task + 1:
        start_offset = idx * num_per_task
        end_offset = start_offset + num_per_task
        sharding_task.apply_async(args=(list(targets[start_offset:end_offset]),))
        idx += 1
