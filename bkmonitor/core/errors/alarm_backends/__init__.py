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


from django.utils.translation import gettext_lazy as _lazy

from core.errors import Error


class AlarmBackendsError(Error):
    status_code = 500
    code = 3350000
    name = _lazy("告警后台服务错误")
    message_tpl = _lazy("告警后台服务错误：{msg}")


class AccessError(AlarmBackendsError):
    code = 3351000
    name = _lazy("数据接入服务错误")
    message_tpl = _lazy("数据接入服务错误：{msg}")


class DetectError(AlarmBackendsError):
    code = 3352000
    name = _lazy("异常检测服务错误")
    message_tpl = _lazy("异常检测服务错误：{msg}")


class TriggerError(AlarmBackendsError):
    code = 3353000
    name = _lazy("异常触发服务错误")
    message_tpl = _lazy("异常触发服务错误：{msg}")


class LockError(AlarmBackendsError):
    code = 3350001
    name = _lazy("分布式锁错误")
    message_tpl = _lazy("分布式锁错误：{msg}")


class StrategyNotFound(AlarmBackendsError):
    code = 3350002
    name = _lazy("策略配置快照找不到")
    message_tpl = _lazy("策略配置快照找不到，key: {key}")


class StrategyItemNotFound(AlarmBackendsError):
    code = 3350003
    name = _lazy("策略对应的监控项找不到")
    message_tpl = _lazy("策略对应的监控项找不到，策略ID: {strategy_id}，监控项ID：{item_id}")


class ActionAlreadyFinishedError(AlarmBackendsError):
    """
    已经结束
    """

    code = 3350004
    name = _lazy("处理已经完成")
    message_tpl = _lazy("当前处理已经结束，处理ID: {action_id}，完成状态：{action_status}")


class EmptyAssigneeError(Error):
    code = 3350005
    name = _lazy("用户组为空")
    message_tpl = _lazy("获取当前告警策略配置的告警组用户为空，无法执行处理套餐")
