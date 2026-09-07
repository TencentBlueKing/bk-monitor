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

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.log_databus.nodeman_v3.constants import (
    NODEMAN_INTEGRATION_MODES,
    NODEMAN_MODE_V2,
    NODEMAN_MODE_V3_FRESH,
)


def get_nodeman_integration_mode() -> str:
    """
    读取节点管理集成模式。

    只允许 v2 与 v3_fresh 两种取值，不提供 hybrid：V3-only 环境下任何 V3 失败都必须失败关闭，
    一旦允许混合模式，异常路径就会悄悄退回 V2 并产生双写。
    """
    mode = getattr(settings, "NODEMAN_INTEGRATION_MODE", NODEMAN_MODE_V2) or NODEMAN_MODE_V2
    if mode not in NODEMAN_INTEGRATION_MODES:
        raise ImproperlyConfigured(
            f"invalid NODEMAN_INTEGRATION_MODE: {mode}, choices are {list(NODEMAN_INTEGRATION_MODES)}"
        )
    return mode


def is_nodeman_v3_only() -> bool:
    return get_nodeman_integration_mode() == NODEMAN_MODE_V3_FRESH
