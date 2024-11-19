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
from collections import defaultdict
from typing import Dict

from blueapps.utils import get_request
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from bk_dataview.api import get_or_create_org
from bk_dataview.permissions import GrafanaPermission, GrafanaRole
from core.drf_resource import Resource, api
from core.errors.dashboard import GetFolderOrDashboardError
from monitor_web.grafana.auth import GrafanaAuthSync
from monitor_web.grafana.permissions import DashboardPermission


class GetDashboardList(Resource):
    """
    查询仪表盘列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        is_report = serializers.BooleanField(label="是否订阅报表请求接口", default=False, required=False)
        is_starred = serializers.BooleanField(label="是否收藏", required=False)

    def perform_request(self, params):
        org_id = GrafanaAuthSync.get_or_create_org_id(params["bk_biz_id"])

        try:
            username = get_request().user.username
            if params["is_report"]:
                username = "admin"
        except Exception:
            username = "admin"

        request_params = {"type": "dash-db", "org_id": org_id, "username": username}
        if "is_starred" in params:
            request_params["starred"] = "true" if params["is_starred"] else "false"
        result = api.grafana.search_folder_or_dashboard(**request_params)

        if result["result"]:
            dashboards = result["data"]
        else:
            raise GetFolderOrDashboardError(**result)

        return [
            {
                "id": dashboard["id"],
                "uid": dashboard["uid"],
                "text": (f"{dashboard['folderTitle']}/" if "folderTitle" in dashboard else "") + dashboard["title"],
                "folder_uid": dashboard.get("folderUid", ""),
                "folder_title": dashboard.get("folderTitle", ""),
                "name": dashboard["title"],
                "is_starred": dashboard["isStarred"],
            }
            for dashboard in dashboards
        ]


class GetDirectoryTree(Resource):
    """
    查询目录树
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")

    def perform_request(self, params):
        org_id = get_or_create_org(params["bk_biz_id"])["id"]
        request = get_request()

        result = api.grafana.search_folder_or_dashboard(org_id=org_id)
        if not result:
            raise GetFolderOrDashboardError(**result)

        # 获取仪表盘权限
        _, role, dashboard_permissions = DashboardPermission.has_permission(request, None, params["bk_biz_id"])

        folders: Dict[int, Dict] = defaultdict(lambda: {"dashboards": []})

        # 补充默认目录
        folders[0].update(
            {"id": 0, "uid": "", "title": "General", "uri": "", "url": "", "slug": "", "tags": [], "isStarred": False}
        )

        for record in result["data"]:
            _type = record.pop("type", "")
            if _type == "dash-folder":
                folders[record["id"]].update(record)
            elif _type == "dash-db":
                # 过滤仪表盘权限
                if getattr(request, "external_user", None) and record["uid"] not in dashboard_permissions:
                    continue
                # 仪表盘是否可编辑
                record["editable"] = (
                    role >= GrafanaRole.Editor
                    or dashboard_permissions.get(record["uid"], GrafanaPermission.View) >= GrafanaPermission.Edit
                )
                folder_id = record.pop("folderId", 0)
                record.pop("folderUid", None)
                record.pop("folderTitle", None)
                record.pop("folderUrl", None)
                folders[folder_id]["dashboards"].append(record)

        return [folder for folder_id, folder in folders.items()]


