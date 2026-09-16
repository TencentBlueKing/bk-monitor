"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from django.utils.translation import gettext_lazy as _

from apps.exceptions import BaseException, ErrorCode


class BaseNodeManV3Exception(BaseException):
    MODULE_CODE = ErrorCode.BKLOG_COLLECTOR_CONFIG
    MESSAGE = _("节点管理 V3 适配异常")


class NodeManV3TransportError(BaseNodeManV3Exception):
    ERROR_CODE = "540"
    MESSAGE = _("节点管理 V3 请求传输失败: {err}")


class NodeManV3APIError(BaseNodeManV3Exception):
    ERROR_CODE = "541"
    MESSAGE = _("节点管理 V3 接口返回失败: {err}")


class NodeManV3UnknownResultError(BaseNodeManV3Exception):
    """
    写请求失败但无法判定服务端是否已生效。

    这类失败不在当次请求里自动重试，而是把动作标记成 unknown 交给下一次显式收敛处理。
    采集项收敛路径上的三个写操作都设计成可安全重放：create 之前先按策略名反查已有策略、
    update 是整体期望态覆盖、execute 重复触发只是多跑一轮收敛。
    新增其它写操作时必须先确认幂等，否则不能沿用这条恢复路径。
    """

    ERROR_CODE = "542"
    MESSAGE = _("节点管理 V3 写请求结果未知，禁止重放: {err}")


class NodeManV3CapabilityBlocked(BaseNodeManV3Exception):
    """
    V3 能力缺失。V3-only 模式下失败关闭，不回退 V2。
    """

    ERROR_CODE = "543"
    MESSAGE = _("节点管理 V3 能力未提供，已按失败关闭处理: {err}")


class NodeManV3BindingNotFound(BaseNodeManV3Exception):
    ERROR_CODE = "544"
    MESSAGE = _("采集项未建立节点管理 V3 部署策略绑定: {err}")
