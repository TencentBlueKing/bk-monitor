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
import logging
import mimetypes
import os
import posixpath
from urllib.parse import unquote

from bkstorages.utils import safe_join
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404, StreamingHttpResponse
from django.template import Context, Template
from rest_framework import permissions

from bkmonitor.iam import ActionEnum, Permission
from bkmonitor.iam.drf import BusinessActionPermission, IAMPermission
from bkmonitor.models import EventPluginV2
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from core.errors.iam import PermissionDeniedError
from fta_web.event_plugin.handler import PackageHandler
from fta_web.event_plugin.resources import GetEventPluginTokenResource

logger = logging.getLogger(__name__)


class EventPluginViewSet(ResourceViewSet):
    def check_permissions(self, request):
        if self.request.method in permissions.SAFE_METHODS:
            permission = BusinessActionPermission([ActionEnum.VIEW_BUSINESS])
            # 有采集管理权限的人员，也可以接入告警源
        else:
            permission = IAMPermission([ActionEnum.MANAGE_GLOBAL_SETTING])
        try:
            permission.has_permission(request, self)
            return
        except PermissionDeniedError:
            permission = BusinessActionPermission([ActionEnum.MANAGE_COLLECTION])
        permission.has_permission(request, self)

    resource_routes = [
        ResourceRoute("GET", resource.event_plugin.list_event_plugin),
        ResourceRoute("GET", resource.event_plugin.get_event_plugin, pk_field="plugin_id"),
        ResourceRoute("POST", resource.event_plugin.deploy_event_plugin),
        ResourceRoute("POST", resource.event_plugin.create_event_plugin),
        ResourceRoute("POST", resource.event_plugin.import_event_plugin, endpoint="import"),
        ResourceRoute("PUT", resource.event_plugin.update_event_plugin, pk_field="plugin_id"),
        ResourceRoute("DELETE", resource.event_plugin.delete_event_plugin, pk_field="plugin_id"),
        ResourceRoute(
            "GET", resource.event_plugin.get_event_plugin_instance, endpoint="instances", pk_field="plugin_id"
        ),
        ResourceRoute("GET", resource.event_plugin.tail_event_plugin_data, endpoint="tail", pk_field="plugin_id"),
        ResourceRoute(
            "POST",
            resource.event_plugin.create_event_plugin_instance,
            endpoint="instance/install",
            pk_field="plugin_id",
        ),
        ResourceRoute("PUT", resource.event_plugin.update_event_plugin_instance, endpoint="instance", pk_field="id"),
        ResourceRoute("GET", resource.event_plugin.get_event_plugin_token, endpoint="instance/token", pk_field="id"),
        ResourceRoute("POST", resource.event_plugin.disable_plugin_collect, endpoint="instance/disable_collect"),
    ]


def serve(request, path, document_root=None, *args, **kwargs):
    path = posixpath.normpath(unquote(path)).lstrip("/")
    fullpath = safe_join(document_root, path)
    if not default_storage.exists(fullpath):
        raise Http404("'%s' does not exist" % fullpath)

    content_type, encoding = mimetypes.guess_type(fullpath)
    content_type = content_type or "application/octet-stream"
    response = FileResponse(default_storage.open(fullpath), content_type=content_type)
    if encoding:
        response["Content-Encoding"] = encoding
    return response


def event_plugin_media(*args, **kwargs):
    """
    处理插件包中的静态文件转发
    """
    plugin_id = kwargs.pop("plugin_id")
    plugin_obj = EventPluginV2.objects.get(plugin_id=plugin_id, is_latest=True)
    plugin = resource.event_plugin.get_event_plugin(plugin_id=plugin_id, version=plugin_obj.version)
    plugin_instances = resource.event_plugin.get_event_plugin_instance(
        plugin_id=plugin_id, bk_biz_id=plugin_obj.bk_biz_id, version=plugin_obj.version
    )
    document_root = os.path.join(PackageHandler.get_media_root(), plugin["package_dir"])
    response = serve(document_root=document_root, *args, **kwargs)
    if response.get("Content-Type", "").startswith("text/"):
        # 如果是文本，可能需要对当中的占位符进行替换
        try:
            # 需要请求token，因为脚本可能会包含token字段的引用

            # 在此之前，需要先做鉴权，避免token泄露
            permission = Permission()
            permission.is_allowed(ActionEnum.MANAGE_GLOBAL_SETTING, raise_exception=True)

            token = GetEventPluginTokenResource().request(id=plugin_instances["instances"][0]["id"]).get("token")
            plugin.update({"token": token})
        except Exception as e:
            logger.exception("[event_plugin_media] get token error: %s", e)
        try:
            plugin["ingest_config"]["push_url"] = plugin_instances["instances"][0].get("push_url", "")
        except Exception as e:
            logger.exception("[event_plugin_media] get push_url error: %s", e)
        context = {"plugin": plugin}
        content = b"".join(response.streaming_content)
        try:
            template = Template(content.decode("utf-8"))
            content = template.render(Context(context))
        except Exception as e:
            logger.exception("[event_plugin_media] render content error: %s", e)
        return StreamingHttpResponse(content, content_type=response["Content-Type"])
    return response