class CreateDashboardOrFolder(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        title = serializers.CharField(label="名称")
        type = serializers.ChoiceField(label="类型", choices=(("dashboard", _("仪表盘")), ("folder", _("文件夹"))))
        folderId = serializers.IntegerField(label="文件夹ID", default=0)

    def perform_request(self, params):
        org_id = GrafanaAuthSync.get_or_create_org_id(params["bk_biz_id"])

        if params["type"] == "folder":
            result = api.grafana.create_folder(org_id=org_id, title=params["title"])
        else:
            result = api.grafana.import_dashboard(
                dashboard={"title": params["title"], "tags": [], "timezone": "", "schemaVersion": 0},
                folderId=params["folderId"],
                org_id=org_id,
            )

        return result


class DeleteDashboard(Resource):
    """
    删除指定仪表盘
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        uid = serializers.CharField(label="仪表盘ID")

    def perform_request(self, params):
        org_id = GrafanaAuthSync.get_or_create_org_id(params["bk_biz_id"])
        result = api.grafana.delete_dashboard_by_uid(org_id=org_id, uid=params["uid"])
        return result


class StarDashboard(Resource):
    """
    收藏指定仪表盘
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        dashboard_id = serializers.CharField(label="仪表盘ID")

    def perform_request(self, params):
        org_id = GrafanaAuthSync.get_or_create_org_id(params["bk_biz_id"])
        username = get_request().user.username
        result = api.grafana.star_dashboard(org_id=org_id, id=params["dashboard_id"], username=username)
        return result


class UnstarDashboard(Resource):
    """
    取消收藏指定仪表盘
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        dashboard_id = serializers.CharField(label="仪表盘ID")

    def perform_request(self, params):
        org_id = GrafanaAuthSync.get_or_create_org_id(params["bk_biz_id"])
        username = get_request().user.username
        result = api.grafana.unstar_dashboard(org_id=org_id, id=params["dashboard_id"], username=username)
        return result


class GetDefaultDashboard(Resource):
    """
    查询当前默认仪表盘
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")

    def perform_request(self, params):
        org_id = GrafanaAuthSync.get_or_create_org_id(params["bk_biz_id"])
        result = api.grafana.get_organization_preference(org_id=org_id)

        if not result["result"]:
            return result

        home_dashboard_id = result["data"]["homeDashboardId"]
        if not home_dashboard_id:
            return {}

        result = api.grafana.search_folder_or_dashboard(type="dash-db", org_id=org_id, dashboardIds=[home_dashboard_id])

        if result["result"] and result["data"]:
            return result["data"][0]

        return {}


class SetDefaultDashboard(Resource):
    """
    设置默认仪表盘
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        dashboard_uid = serializers.CharField(label="仪表盘ID")

    def perform_request(self, params):
        org_id = GrafanaAuthSync.get_or_create_org_id(params["bk_biz_id"])
        result = api.grafana.search_folder_or_dashboard(type="dash-db", org_id=org_id)

        if result["result"]:
            dashboards = result["data"]
        else:
            return {
                "result": result["result"],
                "code": result["code"],
                "message": result["message"],
            }

        for dashboard in dashboards:
            if dashboard["uid"] == params["dashboard_uid"]:
                return api.grafana.patch_organization_preference(org_id=org_id, homeDashboardId=dashboard["id"])
        return {"result": False, "message": _("设置失败，找不到该仪表盘")}


class DeleteFolder(Resource):
    """
    删除指定目录
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        uid = serializers.CharField(label="目录ID")

    def perform_request(self, params):
        org_id = GrafanaAuthSync.get_or_create_org_id(params["bk_biz_id"])
        result = api.grafana.delete_folder(org_id=org_id, uid=params["uid"])
        return result


class RenameFolder(Resource):
    """
    重命名指定目录
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        uid = serializers.CharField(label="目录ID")
        title = serializers.CharField(label="目录名称")

    def perform_request(self, params):
        org_id = GrafanaAuthSync.get_or_create_org_id(params["bk_biz_id"])
        folder_data = api.grafana.get_folder_by_uid(org_id=org_id, uid=params["uid"])
        current_version = folder_data["data"].get("version", 1)
        result = api.grafana.update_folder(
            org_id=org_id, uid=params["uid"], title=params["title"], version=current_version
        )
        return result


class QuickImportDashboard(Resource):
    """
    仪表盘快捷导入
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        dash_name = serializers.CharField(label="仪表盘名称")
        folder_name = serializers.CharField(label="仪表盘文件夹名称", default="")

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]
        dash_name = params["dash_name"]
        if not dash_name.endswith(".json"):
            dash_name += ".json"
        folder_name = params["folder_name"]
        folder_id = 0
        org_id = GrafanaAuthSync.get_or_create_org_id(bk_biz_id)
        # 确定存放目录
        if folder_name and folder_name != "General":
            folder_list = api.grafana.search_folder_or_dashboard(type="dash-folder", org_id=org_id, query=folder_name)[
                "data"
            ]
            folder_list = [fold["id"] for fold in folder_list if fold["title"] == folder_name]
            if folder_list:
                folder_id = folder_list[0]

        from monitor_web.grafana.provisioning import BkMonitorProvisioning

        # 寻找对应仪表盘文件
        if not BkMonitorProvisioning.create_default_dashboard(
            org_id, json_name=dash_name, folder_id=folder_id, bk_biz_id=bk_biz_id
        ):
            raise ImportError(f"bk_biz_id[{bk_biz_id}], quick import dashboard[{dash_name}] failed")

        return
