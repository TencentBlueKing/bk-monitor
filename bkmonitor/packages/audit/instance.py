"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

__doc__ = """
from audit.instance import *
from bk_audit.log.exporters import BaseExporter
from rest_framework.test import APIRequestFactory
class ConsoleExporter(BaseExporter):
    is_delay = False
    def export(self, events):
        for event in events:
            print(event.to_json_str())
bk_audit_client.add_exporter(ConsoleExporter())
factory = APIRequestFactory()
request = factory.get("/grafana/api/dashboards/home", data={})
request.biz_id=2
class User:
    username = "admin"
setattr(request, "user", User())
push_event(request)
"""

import logging
import re
from copy import copy
from types import SimpleNamespace

from audit.client import bk_audit_client
from bk_audit.log.models import AuditContext, AuditInstance

from bkmonitor.iam import ActionEnum

logger = logging.getLogger(__name__)


class BaseMonitorInstance:
    action = None
    resource_id = ""

    @property
    def instance(self):
        return AuditInstance(self)

    @property
    def extend_data(self):
        return {"action_name": self.action.name}

    @property
    def resource_type(self):
        class ResourceType:
            id = ""

        _resource_type = ResourceType()
        _resource_type.id = self.resource_id
        return _resource_type


class DashboardInstance(BaseMonitorInstance):
    action = ActionEnum.VIEW_SINGLE_DASHBOARD
    resource_id = "Dashboard"

    def __init__(self, uid):
        self.instance_id = uid
        self.instance_name = uid


def push_event(request, response=None):
    """
    基于request对象，自动上报审计日志
    """
    try:
        key_params = ["user", "biz_id"]
        # request 合法性验证
        for key in key_params:
            if not hasattr(request, key):
                return

        instance = None
        for methods, regex, instance_cls in InstanceFilter:
            if request.method not in methods:
                continue
            ret = regex.fullmatch(request.path)
            if ret:
                instance = instance_cls(**ret.groupdict())
                break

        if instance is None:
            return

        external_user = getattr(request, "external_user", "")
        authorizer = getattr(request.user, "username", "")
        audit_request = request
        if external_user:
            audit_request = copy(request)
            audit_request.user = SimpleNamespace(username=external_user)
        context = AuditContext(request=audit_request)

        extend_data = {
            "external_user": external_user,
            "bk_biz_id": request.biz_id,
            "request_method": request.method,
        }
        if external_user and authorizer:
            extend_data["authorizer"] = authorizer
        org_name = getattr(request, "org_name", "")
        if org_name:
            extend_data["grafana_org_name"] = org_name
        extend_data.update(instance.extend_data)

        status_code = getattr(request, "_audit_response_status", getattr(response, "status_code", None))
        result_code = 0
        result_content = ""
        if status_code is not None:
            extend_data["response_status"] = status_code
            if status_code >= 400:
                result_code = status_code
                result_content = f"HTTP {status_code}"

        bk_audit_client.add_event(
            action=instance.action,
            resource_type=instance.resource_type,
            audit_context=context,
            instance=instance.instance,
            result_code=result_code,
            result_content=result_content,
            extend_data=extend_data,
        )
        bk_audit_client.export_events()
    except Exception:
        logger.exception("push audit event failed")


InstanceFilter = (
    ({"GET"}, re.compile(r"/grafana/api/dashboards/(?P<uid>home)/?"), DashboardInstance),
    ({"GET"}, re.compile(r"/grafana/api/dashboards/uid/(?P<uid>[^/]+)/?"), DashboardInstance),
)
