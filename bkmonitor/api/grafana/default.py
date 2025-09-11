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

import json
import logging
from random import randint
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.utils.translation import gettext as _
from rest_framework import serializers

from core.drf_resource import Resource
from core.errors.api import BKAPIError

logger = logging.getLogger(__name__)


class GrafanaApiResource(Resource):
    """
    Grafana
    """

    method = ""
    path = ""
    with_org_id = False

    def perform_request(self, params):
        url = urljoin(settings.GRAFANA_URL, self.path.format(**params))

        if isinstance(self.method, tuple):
            method = self.method[0]
        else:
            method = self.method

        if "username" in params:
            username = params["username"]
        else:
            username = "admin"

        requests_params = {"method": method, "url": url, "headers": {"X-WEBAUTH-USER": username}}

        # 对于非Admin API，通过参数在请求头注入org_id
        if self.with_org_id:
            if "org_id" not in params:
                raise BKAPIError(system_name="grafana", url=url, result=_("请求缺少org_id"))

            requests_params["headers"]["X-Grafana-Org-Id"] = str(params["org_id"])
            del params["org_id"]

        if method in ["PUT", "POST", "PATCH"]:
            requests_params["json"] = params
        elif method in ["GET", "HEAD", "DELETE"]:
            requests_params["params"] = params
        r = requests.request(**requests_params)

        result = r.status_code in [200, 204]
        if result:
            data = r.json()
            message = ""
        else:
            data = None
            try:
                message = r.json()["message"]
            except json.decoder.JSONDecodeError:
                message = r.content
        return {"result": result, "code": r.status_code, "message": message, "data": data}


class CreateUser(GrafanaApiResource):
    method = "POST"
    path = "/api/admin/users/"

    class RequestSerializer(serializers.Serializer):
        name = serializers.CharField(required=True, max_length=64)
        email = serializers.EmailField(required=False)
        login = serializers.CharField(required=True, max_length=32)
        password = serializers.CharField(required=False, default=lambda: str(randint(100000000, 999999999)))


class GetOrganizationByName(GrafanaApiResource):
    method = "GET"
    path = "/api/orgs/name/{name}"

    class RequestSerializer(serializers.Serializer):
        name = serializers.CharField(required=True)


class GetOrganizationByID(GrafanaApiResource):
    method = "GET"
    path = "/api/orgs/{id}"

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=True)


class GetAllOrganization(GrafanaApiResource):
    method = "GET"
    path = "/api/orgs/"

    class RequestSerializer(serializers.Serializer):
        perpage = serializers.IntegerField(required=False, default=20000)


class CreateOrUpdateDashboard(GrafanaApiResource):
    method = "POST"
    path = "/api/dashboards/db/"
    with_org_id = True

    class RequestSerializer(serializers.Serializer):
        dashboard = serializers.DictField()
        org_id = serializers.IntegerField()
        folderId = serializers.IntegerField(default=0)


class UpdateOrganizationPreference(GrafanaApiResource):
    method = "PUT"
    path = "/api/org/preferences/"
    with_org_id = True

    class RequestSerializer(serializers.Serializer):
        homeDashboardId = serializers.IntegerField()
        org_id = serializers.IntegerField()


class PatchOrganizationPreference(GrafanaApiResource):
    method = "PATCH"
    path = "/api/org/preferences/"
    with_org_id = True

    class RequestSerializer(serializers.Serializer):
        homeDashboardId = serializers.IntegerField(required=False)
        org_id = serializers.IntegerField(required=False)


class GetOrganizationPreference(GrafanaApiResource):
    method = "GET"
    path = "/api/org/preferences/"
    with_org_id = True

    class RequestSerializer(serializers.Serializer):
        org_id = serializers.IntegerField()


class CreateDataSource(GrafanaApiResource):
    method = "POST"
    path = "/api/datasources/"
    with_org_id = True

    class RequestSerializer(serializers.Serializer):
        org_id = serializers.IntegerField()
        name = serializers.CharField()
        type = serializers.CharField()
        url = serializers.CharField(required=False)
        access = serializers.CharField(default="direct")
        basicAuth = serializers.BooleanField(default=False)
        jsonData = serializers.DictField(required=False)
        isDefault = serializers.BooleanField(default=False)


class GetAllDataSource(GrafanaApiResource):
    method = "GET"
    path = "/api/datasources"
    with_org_id = True

    class RequestSerializer(serializers.Serializer):
        org_id = serializers.IntegerField()


