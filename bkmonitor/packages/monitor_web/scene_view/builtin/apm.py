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
import copy
import json
import logging
from typing import Any, Dict, List, Optional, Set

import arrow
from django.utils.translation import gettext as _
from rest_framework import serializers

from apm_web.constants import HostAddressType
from apm_web.handlers import metric_group
from apm_web.handlers.component_handler import ComponentHandler
from apm_web.handlers.host_handler import HostHandler
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.models import Application, CodeRedefinedConfigRelation
from bkmonitor.models import MetricListCache
from constants.apm import (
    MetricTemporality,
    TelemetryDataType,
)
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import resource
from monitor_web.models.scene_view import SceneViewModel, SceneViewOrderModel
from monitor_web.scene_view.builtin import BuiltinProcessor

logger = logging.getLogger(__name__)


class ApmBuiltinProcessor(BuiltinProcessor):
    SCENE_ID = "apm"
    builtin_views: Dict = None

    filenames = [
        # ⬇️ APM观测场景视图
        "apm_application-endpoint",
        "apm_application-error",
        "apm_application-overview",
        "apm_application-service",
        "apm_application-topo",
        "apm_application-custom_metric",
        "apm_service-component-default-error",
        "apm_service-component-default-instance",
        "apm_service-component-default-overview",
        "apm_service-component-default-topo",
        "apm_service-component-db-db",
        "apm_service-component-messaging-endpoint",
        "apm_service-service-default-caller_callee",
        "apm_service-service-default-endpoint",
        "apm_service-service-default-error",
        "apm_service-service-default-host",
        "apm_service-service-default-instance",
        "apm_service-service-default-log",
        "apm_service-service-default-overview",
        "apm_service-service-default-profiling",
        "apm_service-service-default-topo",
        "apm_service-service-default-db",
        "apm_service-service-default-custom_metric",
        "apm_service-remote_service-http-overview",
        # ⬇️ APMTrace检索场景视图
        "apm_trace-log",
        "apm_trace-host",
    ]

    REQUIRE_ADD_PARAMS_VIEW_IDS = [
        "service-default-endpoint",
        "service-default-overview",
        "service-default-error",
        "service-default-host",
        "service-default-instance",
        "service-default-log",
        "service-default-topo",
        "service-default-db",
        "service-default-caller_callee",
        "service-default-custom_metric",
    ]
    APM_TRACE_PREFIX = "apm_trace"

    @classmethod
    def load_builtin_views(cls):
        # if cls.builtin_views is None:
        cls.builtin_views = {}

        for filename in cls.filenames:
            cls.builtin_views[filename] = cls._read_builtin_view_config(filename)

    @classmethod
    def exists_views(cls, name):
        """是否存在指定的视图"""
        return bool(next((i for i in cls.filenames if name in i), None))

    @classmethod
    def create_or_update_view(
        cls, bk_biz_id: int, scene_id: str, view_type: str, view_id: str, view_config: Dict
    ) -> Optional[SceneViewModel]:
        view = SceneViewModel.objects.get(bk_biz_id=bk_biz_id, scene_id=scene_id, type=view_type, id=view_id)
        if "order" in view_config:
            view.order = view_config["order"]
        view.save()
        return view

    @classmethod
    def get_view_config(cls, view: SceneViewModel, params: Dict = None, *args, **kwargs) -> Dict:
        """APM下不需要区分视图的type类型(overview/detail)"""
        # 根据params类型判断是什么类型 找不到则使用default
        cls.load_builtin_views()

        bk_biz_id = view.bk_biz_id
        app_name = params["app_name"]
        service_name = params["service_name"]

        builtin_view = f"{view.scene_id}-{view.id}"
        view_config = cls.builtin_views[builtin_view]
        view_config = cls._replace_variable(view_config, "${bk_biz_id}", bk_biz_id)
        # 替换table_id
        table_id = Application.get_metric_table_id(bk_biz_id, app_name)
        view_config = cls._replace_variable(view_config, "${table_id}", table_id)

        if builtin_view.startswith(cls.APM_TRACE_PREFIX):
            # APM Trace检索处

            if builtin_view == f"{cls.APM_TRACE_PREFIX}-host":
                span_id = params.get("span_id")
                if not span_id:
                    raise ValueError(_("缺少SpanId参数"))

                span_host = HostHandler.find_host_in_span(bk_biz_id, app_name, span_id)

                if span_host:
                    cls._add_config_from_host(view, view_config)
                    # 替换模版中变量
                    view_config = cls._replace_variable(view_config, "${app_name}", app_name)
                    view_config = cls._replace_variable(view_config, "${span_id}", span_id)
                    cls._handle_current_target(span_host, view_config)
                    return view_config

                return cls._get_non_host_view_config(builtin_view, params)
            elif builtin_view == f"{cls.APM_TRACE_PREFIX}-log":
                service_name = params.get("service_name")
                span_id = params.get("span_id")
                if not service_name or not span_id:
                    raise ValueError(_("缺少ServiceName或者spanId参数"))

                view_config = cls._replace_variable(view_config, "${app_name}", app_name)
                view_config = cls._replace_variable(view_config, "${service_name}", service_name)
                view_config = cls._replace_variable(view_config, "${span_id}", span_id)

            return view_config

        # APM观测场景处
        if builtin_view == "apm_service-service-default-host":
            if all(list(params.values())) and HostHandler.list_application_hosts(
                view.bk_biz_id,
                params.get("app_name"),
                params.get("service_name"),
                start_time=params.get("start_time"),
                end_time=params.get("end_time"),
            ):
                cls._add_config_from_host(view, view_config)
                return view_config

            return cls._get_non_host_view_config(builtin_view, params)

        if builtin_view == "apm_service-service-default-caller_callee":
            group: metric_group.TrpcMetricGroup = metric_group.MetricGroupRegistry.get(
                metric_group.GroupEnum.TRPC, bk_biz_id, app_name
            )

            # 探测服务，存在再展示页面
            view_config["hidden"] = True
            server_list: List[str] = group.fetch_server_list()
            for server in server_list:
                if not server:
                    continue

                if server.endswith(params["service_name"]):
                    view_config["hidden"] = False
                    break

            # 如果页面隐藏或者只需要列表信息，提前返回减少渲染耗时
            if view_config["hidden"] or params.get("only_simple_info"):
                return view_config

            server_config: Dict[str, Any] = group.get_server_config(server=params["service_name"])
            if server_config["temporality"] == MetricTemporality.CUMULATIVE:
                # 指标为累加类型，需要添加 increase 函数
                cls._add_functions(view_config, [{"id": "increase", "params": [{"id": "window", "value": "1m"}]}])

            view_config = cls._replace_variable(view_config, "${temporality}", server_config["temporality"])
            view_config = cls._replace_variable(view_config, "${server}", server_config["server_field"])
            view_config = cls._replace_variable(view_config, "${service_name}", server_config["service_field"])
            view_config = cls._replace_variable(
                view_config, "${server_filter_method}", server_config["server_filter_method"]
            )

            ret_code_as_exception: str = "false"
            try:
                code_redefined_config = CodeRedefinedConfigRelation.objects.get(
                    bk_biz_id=view.bk_biz_id, app_name=app_name, service_name=params["service_name"]
                )
                if code_redefined_config.ret_code_as_exception:
                    ret_code_as_exception = "true"
                    success_rate_panel_data: Dict[str, Any] = view_config["overview_panels"][0]["extra_panels"][1][
                        "targets"
                    ][0]["data"]
                    code_condition: Dict[str, Any] = {
                        "key": "code",
                        "method": "eq",
                        "value": ["0", "ret_0"],
                        "condition": "and",
                    }
                    success_rate_panel_data["query_configs"][0]["where"][1] = code_condition
                    success_rate_panel_data["unify_query_param"]["query_configs"][0]["where"][1] = code_condition

                    view_config["overview_panels"][0]["extra_panels"][2]["options"]["child_panels_selector_variables"][
                        1
                    ]["variables"] = {"code_field": "code", "code_values": ["0", "ret_0"], "code_method": "neq"}
            except CodeRedefinedConfigRelation.DoesNotExist:
                pass

            view_config = cls._replace_variable(view_config, "${ret_code_as_exception}", ret_code_as_exception)

        # APM自定义指标
        if builtin_view == "apm_service-service-default-custom_metric" and app_name:
            try:
                application = Application.objects.get(app_name=app_name, bk_biz_id=bk_biz_id)
                result_table_id = application.fetch_datasource_info(
                    TelemetryDataType.METRIC.datasource_type, attr_name="result_table_id"
                )
            except Application.DoesNotExist:
                raise ValueError("Application does not exist")

            metric_group_mapping = dict()
            group_panel_template = view_config["overview_panels"][0]
            metric_panel_template = group_panel_template["panels"].pop(0)

            metric_queryset = MetricListCache.objects.filter(
                result_table_id=result_table_id,
                data_source_label=DataSourceLabel.CUSTOM,
                data_type_label=DataTypeLabel.TIME_SERIES,
            )
            monitor_name_mapping = cls.get_monitor_name(bk_biz_id, result_table_id, count=metric_queryset.count())
            for idx, i in enumerate(metric_queryset):
                # 过滤内置指标
                if any([str(i.metric_field).startswith("apm_"), str(i.metric_field).startswith("bk_apm_")]):
                    continue
                # 根据dimension获取monitor_name监控项, 获取不到的则跳过
                metric_info = monitor_name_mapping.get(f"{i.metric_field}_value")
                if not metric_info:
                    continue
                # 根据service进行过滤，不满足条件的过滤
                if service_name and metric_info["actual_service_name"] != service_name:
                    continue

                # 进行panels的变量渲染
                variables = {
                    "id": f"idx_{idx}",
                    "table_id": i.result_table_id,
                    "metric_field": i.metric_field,
                    "readable_name": i.readable_name,
                    "data_source_label": i.data_source_label,
                    "data_type_label": i.data_type_label,
                    "filter_key_name": metric_info["filter_service_name"],
                    "filter_key_value": metric_info["filter_service_value"],
                }
                metric_panel = copy.deepcopy(metric_panel_template)
                for var_name, var_value in variables.items():
                    metric_panel = cls._replace_variable(metric_panel, "${{{}}}".format(var_name), var_value)

                monitor_name = metric_info["monitor_name"]
                if monitor_name not in metric_group_mapping:
                    group_id = len(metric_group_mapping)
                    group_panel = copy.deepcopy(group_panel_template)
                    group_variables = {
                        "group_id": group_id,
                        "group_name": monitor_name,
                    }
                    for var_name, var_value in group_variables.items():
                        group_panel = cls._replace_variable(group_panel, "${{{}}}".format(var_name), var_value)
                    metric_group_mapping[monitor_name] = group_panel
                metric_group_mapping[monitor_name]["panels"].append(metric_panel)
            view_config["overview_panels"] = list(metric_group_mapping.values())
        return view_config

    @classmethod
    def get_monitor_name(cls, bk_biz_id, result_table_id, count: int = 1000) -> dict:
        promql = (
            f"count by (scope_name, monitor_name, service_name, target, __name__) "
            f"({{__name__=~\"custom:{result_table_id}:.*\"}})"
        )
        end_time = int(arrow.now().timestamp)
        start_time = end_time - 60
        request_params = {
            "bk_biz_id": bk_biz_id,
            "query_configs": [
                {
                    "data_source_label": DataSourceLabel.PROMETHEUS,
                    "data_type_label": DataTypeLabel.TIME_SERIES,
                    "promql": promql,
                    "interval": "auto",
                    "alias": "a",
                    "filter_dict": {},
                }
            ],
            "slimit": count,
            "expression": "",
            "alias": "a",
            "start_time": start_time,
            "end_time": end_time,
        }

        metric_mapping_config = {
            "Galileo": {
                "monitor_name": "monitor_name",
                "filter_service_name": "target",
                "filter_service_prefix": "BCS.",
            },
            "OpenTelemetry": {
                "monitor_name": "scope_name",
                "filter_service_name": "service_name",
                "filter_service_prefix": "",
            },
        }

        monitor_name_mapping = {}
        try:
            series = resource.grafana.graph_unify_query(request_params)["series"]
            for metric in series:
                metric_field = metric.get("dimensions", {}).get("__name__")
                if metric_field:
                    # Todo: 后续明确区分方案后，最好调整下
                    metric_type = "Galileo" if "monitor_name" in metric["dimensions"] else "OpenTelemetry"
                    mapping_config = metric_mapping_config[metric_type]
                    monitor_name_mapping[metric_field] = {
                        "metric_type": metric_type,
                        "monitor_name": metric["dimensions"].get(mapping_config["monitor_name"]),
                        "filter_service_name": mapping_config["filter_service_name"],
                        "filter_service_value": metric["dimensions"].get(mapping_config["filter_service_name"]),
                    }
                    monitor_name_mapping[metric_field]["actual_service_name"] = cls.remove_prefix(
                        monitor_name_mapping[metric_field]["filter_service_value"],
                        mapping_config["filter_service_prefix"],
                    )
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(f"查询自定义指标关键维度信息失败: {e} ")

        return monitor_name_mapping

    @classmethod
    def remove_prefix(cls, text, prefix):
        if isinstance(text, str) and text.startswith(prefix):
            return text[len(prefix) :]
        return text

    @classmethod
    def _handle_current_target(cls, span_host, view_config):
        """
        处理current_target
        在Trace检索处 将主机图表配置里面的$current_target直接替换为主机数据
        IPV4: bk_target_ip+bk_target_cloud_id
        IPV6:
        """

        for overview_panel in view_config.get("overview_panels", []):
            for panel in overview_panel.get("panels", []):
                for target in panel.get("targets"):
                    for query_config in target.get("data", {}).get("query_configs", []):
                        if "$current_target" not in query_config.get("filter_dict", {}).get("targets", []):
                            continue
                        current_target = {}
                        if span_host["address_type"] == HostAddressType.IPV4:
                            current_target["bk_target_ip"] = span_host["bk_host_innerip"]
                            current_target["bk_target_cloud_id"] = span_host["bk_cloud_id"]
                        else:
                            current_target["bk_host_id"] = span_host["bk_host_id"]

                        query_config["filter_dict"]["targets"] = [current_target]

    @classmethod
    def _replace_variable(cls, view_config, target, value):
        """替换模版中的变量"""
        content = json.dumps(view_config)
        return json.loads(content.replace(target, str(value)))

    @classmethod
    def _add_functions(cls, view_config: Dict[str, Any], functions: List[Dict[str, Any]]):
        for panel in (
            (view_config.get("overview_panels") or [])
            + (view_config.get("extra_panels") or [])
            + (view_config.get("panels") or [])
        ):
            cls._add_functions(panel, functions)

        for target in view_config.get("targets") or []:
            target_data = target.get("data")
            if not target_data:
                continue

            for query_config in target_data.get("query_configs") or []:
                query_config.setdefault("functions", []).extend(functions)

            if not target_data.get("unify_query_param"):
                continue

            for query_config in target_data["unify_query_param"].get("query_configs") or []:
                query_config.setdefault("functions", []).extend(functions)

    @classmethod
    def _add_config_from_host(cls, view, view_config):
        """从主机监控中获取并增加配置"""
        from monitor_web.scene_view.builtin.host import get_auto_view_panels

        # 特殊处理服务主机页面 -> 为主机监控panel配置
        host_view = SceneViewModel.objects.filter(bk_biz_id=view.bk_biz_id, scene_id="host", type="detail").first()
        if host_view:
            view_config["overview_panels"], view_config["order"] = get_auto_view_panels(view)

    @classmethod
    def create_default_views(cls, bk_biz_id: int, scene_id: str, view_type: str, existed_views):
        cls.load_builtin_views()

        builtin_view_ids = {v.split("-", 1)[-1] for v in cls.builtin_views if v.startswith(f"{scene_id}-")}
        existed_view_ids: Set[str] = {v.id for v in existed_views}
        create_view_ids = builtin_view_ids - existed_view_ids
        new_views = []
        for view_id in create_view_ids:
            view_config = cls.builtin_views[f"{scene_id}-{view_id}"]
            new_views.append(
                SceneViewModel(
                    bk_biz_id=bk_biz_id,
                    scene_id=scene_id,
                    type="",
                    id=view_id,
                    name=view_config["name"],
                    mode=view_config["mode"],
                    variables=view_config.get("variables", []),
                    panels=view_config.get("panels", []),
                    list=view_config.get("list", []),
                    order=view_config.get("order", []),
                    options=view_config.get("options", {}),
                )
            )
        if new_views:
            SceneViewModel.objects.bulk_create(new_views)

        # 删除多余的视图
        delete_view_ids = existed_view_ids - builtin_view_ids
        if delete_view_ids:
            SceneViewModel.objects.filter(bk_biz_id=bk_biz_id, scene_id=scene_id, id__in=delete_view_ids).delete()

        cls.create_default_apm_order(bk_biz_id, scene_id)

    @classmethod
    def create_default_apm_order(cls, bk_biz_id: int, scene_id: str):
        # 顶部栏优先级配置
        if scene_id == f"{cls.SCENE_ID}_application":
            SceneViewOrderModel.objects.update_or_create(
                bk_biz_id=bk_biz_id,
                scene_id=scene_id,
                type="",
                defaults={"config": ["overview", "topo", "service", "endpoint", "db", "error"]},
            )
        if scene_id == f"{cls.SCENE_ID}_service":
            SceneViewOrderModel.objects.update_or_create(
                bk_biz_id=bk_biz_id,
                scene_id=scene_id,
                type="",
                defaults={
                    "config": [
                        "overview",
                        "caller_callee",
                        "topo",
                        "endpoint",
                        "db",
                        "error",
                        "instance",
                        "host",
                        "log",
                        "profiling",
                    ]
                },
            )

    @classmethod
    def is_builtin_scene(cls, scene_id: str) -> bool:
        return scene_id.startswith(cls.SCENE_ID)

    @classmethod
    def _get_non_host_view_config(cls, builtin_view, params):
        # 不同场景下返回不同的无数据配置
        link = {}
        if builtin_view.startswith(cls.APM_TRACE_PREFIX):
            title = _("暂未发现主机")
            sub_title = _(
                "关联主机方法:\n1. 上报时增加 IP 信息。"
                "如果是非容器环境，"
                "需要补充 resource.net.host.ip(机器的 IP 地址) 字段。"
                "如果是容器环境，"
                "可将上报地址切换为集群内上报，自动获得关联。\n",
            )

        else:
            title = _("暂未关联主机")
            sub_title = _(
                "关联主机方法:\n1. SDK上报时增加IP信息。"
                "如果是非容器环境，"
                "需要补充 resource.net.host.ip(机器的 IP 地址) 字段。"
                "如果是容器环境，"
                "可将上报地址切换为集群内上报，自动获得关联。\n"
                "2. 在服务设置中，通过【关联 CMDB 服务】设置关联服务模版，会自动关联此服务模版下的主机列表"
            )

            if params.get("app_name") and params.get("service_name"):
                url = f"/service-config?app_name={params['app_name']}&service_name={params['service_name']}"
                link = {
                    "link": {"target": "self", "value": _("关联服务模版"), "url": url},
                }

        return {
            "id": "host",
            "type": "overview",
            "mode": "auto",
            "name": _("主机"),
            "panels": [],
            "overview_panels": [
                {
                    "id": 1,
                    "title": "",
                    "type": "exception-guide",
                    "targets": [{"data": {"type": "empty", "title": title, "subTitle": sub_title, **link}}],
                    "gridPos": {"x": 0, "y": 0, "w": 24, "h": 24},
                }
            ],
            "order": [],
        }

    @classmethod
    def convert_custom_params(cls, scene_id, params):
        """
        将接口参数转换为视图类需要的参数 各个场景需要的参数如下:
        APM观测场景服务页面处:
            1. apm_app_name
            2. apm_service_name
        APM Trace检索页面处:
            1. apm_span_id
        """

        if scene_id.startswith(cls.APM_TRACE_PREFIX):
            return {
                "span_id": params.get("apm_span_id"),
                "app_name": params.get("apm_app_name"),
                "service_name": params.get("apm_service_name"),
                "only_simple_info": params.get("only_simple_info") or False,
            }

        return {
            "app_name": params.get("apm_app_name"),
            "service_name": params.get("apm_service_name"),
            "only_simple_info": params.get("only_simple_info") or False,
        }

    @classmethod
    def is_custom_view_list(cls) -> bool:
        return True

    @classmethod
    def list_view_list(cls, scene_id, views: List[SceneViewModel], params):
        """
        对于APM服务 需要根据不同类型返回不同的图表配置
        """

        # 只处理APM服务视图
        if scene_id != "apm_service":
            return None

        class _Serializer(serializers.Serializer):
            bk_biz_id = serializers.IntegerField()
            apm_app_name = serializers.CharField()
            apm_service_name = serializers.CharField()

        _Serializer(data=params).is_valid(raise_exception=True)
        node = ServiceHandler.get_node(
            params["bk_biz_id"],
            params["apm_app_name"],
            params["apm_service_name"],
            raise_exception=False,
        )
        default_key = "service-default"
        if node:
            if ComponentHandler.is_component_by_node(node):
                default_key = f"{node['extra_data']['kind']}-default"
            specific_key = f"{node['extra_data']['kind']}-{node['extra_data']['category']}"
            specific_views = [i for i in views if i.id.startswith(specific_key)]
            specific_tabs = [i.id.split("-")[-1] for i in specific_views]
        else:
            specific_tabs = []
            specific_views = []

        default_views = [i for i in views if i.id.startswith(default_key) and i.id.split("-")[-1] not in specific_tabs]

        res = default_views + specific_views
        if ServiceHandler.is_remote_service_by_node(node):
            # 自定义服务 无实例、 Profiling 、 DB
            ignore_tabs = ["db", "instance", "profiling"]
            res = [i for i in res if i.id.split("-")[-1] not in ignore_tabs]

        return res

    @classmethod
    def get_dashboard_id(cls, bk_biz_id, app_name, service_name, tab_name, views):
        """获取前端跳转链接里面的 dashboardId (服务页面)"""
        try:
            node = ServiceHandler.get_node(bk_biz_id, app_name, service_name)
        except Exception:  # pylint: disable=broad-except
            return None

        default_key = f"service-default-{tab_name}"
        if ComponentHandler.is_component_by_node(node):
            default_key = f"{node['extra_data']['kind']}-default-{tab_name}"

        specific_key = f"{node['extra_data']['kind']}-{node['extra_data']['category']}-{tab_name}"

        specific_view = next((i for i in views if i.id.startswith(specific_key)), None)
        if specific_view:
            return specific_view.id

        return next((i.id for i in views if i.id.startswith(default_key)), None)

    @classmethod
    def is_custom_sort(cls, scene_id) -> bool:
        """
        是否需要自定义视图列表的排序
        """

        return scene_id == "apm_service"

    @classmethod
    def sort_view_list(cls, scene_id, order, results):
        """
        返回排序后的视图列表 当cls.is_custom_sort() = True时有效
        """
        if scene_id != "apm_service":
            return results

        return sorted(
            results,
            key=lambda x: order.index(x["id"].split("-")[-1]) if x["id"].split("-")[-1] in order else len(results),
        )

    @classmethod
    def handle_view_list_config(cls, scene_id, list_config_item):
        params = {"apm_app_name": "${app_name}"}

        if scene_id == "apm_service":
            # 服务页面需要传递服务信息等参数
            if list_config_item["id"] in cls.REQUIRE_ADD_PARAMS_VIEW_IDS:
                params.update(
                    {
                        "apm_service_name": "${service_name}",
                    }
                )

        list_config_item["params"] = params
