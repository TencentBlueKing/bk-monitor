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

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import arrow
from django.http import Http404
from django.utils.translation import ugettext as _
from rest_framework import serializers

from bkmonitor.aiops.utils import AiSetting
from bkmonitor.data_source import UnifyQuery, load_data_source
from bkmonitor.models import MetricListCache
from bkmonitor.share.api_auth_resource import ApiAuthResource
from constants.aiops import SceneSet
from constants.data_source import GRAPH_MAX_SLIMIT, DataSourceLabel
from core.drf_resource import Resource, api, resource
from monitor_web.models.scene_view import (
    SceneModel,
    SceneViewModel,
    SceneViewOrderModel,
)
from monitor_web.scene_view.builtin import (
    BUILTIN_SCENES,
    create_default_views,
    create_or_update_view,
    get_builtin_scene_processor,
    get_scene_processors,
    get_view_config,
    list_processors_view,
    post_handle_view_list_config,
)

logger = logging.getLogger(__name__)


def validate_scene_type(params):
    """忽略掉视图类型type ."""
    scene_id = params["scene_id"]
    if scene_id in ["apm_application", "apm_service", "kubernetes", "alert"]:
        params["type"] = ""
    return params


class GetSceneResource(Resource):
    """
    获取场景分类
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")

    class ResponseSerializer(serializers.Serializer):
        id = serializers.CharField(label="场景ID")
        name = serializers.CharField(label="场景名称")

    many_response_data = True

    def perform_request(self, params):
        scenes = SceneModel.objects.filter(bk_biz_id=params["bk_biz_id"])
        result = [{"id": key, "name": str(value["name"]), "builtin": True} for key, value in BUILTIN_SCENES.items()]
        return result + [{"id": app.id, "name": app.name, "builtin": False} for app in scenes]


class GetSceneViewListResource(ApiAuthResource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        scene_id = serializers.CharField(label="场景分类")
        type = serializers.ChoiceField(label="视图类型", required=False, choices=("overview", "detail", ""), default="")
        apm_app_name = serializers.CharField(label="应用名称(APM场景变量)", required=False, allow_null=True)
        apm_service_name = serializers.CharField(label="服务名称(APM场景变量)", required=False, allow_null=True)
        apm_category = serializers.CharField(label="服务分类(APM场景变量)", required=False, allow_null=True)
        apm_kind = serializers.CharField(label="服务类型(APM场景变量)", required=False, allow_null=True)
        apm_predicate_value = serializers.CharField(label="服务类型具体值(APM场景变量)", required=False, allow_null=True)

        def validate(self, params):
            return validate_scene_type(params)

    @classmethod
    def get_panel_count(cls, view_config) -> int:
        """
        获取图表数量
        """
        panels: List[Dict] = view_config.get("panels", [])
        count = 0
        for panel in panels:
            if panel.get("type") == "row":
                count += cls.get_panel_count(panel)
            elif panel["type"] != "tag-chart":
                count += 1
        return count

    def get_view_list(self, params):
        scene_id = params["scene_id"]
        scene_type = params.get("type", "")
        bk_biz_id = params["bk_biz_id"]

        # 添加自定义视图
        views = SceneViewModel.objects.filter(bk_biz_id=bk_biz_id, scene_id=scene_id, type=scene_type)

        # 创建默认视图
        create_default_views(bk_biz_id=bk_biz_id, scene_id=scene_id, view_type=scene_type, existed_views=views)

        # 补齐默认视图后重新获取视图列表，后续可以优化为按上面两个数据组合计算，避免重复db请求
        views = SceneViewModel.objects.filter(bk_biz_id=bk_biz_id, scene_id=scene_id, type=scene_type)

        result = []
        if scene_id != "kubernetes":
            specific_views = views
            # 优先从processor处获取视图列表
            custom_view_list = list_processors_view(scene_id, views, params)
            if custom_view_list:
                specific_views = custom_view_list

            for view in specific_views:
                view_config = get_view_config(view, params)
                result.append(
                    {
                        "id": view.id,
                        "name": view.name,
                        "show_panel_count": view_config.get("options", {}).get("show_panel_count", False),
                        "mode": view_config.get("mode", ""),
                        "type": scene_type,
                        "panel_count": self.get_panel_count(view_config),
                    }
                )
        else:
            for view in views:
                # 获得场景处理器
                processor = get_builtin_scene_processor(view)
                # 加载默认配置
                processor.load_builtin_views()
                # 读取配置
                view_id = processor.get_view_id(view)
                view_config = json.loads(json.dumps(processor.builtin_views[view_id]))
                mode = view_config.get("mode", "")
                result.append(
                    {
                        "id": view.id,
                        "name": view.name,
                        "show_panel_count": False,
                        "mode": mode,
                        "type": scene_type,
                    }
                )

        # 按配置进行排序
        scene: Optional[SceneViewOrderModel] = SceneViewOrderModel.objects.filter(
            bk_biz_id=bk_biz_id, scene_id=scene_id, type=scene_type
        ).first()

        if scene:
            order: List = scene.config

            generator = get_scene_processors(scene_id)
            if generator.is_custom_sort(scene_id):
                result = generator.sort_view_list(scene_id, order, result)
            else:
                length = len(result)
                result.sort(key=lambda x: order.index(x["id"]) if x["id"] in order else length)

        return result

    def perform_request(self, params):
        scene_id = params.get("scene_id")
        if scene_id != "kubernetes" and "type" not in params:
            params["type"] = "detail"
            detail_view_list = self.get_view_list(params)
            params["type"] = "overview"
            overview_view_list = self.get_view_list(params)
            config = overview_view_list + detail_view_list
        else:
            config = self.get_view_list(params)

        # 添加额外配置
        post_handle_view_list_config(scene_id, config)
        return config


class GetSceneViewResource(ApiAuthResource):
    """
    获取场景视图配置
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        scene_id = serializers.CharField(label="场景分类")
        type = serializers.ChoiceField(label="视图类型", choices=("overview", "detail", ""), default="")
        id = serializers.CharField(label="视图ID")
        is_split = serializers.BooleanField(label="是否分屏", default=False)
        split_variables = serializers.ListSerializer(label="分屏变量配置", default=[], child=serializers.DictField())
        # K8S场景变量
        bk_monitor_name = serializers.CharField(label="ServiceMonitor名称", required=False, allow_null=True)
        bcs_cluster_id = serializers.CharField(label="集群ID", required=False, allow_null=True)
        # ---
        # APM场景变量
        apm_app_name = serializers.CharField(label="应用名称(仅APM服务页面场景变量使用)", required=False, allow_null=True)
        apm_service_name = serializers.CharField(label="服务名称(仅APM服务页面场景变量使用)", required=False, allow_null=True)
        apm_category = serializers.CharField(label="服务分类(APM场景变量)", required=False, allow_null=True)
        apm_kind = serializers.CharField(label="服务类型(APM场景变量)", required=False, allow_null=True)
        apm_predicate_value = serializers.CharField(label="服务类型具体值(APM场景变量)", required=False, allow_null=True)
        apm_span_id = serializers.CharField(label="SpanId(APM场景变量)", required=False, allow_null=True)
        # ---
        # 主机信息场景变量
        bk_host_innerip = serializers.CharField(label="主机内网IP", required=False, allow_null=True)
        bk_cloud_id = serializers.CharField(label="主机云区域ID", required=False, allow_null=True)
        bk_host_id = serializers.CharField(label="主机ID", required=False, allow_null=True)
        # ---

        def validate(self, params):
            return validate_scene_type(params)

    @classmethod
    def process_split(cls, view_config: Dict, split_variables: List[Dict]) -> Dict:
        """
        分屏逻辑处理
        """
        view_config["variables"] = view_config.get("variables", [])
        view_config["variables"].extend(split_variables)

        # 将侧边栏转换为变量
        panel = view_config["options"].get("selector_panel")
        view_config["options"]["selector_panel"] = None
        if panel:
            selector_variable = None
            if panel["type"] == "topo_tree":
                # 如果拓扑树，需要判断是采集还是主机监控
                if panel["targets"][0]["api"] == "collecting.frontendTargetStatusTopo":
                    selector_variable = {
                        "title": _("实例"),
                        "type": "list",
                        "targets": [
                            {
                                "datasource": "list",
                                "dataType": "list",
                                "api": "collecting.frontendTargetStatusTopo",
                                "data": {"only_instance": True},
                                "fields": {
                                    "target": "current_target",
                                },
                            }
                        ],
                        "options": {"variables": {"multiple": True, "required": False}},
                    }
                elif panel["targets"][0]["api"] == "commons.getTopoTree":
                    selector_variable = {
                        "title": _("主机"),
                        "type": "list",
                        "targets": [
                            {
                                "datasource": "host",
                                "dataType": "list",
                                "api": "scene_view.getHostList",
                                "data": {},
                                "fields": {
                                    "target": "current_target",
                                },
                            }
                        ],
                        "options": {"variables": {"multiple": False, "required": True}},
                    }
            elif panel["targets"][0]["api"].startswith("scene_view.getKubernetes"):
                selector_variable = {
                    "title": panel["title"],
                    "type": "list",
                    "targets": panel["targets"],
                    "options": {},
                }
            else:
                selector_variable = {
                    "title": panel["title"],
                    "type": "list",
                    "targets": panel["targets"],
                    "options": {"variables": {"multiple": True, "required": False}},
                }

            if selector_variable:
                view_config["variables"].insert(0, selector_variable)

        return view_config

    def perform_request(self, params):
        # 创建默认视图
        bk_biz_id = params["bk_biz_id"]
        scene_id = params["scene_id"]
        view_id = params["id"]
        scene_type = params.get("type")

        exists_views = SceneViewModel.objects.filter(bk_biz_id=bk_biz_id, scene_id=scene_id, type=scene_type)

        create_default_views(
            bk_biz_id=bk_biz_id,
            scene_id=scene_id,
            view_type=scene_type,
            existed_views=exists_views,
        )

        view = SceneViewModel.objects.filter(
            bk_biz_id=bk_biz_id, scene_id=scene_id, type=scene_type, id=view_id
        ).first()

        if not view:
            raise Http404

        view_config = get_view_config(view, params)

        if params["is_split"]:
            return self.process_split(view_config, params["split_variables"])

        if scene_id == SceneSet.HOST:
            ai_setting = AiSetting(bk_biz_id=bk_biz_id)

            pop_ai_panel_flag = False

            if ai_setting.multivariate_anomaly_detection.host.is_access_aiops():
                for panel in view_config.get("panels", []):
                    for item in panel.get("panels", []):
                        if item.get("type") == "graph":
                            item["type"] = "performance-chart"
            else:
                pop_ai_panel_flag = True

            if pop_ai_panel_flag:
                view_config["options"].pop("ai_panel", None)

        return view_config


