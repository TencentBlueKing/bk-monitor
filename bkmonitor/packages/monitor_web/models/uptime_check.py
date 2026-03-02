"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from monitor.models import UptimeCheckGroup as base_UptimeCheckGroup
from monitor.models import UptimeCheckNode as base_UptimeCheckNode
from monitor.models import UptimeCheckTask as base_UptimeCheckTask
from monitor.models import (
    UptimeCheckTaskCollectorLog as base_UptimeCheckTaskCollectorLog,
)


class UptimeCheckNode(base_UptimeCheckNode):
    class Meta:
        proxy = True


class UptimeCheckTask(base_UptimeCheckTask):
    class Meta:
        proxy = True


class UptimeCheckTaskCollectorLog(base_UptimeCheckTaskCollectorLog):
    class Meta:
        proxy = True


class UptimeCheckGroup(base_UptimeCheckGroup):
    class Meta:
        proxy = True
