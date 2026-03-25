"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.translation import gettext as _
from rest_framework.decorators import action

from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from kernel_api.resource.collecting import CollectConfigInfoResource
from monitor_api.views import *  # noqa
from monitor_api.views import Response
from monitor_web.uptime_check.views import UptimeCheckGroupViewSet as _UptimeCheckGroupViewSet
from monitor_web.uptime_check.views import UptimeCheckNodeViewSet as _UptimeCheckNodeModelViewSet
from monitor_web.uptime_check.views import UptimeCheckTaskViewSet as _UptimeCheckTaskModelViewSet


class UptimeCheckNodeViewSet(_UptimeCheckNodeModelViewSet):
    @action(methods=["POST"], detail=False)
    def delete(self, request, *args, **kwargs):
        pk = request.data.get("node_id")
        super().destroy(request, pk)
        return Response({"id": pk, "result": _("删除成功")})

    @action(methods=["POST"], detail=False)
    def edit(self, request, *args, **kwargs):
        pk = request.data.get("node_id")
        return super().update(request, pk, *args, **kwargs)

    @action(methods=["POST"], detail=False)
    def add(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)


class UptimeCheckTaskViewSet(_UptimeCheckTaskModelViewSet):
    @action(methods=["POST"], detail=False)
    def delete(self, request, *args, **kwargs):
        pk = request.data.get("task_id")
        super().destroy(request, pk)
        return Response({"id": pk, "result": _("删除成功")})

    @action(methods=["POST"], detail=False)
    def edit(self, request, *args, **kwargs):
        pk = request.data.get("task_id")
        return super().update(request, pk, *args, **kwargs)

    @action(methods=["POST"], detail=False)
    def add(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @action(methods=["POST"], detail=False)
    def deploy(self, request, *args, **kwargs):
        pk = request.data.get("task_id")
        return super().deploy(request, pk)

    @action(methods=["POST"], detail=False)
    def change_status(self, request, *args, **kwargs):
        pk = request.data.get("task_id")
        return super().change_status(request, pk)


class UptimeCheckGroupViewSet(_UptimeCheckGroupViewSet):
    @action(methods=["POST"], detail=False)
    def add(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @action(methods=["POST"], detail=False)
    def delete(self, request, *args, **kwargs):
        pk = request.data.get("group_id")
        super().destroy(request, pk)
        return Response({"group_id": pk, "result": _("删除成功")})

    @action(methods=["POST"], detail=False)
    def edit(self, request, *args, **kwargs):
        pk = request.data.get("group_id")
        return super().update(request, pk)

    @action(methods=["POST"], detail=False)
    def add_task(self, request, *args, **kwargs):
        pk = request.data.get("group_id")
        return super().add_task(request, pk)

    @action(methods=["POST"], detail=False)
    def remove_task(self, request, *args, **kwargs):
        pk = request.data.get("group_id")
        return super().remove_task(request, pk)


class CollectConfigViewSet(ResourceViewSet):
    resource_routes = [ResourceRoute("GET", CollectConfigInfoResource)]