class UpdateSceneViewResource(Resource):
    """
    更新场景视图配置
    """

    class RequestSerializer(serializers.Serializer):
        class ConfigSerializer(serializers.Serializer):
            mode = serializers.ChoiceField(label="模式", required=False, choices=("auto", "custom"))
            variables = serializers.ListSerializer(label="变量配置", required=False, child=serializers.DictField())
            order = serializers.ListSerializer(label="排序配置(平铺模式专用)", required=False, child=serializers.DictField())
            panels = serializers.ListSerializer(label="图表配置", required=False, child=serializers.DictField())
            list = serializers.ListSerializer(label="列表页配置", required=False, child=serializers.DictField())
            options = serializers.DictField(label="视图配置", required=False)

        bk_biz_id = serializers.IntegerField(label="业务ID")
        scene_id = serializers.CharField(label="场景分类")
        type = serializers.ChoiceField(label="视图类型", choices=("overview", "detail"))
        id = serializers.RegexField(label="视图ID", max_length=32, regex="^[0-9a-zA-Z_]+$", required=False)
        name = serializers.CharField(label="视图名称")
        config = ConfigSerializer(label="视图配置", default={})
        view_order = serializers.ListSerializer(label="视图排序", child=serializers.CharField(), default=[])

        def validate(self, params):
            return validate_scene_type(params)

    def perform_request(self, params: Dict):
        # 修改视图排序
        if params["view_order"]:
            order_config, is_created = SceneViewOrderModel.objects.get_or_create(
                bk_biz_id=params["bk_biz_id"],
                scene_id=params["scene_id"],
                type=params["type"],
                defaults={"config": params["view_order"]},
            )
            if not is_created:
                order_config.config = params["view_order"]
                order_config.save()

        params["id"] = params.get("id") or f"custom_{SceneViewModel.objects.count()}"
        config = params["config"]
        config["name"] = params["name"]
        view = create_or_update_view(
            bk_biz_id=params["bk_biz_id"],
            scene_id=params["scene_id"],
            view_type=params["type"],
            view_id=params["id"],
            view_config=config,
        )
        if view:
            return view.id


