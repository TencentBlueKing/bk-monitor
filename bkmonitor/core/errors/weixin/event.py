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


class WeixinEventError(Error):
    status_code = 400
    code = 3319000
    name = _lazy("移动端事件模块错误")
    message_tpl = _lazy("移动端事件模块错误：{msg}")


class AlertCollectNotFound(Error):
    code = 3319001
    name = _lazy("告警汇总记录不存在")
    message_tpl = _lazy("告警汇总记录({alert_collect_id})不存在")


class EventNotFound(Error):
    code = 3319002
    name = _lazy("告警事件不存在")
    message_tpl = _lazy("告警事件({event_id})不存在")
