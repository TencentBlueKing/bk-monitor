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


class AlertEventError(Error):
    status_code = 400
    code = 3314001
    name = _lazy("告警事件模块错误")
    message_tpl = _lazy("告警事件模块错误：{msg}")


class EventNotExist(AlertEventError):
    code = 3314002
    name = _lazy("告警事件不存在")
    message_tpl = _lazy("告警事件不存在：{event_id}")


class NotTimeSeriesError(AlertEventError):
    status_code = 204
    code = 3314003
    name = _lazy("非时序数据类型")
    message_tpl = _lazy("{event_id}事件关联的数据类型非时序数据类型")


class AggmethodIsRealtimeError(AlertEventError):
    status_code = 204
    code = 3314004
    name = _lazy("聚合方法是实时")
    message_tpl = _lazy("{event_id}实时监控无关联图表")