class DeleteSceneViewResource(Resource):
    """
    删除场景视图配置
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        scene_id = serializers.CharField(label="场景分类")
        id = serializers.CharField(label="视图ID")
        type = serializers.ChoiceField(label="视图类型", choices=("overview", "detail"))

        def validate(self, params):
            return validate_scene_type(params)

    def perform_request(self, params):
        SceneViewModel.objects.filter(
            bk_biz_id=params["bk_biz_id"], scene_id=params["scene_id"], type=params["type"], id=params["id"]
        ).delete()

        # 删除对应的排序配置
        try:
            scene = SceneModel.objects.get(bk_biz_id=params["bk_biz_id"], id=params["scene_id"])
            scene.view_order = [_id for _id in scene.view_order if _id != params["id"]]
            scene.save()
        except SceneModel.DoesNotExist:
            pass


class GetSceneViewDimensionsResource(ApiAuthResource):
    """
    查询场景视图可用维度
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        bcs_cluster_id = serializers.CharField(required=False, label="集群ID", allow_blank=True, allow_null=True)
        scene_id = serializers.CharField(label="场景分类")
        type = serializers.ChoiceField(label="视图类型", choices=("overview", "detail"))
        id = serializers.CharField(label="视图ID")
        name = serializers.CharField(label="资源名称", allow_blank=True, allow_null=True, required=False)
        namespace = serializers.CharField(label="命名空间", required=False)

    @classmethod
    def get_metrics(cls, params: Dict):
        resource_id = params["id"]
        bk_biz_id = params["bk_biz_id"]
        bcs_cluster_id = params.get("bcs_cluster_id")
        name = params.get("name")
        namespace = params.get("namespace")
        if resource_id == "service_monitor":
            if not (name and bcs_cluster_id):
                return []
            panels = resource.scene_view.get_kubernetes_service_monitor_panels(
                {"bcs_cluster_id": bcs_cluster_id, "name": name, "bk_biz_id": bk_biz_id, "namespace": namespace}
            )
        elif resource_id == "pod_monitor":
            if not (name and bcs_cluster_id):
                return []
            panels = resource.scene_view.get_kubernetes_pod_monitor_panels(
                {"bcs_cluster_id": bcs_cluster_id, "name": name, "bk_biz_id": bk_biz_id, "namespace": namespace}
            )
        else:
            view_config = GetSceneViewResource().request(params)
            panels = view_config.get("panels")

        if not panels:
            return []

        result_table_ids = defaultdict(set)
        k8s_metric_fields = []
        for row in panels:
            if row.get("type") == "row":
                row_panels = row.get("panels", [])
            else:
                row_panels = [row]

            for panel in row_panels:
                for target in panel.get("targets", []):
                    if target.get("datasource") != "time_series" or not target.get("data"):
                        continue

                    data = target["data"]
                    for query_config in data.get("query_configs", []):
                        table = query_config.get("table") or query_config.get("index_set_id")
                        if not table:
                            query_metrics = query_config.get("metrics")
                            if not query_metrics:
                                query_metrics = []
                            for query_metric in query_metrics:
                                field = query_metric.get("field")
                                if not query_metric.get("table") and field:
                                    k8s_metric_fields.append(field)

                            continue
                        data_source = (query_config["data_source_label"], query_config["data_type_label"])
                        result_table_ids[data_source].add(table)

        if k8s_metric_fields:
            k8s_metrics = MetricListCache.objects.filter(result_table_id="", metric_field__in=k8s_metric_fields)
            yield from k8s_metrics
        for (data_source_label, data_type_label), tables in result_table_ids.items():
            if data_source_label != DataSourceLabel.BK_LOG_SEARCH:
                metrics = MetricListCache.objects.filter(
                    data_source_label=data_source_label, data_type_label=data_type_label, result_table_id__in=tables
                )
            else:
                metrics = MetricListCache.objects.filter(
                    data_source_label=data_source_label, data_type_label=data_type_label, related_id__in=tables
                )

            yield from metrics

    def perform_request(self, params):
        existed_dimensions = set()
        dimensions = []
        for metric in self.get_metrics(params):
            for dimension in metric.dimensions:
                if dimension["id"] in existed_dimensions:
                    continue
                dimensions.append(dimension)
                existed_dimensions.add(dimension["id"])
        return dimensions


