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

from django.utils.translation import gettext_lazy as _

from core.errors import Error


class AlertError(Error):
    status_code = 500
    code = 3324001
    name = _("告警模块错误")
    message_tpl = _("告警模块错误")


class AlertNotFoundError(Error):
    status_code = 404
    code = 3324002
    name = _("告警不存在")
    message_tpl = _("告警ID ({alert_id}) 对应的告警信息不存在")


class EventNotFoundError(Error):
    status_code = 404
    code = 3324002
    name = _("事件不存在")
    message_tpl = _("事件ID ({event_id}) 对应的告警信息不存在")


class QueryStringParseError(Error):
    status_code = 200
    code = 3324003
    name = _("查询语法错误")
    message_tpl = _("查询语法错误: {msg}")


class AIOpsResultError(Error):
    status_code = 200
    code = 3324004
    name = _("AIOps结果异常")
    message_tpl = _("AIOps结果异常: {err}")


class AIOpsFunctionAccessedError(Error):
    status_code = 200
    code = 3324005
    name = _("AIOps功能未接入")
    message_tpl = _("当前空间尚未接入[{func}]功能")


class AIOpsMultiAnomlayDetectError(Error):
    status_code = 200
    code = 3324006
    name = _("主机智能异常检测结果内容异常")
    message_tpl = _("主机智能异常检测结果内容异常")


class AIOpsDisableError(Error):
    # 区别于 AIOpsFunctionAccessedError，AIOpsDisableError 表示功能在监控侧未开启
    status_code = 200
    code = 3324007
    name = _("AIOps功能未开启")
    message_tpl = _("当前空间尚未开[{func}]功能")


class AIOpsAccessedError(Error):
    status_code = 200
    code = 3324008
    name = _("AIOps功能接入失败")
    message_tpl = _("当前空间接入[{func}]功能失败")
