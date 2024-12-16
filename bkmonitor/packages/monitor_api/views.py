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


import six
from blueapps.account.decorators import login_exempt
from django.apps import apps
from django.conf import settings
from django.utils.decorators import classonlymethod
from django.utils.translation import gettext as _
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.mixins import ListModelMixin
from rest_framework.response import Response
from rest_framework.serializers import Serializer
from rest_framework.viewsets import GenericViewSet

from bkmonitor.models import BaseAlarm
from monitor import models as app_models
from monitor.constants import SHELL_COLLECTOR_DB, UPTIME_CHECK_DB
from monitor_api import filtersets, models, serializers
from utils.host_index_backend import host_index_backend


class NestedRouterMixin(object):
    def _nested_router_patch(self, **kwargs):
        queryset = self.get_queryset()
        for k, v in six.iteritems(kwargs):
            if k.endswith("_pk"):
                lookup = k[:-3]
                queryset = queryset.filter(**{lookup: v})
        self.queryset = queryset

    @action(detail=False, methods=["get"], url_path="count")
    def count(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        content = {"count": queryset.count()}
        return Response(content)

    def list(self, request, *args, **kwargs):
        self._nested_router_patch(**kwargs)
        return super(NestedRouterMixin, self).list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        self._nested_router_patch(**kwargs)
        return super(NestedRouterMixin, self).retrieve(request, *args, **kwargs)


def get_viewset(model, read_only=True):
    class ReadOnlyModelViewSet(NestedRouterMixin, viewsets.ReadOnlyModelViewSet):
        ordering_fields = "__all__"

    class ModelViewSet(NestedRouterMixin, viewsets.ModelViewSet):
        ordering_fields = "__all__"

    cls_name = "%sViewSet" % model.__name__
    filterset_name = "%sFilterSet" % model.__name__
    serializer_name = "%sSerializer" % model.__name__
    if read_only:
        base = ReadOnlyModelViewSet
    else:
        base = ModelViewSet
    return cls_name, type(
        str(cls_name),
        (base,),
        {
            "queryset": model.objects.all(),
            "serializer_class": getattr(serializers, serializer_name),
            "filter_class": getattr(filtersets, filterset_name),
            "ordering_fields": "__all__",
        },
    )


for full_name, read_only in settings.MONITOR_API_MODELS:
    app_label, model_name = full_name.split(".")
    app_config = apps.get_app_config(app_label)
    model = app_config.get_model(model_name)
    name, viewset = get_viewset(model, read_only)
    locals()[name] = viewset


class UserConfigViewSet(NestedRouterMixin, viewsets.ModelViewSet):
    ordering_fields = "__all__"
    queryset = app_models.UserConfig.objects.all()
    serializer_class = serializers.UserConfigSerializer
    filter_class = filtersets.UserConfigFilterSet

    def create(self, request, *args, **kwargs):
        mutable = request.POST._mutable
        request.POST._mutable = True
        username = self.request.user.username
        request.data.update({"username": username})
        request.POST._mutable = mutable
        return super(UserConfigViewSet, self).create(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super(UserConfigViewSet, self).get_queryset()
        return queryset.filter(username=self.request.user.username)


class AlarmTypeViewSet(ListModelMixin, GenericViewSet):
    serializer_class = Serializer

    def get_queryset(self):
        return

    @classonlymethod
    def as_view(cls, actions=None, **initkwargs):
        # 登录豁免
        view = super(AlarmTypeViewSet, cls).as_view(actions=actions, **initkwargs)
        return login_exempt(view)

    def list(self, request, *args, **kwargs):
        info_list = []
        fields = {
            "cpu": "CPU",
            "net": _("网卡"),
            "mem": _("内存"),
            "disk": _("磁盘"),
            "process": _("进程"),
            "system_env": _("系统环境"),
        }
        for _f in fields:
            # 只过滤需要展示的内容
            host_index_list = host_index_backend.filter_host_index(graph_show=True, category=_f)
            for _h in host_index_list:
                info = dict(monitor_target=_h.id, description=_h.desc, monitor_type=_h.category, scenario=_("主机监控"))
                info_list.append(info)

        base_host_index_list = BaseAlarm.objects.filter(is_enable=True)
        for bhi in base_host_index_list:
            info_list.append(
                dict(monitor_target=bhi.real_id, description=bhi.desc, monitor_type=bhi.category, scenario=_("主机监控"))
            )
        info_list.append(
            dict(
                monitor_target=models.os_restart_index.real_id,
                description=models.os_restart_index.desc,
                monitor_type=models.os_restart_index.category,
                scenario=_("主机监控"),
            )
        )
        info_list.append(
            dict(
                monitor_target=models.proc_port_index.real_id,
                description=models.proc_port_index.desc,
                monitor_type=models.proc_port_index.category,
                scenario=_("主机监控"),
            )
        )
        info_list.append(
            dict(
                monitor_target=models.custom_str_index.real_id,
                description=models.custom_str_index.desc,
                monitor_type=models.custom_str_index.category,
                scenario=_("主机监控"),
            )
        )

        # 内置
        info_list += [
            dict(
                monitor_target="",
                description=c.get("category_display", ""),
                monitor_type=c["category"],
                scenario=_("组件"),
            )
            for c in []
            if "category" in c and c["category"] != "system"
        ]
        # 自定义组件监控
        components = []
        component_names = []
        for c in components:
            if c.component_name in component_names:
                continue
            component_names.append(c.component_name)
            info_list.append(
                dict(
                    monitor_target="",
                    description=c.component_name_display,
                    monitor_type=c.component_name,
                    scenario=_("组件"),
                )
            )
        # 物理机
        info_list += [
            dict(
                monitor_target="",
                description=_("物理机") + "-%s" % fields.get(_t, _t),
                monitor_type="%s" % _t,
                scenario=_("组件"),
            )
            for _t in ["cpu", "disk", "net", "mem", "system_env", "process"]
        ]
        # 脚本采集
        info_list += [
            dict(monitor_target="", description=_("脚本采集"), monitor_type=SHELL_COLLECTOR_DB, scenario=_("脚本采集"))
        ]
        # 自定义监控
        info_list += [dict(monitor_target="", description=_("自定义监控"), monitor_type="custom", scenario=_("自定义监控"))]
        # 服务拨测
        info_list += [dict(monitor_target="", description=_("服务拨测"), monitor_type=UPTIME_CHECK_DB, scenario=_("服务拨测"))]
        return Response(info_list)