class GetSceneViewDimensionValueResource(ApiAuthResource):
    """
    查询场景视图维度候选值
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        scene_id = serializers.CharField(label="场景分类")
        type = serializers.ChoiceField(label="视图类型", choices=("overview", "detail"))
        id = serializers.CharField(label="视图ID")
        field = serializers.CharField(label="查询维度")
        where = serializers.ListField(label="查询条件", default=[], allow_empty=True, child=serializers.DictField())
        limit = serializers.IntegerField(label="限制数量", default=GRAPH_MAX_SLIMIT)
        start_time = serializers.IntegerField(label="开始时间", required=False)
        end_time = serializers.IntegerField(label="结束时间", required=False)

    def perform_request(self, params):
        for metric in GetSceneViewDimensionsResource.get_metrics(params):
            for dimension in metric.dimensions:
                if dimension["id"] != params["field"]:
                    continue

                data_source_class = load_data_source(metric.data_source_label, metric.data_type_label)
                data_source = data_source_class(
                    bk_biz_id=params["bk_biz_id"],
                    **{
                        "data_source_label": metric.data_source_label,
                        "data_type_label": metric.data_type_label,
                        "table": metric.result_table_id,
                        "data_label": metric.data_label,
                        "index_set_id": metric.related_id,
                        "where": params["where"],
                        "group_by": [params["field"]],
                        "metrics": [{"field": metric.metric_field, "method": "COUNT"}],
                    },
                )
                query = UnifyQuery(bk_biz_id=params["bk_biz_id"], data_sources=[data_source], expression="")

                if not params.get("start_time") or not params.get("end_time"):
                    end_time = int(arrow.now().timestamp)
                    start_time = end_time - 36000
                else:
                    start_time = params["start_time"]
                    end_time = params["end_time"]

                values = query.query_dimensions(
                    dimension_field=params["field"],
                    limit=params["limit"],
                    start_time=start_time * 1000,
                    end_time=end_time * 1000,
                )

                dimensions = values["values"][params["field"]] if isinstance(values, dict) else values

                return [{"id": dimension, "name": dimension} for dimension in set(dimensions) if dimension]


class GetStrategyAndEventCountResource(Resource):
    """
    查询策略数和告警事件数
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        scene_id = serializers.CharField(label="场景分类")
        target = serializers.DictField(required=False, default={}, label="当前目标")

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]
        scenario = ["os"]
        conditions = [{"key": "strategy_status", "value": ["ON"]}]
        query_string = ""
        if params["scene_id"] == "host":
            scenario = ["os", "host_process", "host_device"]
            ip = params["target"].get("bk_target_ip")
            bk_cloud_id = params["target"].get("bk_target_cloud_id")
            bk_host_id = params["target"].get("bk_host_id")
            # TODO: 策略列表/事件中心支持主机ID检索后调整
            if bk_host_id:
                hosts = api.cmdb.get_host_by_id(bk_biz_id=bk_biz_id, bk_host_ids=[bk_host_id])
                if hosts:
                    ip = hosts[0].bk_host_innerip
                    bk_cloud_id = hosts[0].bk_cloud_id
                else:
                    return {"strategy_counts": 0, "event_counts": 0}
            if ip:
                conditions.extend([{"key": "IP", "value": [ip]}, {"key": "bk_cloud_id", "value": [bk_cloud_id]}])
                query_string = _("目标IP : {} AND 目标云区域ID : {}").format(ip, bk_cloud_id)

        elif params["scene_id"] == "uptime_check":
            scenario = ["uptimecheck"]
            task_id = params["target"].get("task_id")
            if task_id:
                conditions.append({"key": "task_id", "value": task_id})
                query_string = 'tags.task_id : "%s"' % task_id

        elif params["scene_id"] == "kubernetes":
            scenario = ["kubernetes"]
            # TODO: 根据场景查询策略列表及事件列表，待场景功能建设后完善
        elif params["scene_id"] == "apm":
            pass

        conditions.append({"key": "scenario", "value": scenario})
        strategy_count_list = resource.strategies.get_strategy_list_v2(
            bk_biz_id=bk_biz_id,
            conditions=conditions,
        )["data_source_list"]
        strategy_counts = 0
        for item in strategy_count_list:
            strategy_counts += item["count"]
        params = {
            "bk_biz_id": bk_biz_id,
            "bk_biz_ids": [bk_biz_id],
            "conditions": [{"key": "category", "value": scenario}],
            "status": ["NOT_SHIELDED_ABNORMAL"],
            "start_time": int((datetime.now() - timedelta(hours=1)).timestamp()),
            "end_time": int(datetime.now().timestamp()),
        }
        if query_string:
            params["query_string"] = query_string
        event_counts = resource.alert.search_alert(**params)["total"]
        return {"strategy_counts": strategy_counts, "event_counts": event_counts}
