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

from bk_audit.contrib.opentelemetry.setup import setup
from django.apps import AppConfig

from apps.log_audit.client import bk_audit_client, otlp_report_enabled
from apps.utils.log import logger


class AuditConfig(AppConfig):
    name = "apps.log_audit"

    # BKAPP_OTEL_LOG_ENDPOINT: 审计中心获取上报endpoint
    # BKAPP_OTEL_LOG_BK_DATA_TOKEN: 审计中心获取上报token
    def ready(self):
        if not otlp_report_enabled():
            logger.warning("[audit] OTLP 上报未启用，审计事件仅输出到 bk_audit 日志器")
            return
        try:
            setup(bk_audit_client)
        except Exception:  # pylint: disable=broad-except
            # 初始化失败不能阻断应用启动，但必须留下痕迹，否则审计事件会静默丢失
            logger.exception("[audit] 初始化 OTLP 上报失败")
