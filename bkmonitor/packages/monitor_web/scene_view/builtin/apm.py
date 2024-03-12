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
from itertools import chain
from typing import Dict, List, Optional, Set

from django.utils.translation import gettext as _
from rest_framework import serializers

from apm_web.constants import HostAddressType
from apm_web.handlers.host_handler import HostHandler
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.models import Application
from apm_web.utils import list_remote_service_callers
from monitor_web.models.scene_view import SceneViewModel, SceneViewOrderModel
from monitor_web.scene_view.builtin import BuiltinProcessor


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
        "apm_service-component-default-error",
        "apm_service-component-default-instance",
        "apm_service-component-default-overview",
        "apm_service-component-default-topo",
        "apm_service-component-default-db",
        "apm_service-service-default-endpoint",
        "apm_service-service-default-error",
        "apm_service-service-default-host",
        "apm_service-service-default-instance",
        "apm_service-service-default-log",
        "apm_service-service-default-overview",
        "apm_service-service-default-profiling",
        "apm_service-service-default-topo",
        "apm_service-service-default-db",
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

                span_host = HostHandler.find_host_in_span(bk_biz_id, app_name, span_id)
                if span_host:
                    cls._handle_log_chart_keyword(view_config, span_host)

            return view_config

        # APM观测场景处
        if builtin_view == "apm_service-service-default-host":
            if all(list(params.values())) and HostHandler.list_application_hosts(
                view.bk_biz_id, params.get("app_name"), params.get("service_name")
            ):
                cls._add_config_from_host(view, view_config)
                return view_config

            return cls._get_non_host_view_config(builtin_view, params)

        if builtin_view.startswith("apm_service-service") and builtin_view.endswith("overview"):
            return cls.special_handle_service_overview_overview(view, view_config, params)

        return view_config

    @classmethod
    def _handle_log_chart_keyword(cls, view_config, span_host):
        """
        处理日志标签页默认的查询条件
        对于Trace检索日志处 如果Span中存在主机IP 需要将此IP作为查询关键词
        """

        for overview_panel in view_config.get("overview_panels", []):
            overview_panel["options"] = {"related_log_chart": {"defaultKeyword": span_host["bk_host_innerip"]}}

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
    def _add_config_from_host(cls, view, view_config):
        """从主机监控中获取并增加配置"""
        from monitor_web.scene_view.builtin.host import get_auto_view_panels

        # 特殊处理服务主机页面 -> 为主机监控panel配置
        host_view = SceneViewModel.objects.filter(bk_biz_id=view.bk_biz_id, scene_id="host", type="detail").first()
        if host_view:
            view_config["overview_panels"], view_config["order"] = get_auto_view_panels(view)

    @classmethod
    def special_handle_service_overview_overview(cls, view, view_config, params):
        # 特殊处理服务overview页面
        if not params:
            return view_config

        bk_biz_id = view.bk_biz_id
        service_name = params.get("service_name")
        app_name = params.get("app_name")
        if not service_name or not app_name:
            return view_config

        if not ServiceHandler.is_remote_service(bk_biz_id, app_name, service_name):
            return view_config

        # 自定义服务需要更改查询条件

        # step1: 查询所有主调服务
        from_services = list_remote_service_callers(bk_biz_id, app_name, service_name)
        pure_service_name = service_name.split(":")[-1]

        # step2: 更新unify-query查询条件
        for target in list(chain(*(panel["targets"] for panel in view_config["panels"] if panel["type"] == "graph"))):
            for query_config in target["data"]["query_configs"]:
                query_config["where"].append({"key": "peer_service", "method": "eq", "value": [pure_service_name]})
                query_config["filter_dict"]["service_name"] = from_services

        return view_config

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
                    "config": ["overview", "topo", "endpoint", "db", "error", "instance", "host", "log", "profiling"]
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
            sub_title = _("关联主机方法:\n1. SDK上报时增加IP信息，将已在CMDB中注册的IP地址补充在Span的resource.net.host.ip字段中\n")

        else:
            title = _("暂未关联主机")
            sub_title = _(
                "关联主机方法:\n1. SDK上报时增加IP信息，将已在CMDB中注册的IP地址补充在Span的resource.net.host.ip字段中\n"
                "2. 关联蓝鲸配置平台服务模版，将会获取此服务模版下的主机"
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
            3. apm_kind
            4. apm_category
            5. apm_predicate_value
        APM Trace检索页面处:
            1. apm_span_id
        """

        if scene_id.startswith(cls.APM_TRACE_PREFIX):
            return {
                "span_id": params.get("apm_span_id"),
                "app_name": params.get("apm_app_name"),
                "service_name": params.get("apm_service_name"),
            }

        return {
            "app_name": params.get("apm_app_name"),
            "service_name": params.get("apm_service_name"),
            "kind": params.get("apm_kind"),
            "category": params.get("apm_category"),
            "predicate_value": params.get("apm_predicate_value"),
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
            apm_app_name = serializers.CharField()
            apm_service_name = serializers.CharField()
            apm_category = serializers.CharField()
            apm_kind = serializers.CharField()
            apm_predicate_value = serializers.CharField()

        if _Serializer(data=params).is_valid():
            # 此分类的具类模版
            specific_key = f"{params['apm_kind']}-{params['apm_predicate_value']}"
            specific_views = [i for i in views if i.id.startswith(specific_key)]
            if specific_views:
                return specific_views

            # 此分类的默认模版
            default_key = f"{params['apm_kind']}-default"
            default_views = [i for i in views if i.id.startswith(default_key)]
            if default_views:
                return default_views

        # 如果参数缺少时 返回默认的配置

        return [i for i in views if i.id.startswith("service-default")]

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
                        "apm_category": "${category}",
                        "apm_kind": "${kind}",
                        "apm_predicate_value": "${predicate_value}",
                    }
                )

        list_config_item["params"] = params
