"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from datetime import datetime
from functools import partial
from secrets import token_hex

import pytz
from django.db import models

from bkmonitor.utils.model_manager import AbstractRecordModel
from constants.common import DEFAULT_TENANT_ID

TokenTypeViews = {
    "grafana": lambda x: x.startswith("monitor_web.grafana."),
    "config": lambda x: x.startswith("monitor_web.strategy."),
    "data_query": lambda x: x.startswith("monitor_web.grafana."),
    "as_code": lambda x: x.startswith("monitor_web.as_code."),
}


class AuthType:
    AsCode = "as_code"
    Grafana = "grafana"
    UptimeCheck = "uptime_check"
    Host = "host"
    Collect = "collect"
    Scene = "scene"
    CustomMetric = "custom_metric"
    CustomEvent = "custom_event"
    Kubernetes = "kubernetes"
    Event = "event"
    Dashboard = "dashboard"
    Apm = "apm"
    API = "api"
    Incident = "incident"
    Entity = "entity"
    User = "user"


class ApiAuthToken(AbstractRecordModel):
    """
    API鉴权令牌
    """

    AUTH_TYPE_CHOICES = (
        (AuthType.AsCode, "AsCode"),
        (AuthType.Grafana, "Grafana"),
        (AuthType.API, "API"),
        (AuthType.UptimeCheck, "UptimeCheck"),
        (AuthType.Host, "Host"),
        (AuthType.Collect, "Collect"),
        (AuthType.Scene, "Scene"),
        (AuthType.CustomMetric, "CustomMetric"),
        (AuthType.CustomEvent, "CustomEvent"),
        (AuthType.Kubernetes, "Kubernetes"),
        (AuthType.Event, "Event"),
        (AuthType.Dashboard, "Dashboard"),
        (AuthType.Apm, "Apm"),
        (AuthType.Incident, "Incident"),
        (AuthType.Entity, "Entity"),
        (AuthType.User, "User"),
    )

    bk_tenant_id = models.CharField("租户ID", max_length=64, default=DEFAULT_TENANT_ID)
    name = models.CharField("令牌名称", max_length=64, unique=True)
    token = models.CharField("鉴权令牌", max_length=32, db_index=True, unique=True, default=partial(token_hex, 16))
    # 所属项目列表 biz#2,project#5
    namespaces = models.JSONField("所属命名空间", default=list)
    type = models.CharField("鉴权类型", max_length=32, choices=AUTH_TYPE_CHOICES)
    params = models.JSONField("鉴权参数", default=dict)
    expire_time = models.DateTimeField("过期时间", null=True, default=None)

    class Meta:
        verbose_name = "API鉴权令牌"
        verbose_name_plural = "API鉴权令牌"
        db_table = "api_auth_token"

    def is_allowed_view(self, view):
        """
        判断view是否合法
        """
        if self.type not in [AuthType.Grafana, AuthType.AsCode, AuthType.Entity]:
            return True
        view_cls = getattr(view, "cls", None)
        if not view_cls:
            return False

        return (
            (self.type == "grafana" and view_cls.__module__ == "monitor_web.grafana.views")
            or (
                self.type == "as_code"
                and (
                    view_cls.__module__ in ["monitor_web.as_code.views"]
                    or view_cls.__name__ in ["QueryAsyncTaskResultViewSet", "CollectorPluginViewSet"]
                )
            )
            or (self.type == "entity" and view_cls.__module__ == "kernel_api.views.v4.entity")
        )

    def is_allowed_namespace(self, namespace: str):
        """
        判断命名空间是否合法
        """
        return namespace in self.namespaces or "biz#all" in self.namespaces

    def is_expired(self):
        """
        判断token是否过期
        """
        if not self.expire_time:
            return False
        return self.expire_time < datetime.now(tz=pytz.utc)


class TokenAccessRecord(AbstractRecordModel):
    """
    API鉴权令牌访问记录
    """

    token = models.CharField("鉴权令牌", max_length=32)

    class Meta:
        verbose_name = "API鉴权令牌访问记录"
        verbose_name_plural = "API鉴权令牌访问记录"
        db_table = "token_access_record"
        index_together = (("token", "create_user"),)
