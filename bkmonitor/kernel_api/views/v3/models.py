# -*- coding: utf-8 -*-
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
from monitor_api.views import Response, viewsets
from monitor_web.uptime_check.views import (
    UptimeCheckGroupViewSet as _UptimeCheckGroupViewSet,
)
from monitor_web.uptime_check.views import (
    UptimeCheckNodeViewSet as _UptimeCheckNodeModelViewSet,
)
from monitor_web.uptime_check.views import (
    UptimeCheckTaskViewSet as _UptimeCheckTaskModelViewSet,
)


class ModelMixin(viewsets.ModelViewSet):
    @action(methods=["POST"], detail=True)
    def delete(self, request, *args, **kwargs):
        obj_id = self.get_object().id
        super(ModelMixin, self).destroy(request, *args, **kwargs)
        return Response({"id": obj_id, "result": _("删除成功")})

    @action(methods=["POST"], detail=True)
    def edit(self, request, *args, **kwargs):
        kwargs.update({"partial": True})
        return super(ModelMixin, self).update(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        data = super(ModelMixin, self).create(request, *args, **kwargs).data
        # 使状态码返回为200，而不是201
        return Response(data)


class UptimeCheckNodeViewSet(_UptimeCheckNodeModelViewSet):
    @action(methods=["POST"], detail=False)
    def delete(self, request, *args, **kwargs):
        self.kwargs["pk"] = request.data.get("node_id")
        super(UptimeCheckNodeViewSet, self).destroy(request, *args, **kwargs)
        return Response({"id": self.kwargs["pk"], "result": _("删除成功")})

    @action(methods=["POST"], detail=False)
    def edit(self, request, *args, **kwargs):
        self.kwargs["pk"] = request.data.get("node_id")
        self.kwargs.update({"partial": True})
        return super(UptimeCheckNodeViewSet, self).update(request, *args, **kwargs)

    @action(methods=["POST"], detail=False)
    def add(self, request, *args, **kwargs):
        return super(UptimeCheckNodeViewSet, self).create(request, *args, **kwargs)


class UptimeCheckTaskViewSet(_UptimeCheckTaskModelViewSet):
    @action(methods=["POST"], detail=False)
    def delete(self, request, *args, **kwargs):
        self.kwargs["pk"] = request.data.get("task_id")
        super(UptimeCheckTaskViewSet, self).destroy(request, *args, **kwargs)
        return Response({"id": self.kwargs["pk"], "result": _("删除成功")})

    @action(methods=["POST"], detail=False)
    def edit(self, request, *args, **kwargs):
        self.kwargs["pk"] = request.data.get("task_id")
        self.kwargs.update({"partial": True})
        return super(UptimeCheckTaskViewSet, self).update(request, *args, **kwargs)

    @action(methods=["POST"], detail=False)
    def add(self, request, *args, **kwargs):
        return super(UptimeCheckTaskViewSet, self).create(request, *args, **kwargs)

    @action(methods=["POST"], detail=False)
    def deploy(self, request, *args, **kwargs):
        self.kwargs["pk"] = request.data.get("task_id")
        return super(UptimeCheckTaskViewSet, self).deploy(request, *args, **kwargs)

    @action(methods=["POST"], detail=False)
    def change_status(self, request, *args, **kwargs):
        self.kwargs["pk"] = request.data.get("task_id")
        self.kwargs["status"] = request.data.get("status", "")
        return super(UptimeCheckTaskViewSet, self).change_status(request, *args, **kwargs)


class UptimeCheckGroupViewSet(_UptimeCheckGroupViewSet):
    @action(methods=["POST"], detail=False)
    def add(self, request, *args, **kwargs):
        return super(UptimeCheckGroupViewSet, self).create(request, *args, **kwargs)

    @action(methods=["POST"], detail=False)
    def delete(self, request, *args, **kwargs):
        self.kwargs["pk"] = request.data.get("group_id")
        super(UptimeCheckGroupViewSet, self).destroy(request, *args, **kwargs)
        return Response({"group_id": self.kwargs["pk"], "result": _("删除成功")})

    @action(methods=["POST"], detail=False)
    def edit(self, request, *args, **kwargs):
        self.kwargs["pk"] = request.data.get("group_id")
        self.kwargs.update({"partial": True})
        return super(UptimeCheckGroupViewSet, self).update(request, *args, **kwargs)

    @action(methods=["POST"], detail=False)
    def add_task(self, request, *args, **kwargs):
        self.kwargs["pk"] = request.data.get("group_id")
        return super(UptimeCheckGroupViewSet, self).add_task(request, *args, **kwargs)

    @action(methods=["POST"], detail=False)
    def remove_task(self, request, *args, **kwargs):
        self.kwargs["pk"] = request.data.get("group_id")
        return super(UptimeCheckGroupViewSet, self).remove_task(request, *args, **kwargs)


class CollectConfigViewSet(ResourceViewSet):
    resource_routes = [ResourceRoute("GET", CollectConfigInfoResource)]
