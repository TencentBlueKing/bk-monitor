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

import os

from bk_audit.client import BkAudit
from bk_audit.contrib.django.formatters import DjangoFormatter
from bk_audit.contrib.opentelemetry.exporters import OTLogExporter
from bk_audit.contrib.opentelemetry.utils import ServiceNameHandler
from bk_audit.log.exporters import LoggerExporter
from django.conf import settings


def otlp_report_enabled() -> bool:
    """
    endpoint 与 token 齐全才认为 OTLP 上报可用

    setup() 对 token 取默认空串，缺失时不报错，事件会发出去再被 bk-collector 拒收。
    这里提前判掉，让缺配置时退回 LoggerExporter 并留下告警。
    不校验 BKAPP_OTEL_LOG_BK_DATA_ID：bk-collector 按 token 路由，data_id 不参与鉴权，
    仓库内所有环境（含 bklog 自身的 OTLP 日志上报）都只配 endpoint 与 token。
    """
    return bool(os.getenv("BKAPP_OTEL_LOG_ENDPOINT", "")) and bool(os.getenv("BKAPP_OTEL_LOG_BK_DATA_TOKEN", ""))


# 未启用 OTLP 时 apps.py 不会调 setup()，OTLogExporter 的日志器没有 handler，
# 事件会被静默丢弃。退回 LoggerExporter 让事件至少落到 bk_audit 日志器，便于自证事件已生成。
exporters = [OTLogExporter()] if otlp_report_enabled() else [LoggerExporter()]

bk_audit_client = BkAudit(
    settings.APP_CODE,
    settings.SECRET_KEY,
    {"formatter": DjangoFormatter(), "exporters": exporters, "service_name_handler": ServiceNameHandler},
)
