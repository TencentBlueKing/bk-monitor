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
import time
from datetime import datetime, timedelta, timezone

from alarm_backends.core.cache.shield import ShieldCacheManager
from alarm_backends.service.alert.qos import FC, IncidentInfluence, register_influence
from alarm_backends.service.alert.qos.scope import load_scope


@register_influence("vm")
class VMIncidentInfluence(IncidentInfluence):
    def load_influence(self, target):
        if target not in self._cache:
            scope_obj = load_scope(self.module, target)
            if scope_obj:
                self._cache[target] = scope_obj
        return self._cache.get(target)

    # VM存储故障
    def get_influence(self, target):
        """返回一个最小化，可以被屏蔽处理器(AlertShieldObj)处理的屏蔽配置结构"""
        scope_obj = self.load_influence(target)
        return scope_obj.get_scope_dimension()

    def get_influence_duration(self, target):
        # 获取目标vm集群的故障影响时间
        scope_obj = self.load_influence(target)
        return scope_obj.get_scope_duration()


def get_influence(module, target) -> dict:
    cls = FC.collection.get(module)
    if cls is None:
        return {}
    return cls().get_influence(target)


def publish_failure(module, target):
    cls = FC.collection.get(module)
    if cls is None:
        return
    influence = cls()
    duration = influence.get_influence_duration(target)
    ShieldCacheManager.publish_failure(module, target, duration)
    return duration


def clear_failure(module, target):
    duration = ShieldCacheManager.get_last_failure_end(module, target)
    if duration > int(time.time()):
        ShieldCacheManager.publish_failure(module, target, 0)
    return 0


def get_failure_scope_config():
    configs = []
    now = int(time.time())
    # 获取当前生效的全部故障
    for module in FC.collection:
        # 获取当前生效的全部故障
        failures = ShieldCacheManager.get_all_failures(module)
        for target, end_time in failures.items():
            time_delta = int(end_time) - now
            if time_delta > 0:
                # 故障中
                _config = get_influence(module, target)
                if _config:
                    _config.update(
                        {
                            "begin_time": datetime.now(tz=timezone.utc),
                            "end_time": datetime.now(tz=timezone.utc) + timedelta(seconds=time_delta),
                        }
                    )
                    configs.append(_config)

    return configs
