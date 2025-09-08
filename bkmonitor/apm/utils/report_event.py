"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import time

from django.conf import settings
from django.utils.translation import gettext as _
from opentelemetry.trace import get_current_span

from bkmonitor.utils.common_utils import get_local_ip
from bkmonitor.utils.custom_report_tools import custom_report_tool
from bkmonitor.utils.request import get_request_username
from core.drf_resource import api


class EventReportHelper:
    """APM api侧事件上报"""

    @classmethod
    def _get_content(cls, content, app=None):
        info = ""
        if app:
            response_biz_data = api.cmdb.get_business(bk_biz_ids=[app.bk_biz_id], bk_tenant_id=app.bk_tenant_id)
            bk_biz_name = response_biz_data[0].bk_biz_name if response_biz_data else ""
            info = (
                f"应用名称: {app.app_name} 业务 ID: {app.bk_biz_id} 业务名称: {bk_biz_name} "
                f"操作人: {get_request_username()}"
            )

        return [
            {
                "event_name": _("监控平台 APM 后台"),
                "target": get_local_ip(),
                "timestamp": int(round(time.time() * 1000)),
                "dimension": {},
                "event": {
                    "content": content + info,
                },
            }
        ]

    @classmethod
    def report(cls, content, application=None, with_trace_id=True):
        if with_trace_id:
            trace_id = format(get_current_span().get_span_context().trace_id, "032x")
            content += f"  TraceId: {trace_id}"

        config_info = settings.APM_CUSTOM_EVENT_REPORT_CONFIG
        data_id = config_info.get("data_id", "")
        token = config_info.get("token", "")

        if config_info and token:
            custom_report_tool(data_id).send_data_by_http(cls._get_content(content, application), token)
