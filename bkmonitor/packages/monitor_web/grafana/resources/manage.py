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
import traceback
from collections import defaultdict, namedtuple
from copy import deepcopy
from typing import Any

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from bk_dataview.api import get_or_create_org
from bk_dataview.models import Dashboard
from bk_dataview.permissions import GrafanaPermission, GrafanaRole
from bkmonitor.models.strategy import QueryConfigModel, StrategyModel
from bkmonitor.utils.request import get_request
from constants.data_source import DataSourceLabel
from core.drf_resource import Resource, api, resource
from core.errors.dashboard import GetFolderOrDashboardError
from monitor.models.models import ApplicationConfig
from monitor_web.grafana.permissions import DashboardPermission
from monitor_web.tasks import migrate_all_panels_task

logger = logging.getLogger(__name__)


class GetDashboardList(Resource):
    """
    查询仪表盘列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        is_report = serializers.BooleanField(label="是否订阅报表请求接口", default=False, required=False)
        is_starred = serializers.BooleanField(label="是否收藏", required=False)

    def perform_request(self, params):
        org_id = get_or_create_org(params["bk_biz_id"])["id"]

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
                "url": dashboard["url"],
                "uri": dashboard["uri"],
                "tags": dashboard["tags"],
            }
            for dashboard in dashboards
        ]


class GetDirectoryTree(Resource):
    """
    查询目录树
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        filter_no_permission = serializers.BooleanField(label="是否过滤无权限的仪表盘", default=False)

    def perform_request(self, params):
        org_id = get_or_create_org(params["bk_biz_id"])["id"]
        request = get_request(peaceful=True)
        if not request:
            raise GetFolderOrDashboardError(code=200, message="lack of request")

        result = api.grafana.search_folder_or_dashboard(org_id=org_id)
        if not result:
            raise GetFolderOrDashboardError(**result)

        # 获取仪表盘权限 （包含 folder 展开后的 Dashboard）
        _, role, dashboard_permissions = DashboardPermission.has_permission(
            request, None, params["bk_biz_id"], force_check=True
        )

        folders: dict[int, dict] = defaultdict(lambda: {"dashboards": []})

        # 补充默认目录
        folders[0].update(
            {"id": 0, "uid": "", "title": "General", "uri": "", "url": "", "slug": "", "tags": [], "isStarred": False}
        )

        # 是否过滤无权限的仪表盘
        is_external_user = getattr(request, "external_user", False)
        filter_no_permission = params.get("filter_no_permission", False) or is_external_user

        for record in result["data"]:
            _type = record.pop("type", "")
            if _type == "dash-folder":
                folders[record["id"]].update(record)
            elif _type == "dash-db":
                # 过滤无权限的仪表盘
                if (
                    filter_no_permission
                    and record["uid"] not in dashboard_permissions
                    and (role < GrafanaRole.Viewer or is_external_user)
                ):
                    continue
                # 仪表盘是否可编辑
                record["editable"] = (
                    role >= GrafanaRole.Editor
                    or dashboard_permissions.get(record["uid"], GrafanaPermission.View) >= GrafanaPermission.Edit
                )
                # 是否有权限
                record["has_permission"] = role > GrafanaRole.Anonymous or record["uid"] in dashboard_permissions
                folder_id = record.pop("folderId", 0)
                record.pop("folderUid", None)
                record.pop("folderTitle", None)
                record.pop("folderUrl", None)
                folders[folder_id]["dashboards"].append(record)

        # 判断目录权限
        for folder_id, folder_data in folders.items():
            dashboards = folder_data["dashboards"]
            # 目录权限 = 角色权限 或 拥有当前目录下所有仪表盘权限
            folder_data["has_folder_permission"] = role >= GrafanaRole.Viewer or (
                len(dashboards) > 0 and all(d.get("has_permission", False) for d in dashboards)
            )

        # 清理空目录
        if filter_no_permission:
            folders = {k: v for k, v in folders.items() if v["dashboards"]}

        return list(folders.values())