class CreateFolder(GrafanaApiResource):
    method = "POST"
    path = "/api/folders/"
    with_org_id = True

    class RequestSerializer(serializers.Serializer):
        org_id = serializers.IntegerField()
        uid = serializers.CharField(required=False)
        title = serializers.CharField()


class SearchFolderOrDashboard(GrafanaApiResource):
    """
    https://grafana.com/docs/grafana/latest/http_api/folder_dashboard_search/#search-folders-and-dashboards
    """

    method = "GET"
    path = "/api/search/"
    with_org_id = True

    class RequestSerializer(serializers.Serializer):
        org_id = serializers.IntegerField()
        type = serializers.CharField(required=False)
        query = serializers.CharField(required=False)
        tag = serializers.CharField(required=False)
        starred = serializers.CharField(required=False)
        limit = serializers.IntegerField(required=False)
        page = serializers.IntegerField(required=False)
        folderIds = serializers.ListField(required=False, child=serializers.IntegerField())
        dashboardIds = serializers.ListField(required=False, child=serializers.IntegerField())
        username = serializers.CharField(required=False, default="admin")


class GetDashboardByUID(GrafanaApiResource):
    method = "GET"
    path = "/api/dashboards/uid/{uid}"
    with_org_id = True

    class RequestSerializer(serializers.Serializer):
        org_id = serializers.IntegerField()
        uid = serializers.CharField()


class CreateOrUpdateDashboardByUID(GrafanaApiResource):
    method = "POST"
    path = "/api/dashboards/db"
    with_org_id = True

    class RequestSerializer(serializers.Serializer):
        org_id = serializers.IntegerField()
        dashboard = serializers.DictField()
        overwrite = serializers.BooleanField()
        folderId = serializers.IntegerField()


class ImportDashboard(GrafanaApiResource):
    method = "POST"
    path = "api/dashboards/import"
    with_org_id = True

    class RequestSerializer(serializers.Serializer):
        org_id = serializers.IntegerField()
        pluginId = serializers.CharField(required=False, default=None)
        path = serializers.CharField(required=False, default=None)
        dashboard = serializers.DictField()
        folderId = serializers.IntegerField(required=False, default=0)
        inputs = serializers.ListField(required=False, default=[])
        overwrite = serializers.BooleanField(required=False, default=True)


class ListFolder(GrafanaApiResource):
    method = "GET"
    path = "/api/folders/"
    with_org_id = True

    class RequestSerializer(serializers.Serializer):
        org_id = serializers.IntegerField()


class DeleteFolder(GrafanaApiResource):
    method = "DELETE"
    path = "/api/folders/{uid}/"
    with_org_id = True

    class RequestSerializer(serializers.Serializer):
        org_id = serializers.IntegerField()
        uid = serializers.CharField()


class UpdateFolder(GrafanaApiResource):
    method = "PUT"
    path = "/api/folders/{uid}/"
    with_org_id = True

    class RequestSerializer(serializers.Serializer):
        org_id = serializers.IntegerField()
        uid = serializers.CharField()
        title = serializers.CharField()
        version = serializers.IntegerField(required=False, default=1)


class GetFolderByUID(GrafanaApiResource):
    method = "GET"
    path = "/api/folders/{uid}/"
    with_org_id = True

    class RequestSerializer(serializers.Serializer):
        org_id = serializers.IntegerField()
        uid = serializers.CharField()


class DeleteDashboardByUID(GrafanaApiResource):
    method = "DELETE"
    path = "/api/dashboards/uid/{uid}/"
    with_org_id = True

    class RequestSerializer(serializers.Serializer):
        org_id = serializers.IntegerField()
        uid = serializers.CharField()


class StarDashboard(GrafanaApiResource):
    method = "POST"
    path = "/api/user/stars/dashboard/{id}"
    with_org_id = True

    class RequestSerializer(serializers.Serializer):
        org_id = serializers.IntegerField()
        id = serializers.CharField()
        username = serializers.CharField(required=False, default="admin")


class UnstarDashboard(GrafanaApiResource):
    method = "DELETE"
    path = "/api/user/stars/dashboard/{id}"
    with_org_id = True

    class RequestSerializer(serializers.Serializer):
        org_id = serializers.IntegerField()
        id = serializers.CharField()
        username = serializers.CharField(required=False, default="admin")
