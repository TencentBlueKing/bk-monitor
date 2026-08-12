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


REGISTERED_SCENE_AUTH_TYPES = {
    "scene_collect",
    "scene_custom_event",
    "scene_custom_metric",
}


READONLY_SCENE_AUTH_TYPES = {
    AuthType.Apm,
    AuthType.Collect,
    AuthType.CustomEvent,
    AuthType.CustomMetric,
    AuthType.Dashboard,
    AuthType.Event,
    AuthType.Host,
    AuthType.Incident,
    AuthType.Kubernetes,
    AuthType.Scene,
    AuthType.UptimeCheck,
}

READONLY_SCENE_DENIED_ACTIONS = {
    "monitor_web.scene_view.views": {
        "bulk_update_scene_view_order_and_name",
        "delete_scene_view",
        "update_scene_view",
    },
    "monitor_web.share.views": {
        "create_share_token",
        "delete_share_token",
        "get_share_token_list",
        "update_share_token",
    },
}

READONLY_SCENE_STANDARD_DENIED_ACTIONS = {"create", "destroy", "partial_update", "update"}

HOST_SHARE_ALLOWED_ACTIONS = {
    "monitor_web.commons.cc.views.GetTopoTree": {"create"},
    "monitor_web.grafana.views.GrafanaViewSet": {"time_series/unify_query"},
    "monitor_web.performance.views.SearchHostInfoViewSet": {"create"},
    "monitor_web.performance.views.SearchHostMetricViewSet": {"create"},
    "monitor_web.scene_view.views.SceneViewViewSet": {
        "get_host_metric_group_panel_order",
        "get_host_or_topo_node_detail",
        "get_host_process_port_status",
        "get_host_process_list",
        "get_host_process_uptime",
        "get_host_views_panels",
        "get_process_metric_group_panel_order",
        "get_process_views_panels",
    },
}


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
        if self.type.startswith("scene_") and self.type not in REGISTERED_SCENE_AUTH_TYPES:
            return False

        view_cls = getattr(view, "cls", None)
        if self.type in READONLY_SCENE_AUTH_TYPES or self.type.startswith("scene_"):
            denied_actions = READONLY_SCENE_DENIED_ACTIONS.get(getattr(view_cls, "__module__", ""), set())
            view_actions = set(getattr(view, "actions", {}).values())
            if denied_actions & view_actions:
                return False

            if self.type == AuthType.Host:
                view_name = f"{getattr(view_cls, '__module__', '')}.{getattr(view_cls, '__name__', '')}"
                return bool(HOST_SHARE_ALLOWED_ACTIONS.get(view_name, set()) & view_actions)

            # ResourceViewSet uses create/update action names for POST/PUT query routes,
            # so standard mutation names only apply to conventional DRF viewsets.
            if not hasattr(view_cls, "resource_routes") and READONLY_SCENE_STANDARD_DENIED_ACTIONS & view_actions:
                return False

        if self.type not in [AuthType.Grafana, AuthType.AsCode, AuthType.Entity]:
            return True
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
