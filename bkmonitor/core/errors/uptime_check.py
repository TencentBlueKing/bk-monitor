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


class UptimeCheckError(Error):
    status_code = 400
    code = 3320001
    name = _lazy("拨测模块错误")
    message_tpl = _lazy("拨测模块错误：{msg}")


class UptimeCheckProcessError(UptimeCheckError):
    code = 3320002
    name = _lazy("bkmonitorbeat进程异常，请至节点管理处理")
    message_tpl = _lazy("bkmonitorbeat进程异常，请至节点管理处理")


class UnknownProtocolError(UptimeCheckError):
    code = 3320003
    name = _lazy("未知的拨测协议类型")
    message_tpl = _lazy("未知的拨测协议类型:{msg}")


class DeprecatedFunctionError(UptimeCheckError):
    code = 3320004
    name = _lazy("方法已弃用")
    message_tpl = _lazy("方法已弃用:{msg}")