class CreateDashboardOrFolder(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        title = serializers.CharField(label="名称")
        type = serializers.ChoiceField(label="类型", choices=(("dashboard", _("仪表盘")), ("folder", _("文件夹"))))
        folderId = serializers.IntegerField(label="文件夹ID", default=0)

    def perform_request(self, params):
        org_id = get_or_create_org(params["bk_biz_id"])["id"]

        if params["type"] == "folder":
            result = api.grafana.create_folder(org_id=org_id, title=params["title"])
        else:
            result = api.grafana.import_dashboard(
                dashboard={"title": params["title"], "tags": [], "timezone": "", "schemaVersion": 0},
                folderId=params["folderId"],
                org_id=org_id,
            )

        return result


class GetDashboardDetail(Resource):
    """
    获取仪表盘详情
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        dashboard_uid = serializers.CharField(label="仪表盘UID")

    def perform_request(self, params):
        org_id = get_or_create_org(params["bk_biz_id"])["id"]

        dashboard = Dashboard.objects.filter(org_id=org_id, uid=params["dashboard_uid"], is_folder=0).first()
        if not dashboard:
            return None

        return {
            "id": dashboard.id,
            "uid": dashboard.uid,
            "title": dashboard.title,
            "data": dashboard.data,
            "version": dashboard.version,
            "slug": dashboard.slug,
        }


class DeleteDashboard(Resource):
    """
    删除指定仪表盘
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        uid = serializers.CharField(label="仪表盘ID")

    def perform_request(self, params):
        org_id = get_or_create_org(params["bk_biz_id"])["id"]
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
        org_id = get_or_create_org(params["bk_biz_id"])["id"]
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
        org_id = get_or_create_org(params["bk_biz_id"])["id"]
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
        org_id = get_or_create_org(params["bk_biz_id"])["id"]
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
        org_id = get_or_create_org(params["bk_biz_id"])["id"]
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
        org_id = get_or_create_org(params["bk_biz_id"])["id"]
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
        org_id = get_or_create_org(params["bk_biz_id"])["id"]
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
        org_id = get_or_create_org(bk_biz_id)["id"]
        # 确定存放目录
        if folder_name and folder_name != "General":
            folder_list = api.grafana.search_folder_or_dashboard(type="dash-folder", org_id=org_id, query=folder_name)[
                "data"
            ]
            folder_list = [fold["id"] for fold in folder_list if fold["title"] == folder_name]
            if folder_list:
                folder_id = folder_list[0]
            else:
                # 当前业务下, 目录不存在, 创建目录
                folder_id = api.grafana.create_folder(org_id=org_id, title=folder_name)["data"]["id"]

        from monitor_web.grafana.provisioning import BkMonitorProvisioning

        # 寻找对应仪表盘文件
        if not BkMonitorProvisioning.create_default_dashboard(
            org_id, json_name=dash_name, folder_id=folder_id, bk_biz_id=bk_biz_id
        ):
            raise ImportError(f"bk_biz_id[{bk_biz_id}], quick import dashboard[{dash_name}] failed")

        return


class CopyDashboardToFolder(Resource):
    """
    将指定仪表盘复制到指定目录
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID", required=True)
        dashboard_uid = serializers.CharField(label="源仪表盘UID", required=True)
        folder_id = serializers.IntegerField(label="目标目录ID", required=True)

    def perform_request(self, params):
        # 1. 获取源仪表盘信息
        org_id = get_or_create_org(params["bk_biz_id"])["id"]
        dashboard_info = api.grafana.get_dashboard_by_uid(org_id=org_id, uid=params["dashboard_uid"])
        dashboard = dashboard_info.get("data", {}).get("dashboard")

        # 没有获取到源仪表盘信息，直接返回
        if not dashboard:
            return {
                "result": False,
                "message": f"Copy failed. The dashboard information could not be found. "
                f"dashboard_uid: {params['dashboard_uid']}",
                "code": 200,
                "data": {},
            }

        # 移除仪表盘信息中的唯一标识符uid和id
        dashboard.pop("uid", None)
        dashboard.pop("id", None)
        # 不覆盖已存在的同名仪表盘，如果存在同名仪表盘，修改名称以避免覆盖
        existed_dashboards = resource.grafana.get_dashboard_list(bk_biz_id=params["bk_biz_id"])
        existed_titles = {dashboard["name"] for dashboard in existed_dashboards}
        while dashboard["title"] in existed_titles:
            dashboard["title"] = f"{dashboard['title']}_copy"

        # 2. 复制仪表盘到目标目录
        result = api.grafana.import_dashboard(
            dashboard=dashboard,
            folderId=params["folder_id"],
            org_id=org_id,
        )

        if not result["result"]:
            return {
                "result": False,
                "message": f"Dashboard_uid: {params['dashboard_uid']} Copy failed. {result['message']}",
                "code": result["code"],
                "data": {},
            }

        return {
            "result": True,
            "message": "Copy success.",
            "code": result["code"],
            "data": {"imported_url": result["data"].get("importedUrl", "")},
        }


class MigrateOldPanels(Resource):
    """
    将旧版 panels 迁移到新版本
    """

    PanelMigrationConfig = namedtuple("PanelMigrationConfig", ["old_type", "new_type", "method_name"])
    GRAPH_TO_TIMESERIES = PanelMigrationConfig("graph", "timeseries", "graph_to_timeseries")
    OLD_TABLE_TO_NEW = PanelMigrationConfig("table-old", "table", "oldtable_to_newtable")
    OLD_PIECHART_TO_NEW = PanelMigrationConfig("grafana-piechart-panel", "piechart", "old_piechart_to_new")
    PANEL_MIGRATIONS = [GRAPH_TO_TIMESERIES, OLD_TABLE_TO_NEW, OLD_PIECHART_TO_NEW]

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID", required=True)
        dashboard_uid = serializers.CharField(label="仪表盘UID", required=True)

    def graph_to_timeseries(self, panel: dict):
        """
        将旧版 graph 面板 迁移到新版本的 timeseries 面板
        """
        old_panel = deepcopy(panel)
        panel.clear()

        # panel 基本信息
        panel["id"] = old_panel["id"]
        panel["type"] = self.GRAPH_TO_TIMESERIES.new_type
        panel["title"] = old_panel.get("title", "Panel Title")
        panel["gridPos"] = old_panel["gridPos"]
        panel["datasource"] = old_panel["datasource"]
        panel["targets"] = old_panel["targets"]

        # 工具提示和图例迁移
        old_tooltip = old_panel.get("tooltip", {})
        short_map = {0: "none", 1: "asc", 2: "desc"}
        tooltip = {
            "mode": "multi" if old_tooltip.get("shared", False) is True else "single",
            "sort": short_map[old_tooltip.get("sort", 0)],
        }
        old_legend = old_panel.get("legend", {})
        calcs_map = {"avg": "mean", "min": "min", "max": "max", "total": "sum", "current": "last"}
        legend = {
            "showLegend": old_legend.get("show", True),
            "displayMode": "table" if old_legend.get("alignAsTable", False) is True else "list",
            "placement": "right" if old_legend.get("rightSide", False) is True else "bottom",
            "calcs": [new_calc for old_calc, new_calc in calcs_map.items() if old_legend.get(old_calc, False)],
        }
        panel["options"] = {"tooltip": tooltip, "legend": legend}

        # 图表上阈值标记模式："off":  不显示阈值效果；"line": 达到阈值的点上绘制一条线；"area": 在满足阈值区域填充颜色；
        # "line+area": 除了在图表中绘制一条代表阈值的线之外,还会填充颜色
        thresholds_style_mode = "off"
        # 阈值和对应显示的颜色
        threshold_steps = [{"color": "green", "value": None}]
        threshold_colors = [
            "red",
            "#EAB839",
            "#6ED0E0",
            "#EF843C",
            "#E24D42",
            "#1F78C1",
            "#BA43A9",
            "#705DA0",
            "#508642",
            "#CCA300",
            "#447EBC",
            "#C15C17",
            "#890F02",
            "#0A437C",
            "#6D1F62",
        ]
        color_index = 0
        for threshold in old_panel.get("thresholds", []):
            if threshold.get("op", "gt") == "lt":  # 当阈值条件为小于时，不显示该阈值, timeseries只有大于显示
                continue
            threshold_steps.append({"color": threshold_colors[color_index], "value": threshold.get("value")})
            color_index = (color_index + 1) % len(threshold_colors)
            if threshold.get("fill", False) is True and threshold.get("line", False) is True:
                thresholds_style_mode = "line+area"
            elif threshold.get("fill", False) is True:
                thresholds_style_mode = "area"
            elif threshold.get("line", False) is True:
                thresholds_style_mode = "line"
            else:
                thresholds_style_mode = "off"
        draw_style_map = {"lines": "line", "bars": "bars", "points": "points"}
        draw_style = "line"
        for old_style, new_style in draw_style_map.items():
            if old_panel.get(old_style, False):
                draw_style = new_style
                break
        custom = {
            # 以下使用timeseries默认值
            "axisBorderShow": False,
            "axisCenteredZero": False,
            "axisColorMode": "text",
            "axisLabel": "",
            "axisPlacement": "auto",
            "scaleDistribution": {"type": "linear"},
            "hideFrom": {"legend": False, "tooltip": False, "viz": False},
            "insertNulls": False,
            "showPoints": "auto",
            "barAlignment": 0,
            # 以下是与graph映射后的值
            "drawStyle": draw_style,
            "lineInterpolation": "stepAfter" if old_panel.get("steppedLine", False) is True else "smooth",
            "lineWidth": old_panel.get("lineWidth", 1),
            "fillOpacity": old_panel.get("fill", 0) * 10,
            "gradientMode": "none" if old_panel.get("fillGradient", 0) == 0 else "opacity",
            "spanNulls": True if old_panel.get("nullPointMode", "null") == "connected" else False,
            "pointSize": old_panel.get("pointradius", 2) * 4,
            "stacking": {"mode": "normal" if old_panel.get("stack", False) is True else "none", "group": "A"},
            "thresholdsStyle": {"mode": thresholds_style_mode},
        }
        # 自定义配置
        panel["fieldConfig"] = {
            "defaults": {
                "color": {"mode": "palette-classic"},
                "mapping": [],
                "thresholds": {"steps": threshold_steps, "mode": "absolute"},
                "custom": custom,
            },
            "overrides": [],
        }
        links = old_panel.get("fieldConfig", {}).get("defaults", {}).get("links", [])
        if links:
            panel["fieldConfig"]["defaults"]["links"] = links
        overrides = old_panel.get("fieldConfig", {}).get("overrides", [])
        if overrides:
            panel["fieldConfig"]["overrides"] = overrides

    def oldtable_to_newtable(self, panel: dict):
        """
        将旧版 table 面板 迁移到新版本的 table 面板
        """
        old_panel = deepcopy(panel)
        panel.clear()

        # panel 基本信息
        panel["id"] = old_panel["id"]
        panel["type"] = self.OLD_TABLE_TO_NEW.new_type
        panel["title"] = old_panel.get("title", "Panel Title")
        panel["gridPos"] = old_panel["gridPos"]
        panel["datasource"] = old_panel["datasource"]
        panel["targets"] = old_panel["targets"]

        # 表头和页脚配置
        panel["options"] = {
            "showHeader": old_panel.get("showHeader", True),
            "cellHeight": "sm",
            "footer": {"show": False, "reducer": ["sum"], "fields": "", "countRows": False, "enablePagination": False},
        }

        panel["fieldConfig"] = {
            "defaults": {
                "color": {"mode": "thresholds"},
                "mapping": [],
                "thresholds": {
                    "mode": "absolute",
                    "steps": [{"value": None, "color": "green"}, {"value": 80, "color": "red"}],
                },
                "custom": {"align": "auto", "cellOptions": {"type": "auto"}, "inspect": False},
            },
            "overrides": [],
        }
        for style in old_panel.get("styles", []):
            override = {"matcher": {"id": "byName", "options": style.get("pattern", "")}, "properties": []}

            alias = style.get("alias", "")
            if alias:
                override["properties"].append({"id": "displayName", "value": alias})

            align = style.get("align", "auto")
            if align != "auto":
                override["properties"].append({"id": "custom.align", "value": align})

            unit = style.get("unit", "")
            if unit:
                if style.get("type") == "date":
                    unit = f"time: {style.get('dateFormat', 'YYYY-MM-DD HH:mm:ss')}"
                override["properties"].append({"id": "unit", "value": unit})

            decimals = style.get("decimals")
            if decimals is not None:
                override["properties"].append({"id": "decimals", "value": decimals})

            panel["fieldConfig"]["overrides"].append(override)

    def old_piechart_to_new(self, panel: dict):
        """
        将旧版 piechart 面板 迁移到新版本的 piechart 面板
        """
        old_panel = deepcopy(panel)
        panel.clear()

        # panel 基本信息
        panel["id"] = old_panel["id"]
        panel["type"] = self.OLD_PIECHART_TO_NEW.new_type
        panel["title"] = old_panel.get("title", "Panel Title")
        panel["gridPos"] = old_panel["gridPos"]
        panel["datasource"] = old_panel["datasource"]
        panel["targets"] = old_panel["targets"]

        # 图例迁移
        old_legend = old_panel.get("legend", {})
        legend_type_map = {"Under graph": "bottom", "Right side": "right", "On graph": "right"}
        legend_values = []
        if old_legend.get("percentage"):
            legend_values.append("percent")
        if old_legend.get("values"):
            legend_values.append("value")
        legend = {
            "showLegend": old_legend.get("show", True),
            "displayMode": "table",  # 旧版没有这个相关配置字段，直接是表格形式展示
            "placement": legend_type_map[old_panel.get("legendType", "Right side")],
            "values": legend_values if legend_values else ["percent"],
        }
        panel["options"] = {
            # 以下是使用新版饼图的默认配置
            "reduceOptions": {"values": False, "calcs": ["lastNotNull"], "fields": ""},
            "tooltip": {"mode": "single", "sort": "none"},
            # 以下是与旧版饼图映射后的配置
            "legend": legend,
            "displayLabels": ["name", "value", "percent"] if old_panel.get("legendType") == "On graph" else [],
            "pieType": old_panel.get("pieType", "pie"),
        }

        # 自定义配置，使用新版饼图的默认配置
        panel["fieldConfig"] = {
            "defaults": {
                "custom": {"hideFrom": {"tooltip": False, "viz": False, "legend": False}},
                "color": {"mode": "palette-classic"},
                "mappings": [],
                "links": [],
            },
            "overrides": [],
        }

    def migrate_panel(self, panel: dict, is_migrate: bool, migrated_panels_details: dict):
        """
        将旧版 panels 迁移到新版本
        """
        panel_type = panel.get("type")
        old_panel = deepcopy(panel)

        for panel_migration in self.PANEL_MIGRATIONS:
            if panel_type == panel_migration.old_type:
                try:
                    migrated_method = getattr(self, panel_migration.method_name)
                    migrated_method(panel)
                except Exception as exc_info:  # noqa
                    logger.error(f"Old Pannel migrates failed: {panel['id']} failed. {traceback.format_exc()}")
                    panel.clear()
                    panel.update(old_panel)
                    migrated_panels_details["failed_details"][panel_migration.old_type]["count"] += 1
                    migrated_panels_details["failed_details"][panel_migration.old_type]["details"].append(
                        {"id": panel["id"], "title": panel.get("title", "Panel Title"), "error_message": str(exc_info)}
                    )
                else:
                    is_migrate = True
                    migrated_panels_details["success_details"][panel_migration.old_type]["count"] += 1
                    migrated_panels_details["success_details"][panel_migration.old_type]["details"].append(
                        {"id": panel["id"], "title": panel.get("title", "Panel Title")}
                    )
                break
        return is_migrate

    def perform_request(self, params):
        # 1. 获取仪表盘信息
        org_id = get_or_create_org(str(params["bk_biz_id"]))["id"]
        dashboard_info = Dashboard.objects.filter(org_id=org_id, is_folder=False, uid=params["dashboard_uid"]).first()
        dashboard = json.loads(dashboard_info.data) if dashboard_info else None

        # 没有获取到仪表盘信息，直接返回
        if not dashboard:
            return {
                "result": False,
                "message": f"Migrate failed. The dashboard information could not be found. "
                f"dashboard_uid: {params['dashboard_uid']}",
                "code": 200,
                "data": {},
            }

        # 2. 遍历 panels 进行转换更新面板配置
        is_migrate = False
        migrated_panels_details = {
            "success_total": 0,
            "failed_total": 0,
            "success_details": {
                panel_migration.old_type: {"count": 0, "details": []} for panel_migration in self.PANEL_MIGRATIONS
            },
            "failed_details": {
                panel_migration.old_type: {"count": 0, "details": []} for panel_migration in self.PANEL_MIGRATIONS
            },
        }
        for panel in dashboard.get("panels", []):
            if panel.get("type") == "row":
                for raw_panel in panel.get("panels", []):
                    is_migrate = self.migrate_panel(raw_panel, is_migrate, migrated_panels_details)
            is_migrate = self.migrate_panel(panel, is_migrate, migrated_panels_details)

        # 统计迁移成功和迁移失败的 pannel 总数
        migrated_panels_details["success_total"] = sum(
            details["count"] for details in migrated_panels_details["success_details"].values()
        )
        migrated_panels_details["failed_total"] = sum(
            details["count"] for details in migrated_panels_details["failed_details"].values()
        )

        # 3. 更新仪表盘
        if migrated_panels_details["failed_total"]:
            # 3.1 如果仪表盘内的面板迁移有失败的情况
            result = api.grafana.create_or_update_dashboard_by_uid(
                org_id=org_id,
                dashboard=dashboard,
                folderId=dashboard_info.folder_id,
                overwrite=False,
            )

            if not result["result"]:
                return {
                    "result": False,
                    "message": result["message"],
                    "code": 500,
                    "data": {},
                }
            else:
                return {
                    "result": True,
                    "message": "Migration completed. Some panels may have failed to migrate.",
                    "code": 200,
                    "data": migrated_panels_details,
                }
        elif is_migrate:
            # 3.1 仪表盘内的面板都成功迁移的情况
            result = api.grafana.create_or_update_dashboard_by_uid(
                org_id=org_id,
                dashboard=dashboard,
                folderId=dashboard_info.folder_id,
                overwrite=False,
            )
            return {
                "result": result["result"],
                "message": "Migrate success." if result["result"] else result["message"],
                "code": 200,
                "data": migrated_panels_details,
            }
        else:
            # 3.2 仪表盘内的面板没有任务迁移的情况
            old_types = [migration.old_type for migration in self.PANEL_MIGRATIONS]
            return {
                "result": True,
                "message": f"Nothing to Migrate. Only these types of panel are supported to migrate: "
                f"{', '.join(old_types)}",
                "code": 200,
                "data": {},
            }


class GetRelatedStrategy(Resource):
    """
    查询图表关联策略
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        dashboard_uid = serializers.CharField(label="仪表盘UID")
        panel_id = serializers.IntegerField(label="图表ID", required=False)

    def perform_request(self, params: dict[str, Any]):
        strategies = StrategyModel.objects.filter(
            bk_biz_id=params["bk_biz_id"],
            type=StrategyModel.StrategyType.Dashboard,
        ).only("id", "name", "is_enabled", "is_invalid", "invalid_type")

        strategy_id_to_strategy = {strategy.id: strategy for strategy in strategies}

        qcs = QueryConfigModel.objects.filter(
            data_source_label=DataSourceLabel.DASHBOARD,
            config__dashboard_uid=params["dashboard_uid"],
            strategy_id__in=list(strategy_id_to_strategy.keys()),
        )

        if params.get("panel_id"):
            qcs = [qc for qc in qcs if qc.config.get("panel_id") == params["panel_id"]]

        result = []
        for qc in qcs:
            strategy = strategy_id_to_strategy[qc.strategy_id]
            result.append(
                {
                    "dashboard_uid": qc.config["dashboard_uid"],
                    "variables": qc.config["variables"],
                    "panel_id": qc.config["panel_id"],
                    "ref_id": qc.config["ref_id"],
                    "strategy_id": qc.strategy_id,
                    "strategy_name": strategy.name,
                    "is_enabled": strategy.is_enabled,
                    "is_invalid": strategy.is_invalid,
                    "invalid_type": strategy.invalid_type,
                }
            )

        return result


class MigrateOldPanelsByBiz(Resource):
    """
    全业务仪表盘旧图表迁移
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID", required=True)

    def perform_request(self, params):
        org_id = get_or_create_org(str(params["bk_biz_id"]))["id"]
        task = migrate_all_panels_task.delay(params["bk_biz_id"], org_id)

        return {"task_id": task.id}


class MigratePanelsInfo(Resource):
    """查询全业务仪表盘旧图表迁移情况"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID", required=True)

    def perform_request(self, params):
        config = ApplicationConfig.objects.get(
            cc_biz_id=params["bk_biz_id"],
            key=f"{params['bk_biz_id']}_migrate_all_panels",
        )
        result = config.value
        result.update({"data_updated": config.data_updated, "data_created": config.data_created})

        return result
