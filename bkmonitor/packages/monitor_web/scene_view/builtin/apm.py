"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import json
import logging
import threading
from typing import Any

from django.conf import settings
from django.core.cache import caches
from django.utils.translation import gettext as _
from rest_framework import serializers

from apm_web.constants import ApmCacheKey, HostAddressType
from apm_web.handlers import metric_group
from apm_web.handlers.component_handler import ComponentHandler
from apm_web.handlers.host_handler import HostHandler
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.metric.constants import SeriesAliasType
from apm_web.models import Application, CodeRedefinedConfigRelation
from bkmonitor.models import MetricListCache
from bkmonitor.utils.cache import CacheType, using_cache
from bkmonitor.utils.common_utils import deserialize_and_decompress
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from bkmonitor.utils.thread_backend import InheritParentThread, run_threads
from constants.apm import MetricTemporality, TelemetryDataType, Vendor
from constants.data_source import DataSourceLabel, DataTypeLabel
from monitor_web.models.scene_view import SceneViewModel, SceneViewOrderModel
from monitor_web.scene_view.builtin import BuiltinProcessor, create_default_views
from monitor_web.scene_view.builtin.constants import DEFAULT_APM_HOST_DETAIL
from monitor_web.scene_view.builtin.utils import gen_string_md5

logger = logging.getLogger(__name__)


def discover_config_from_node_or_none(node: dict[str, Any]) -> dict[str, Any] | None:
    is_trpc: bool = False
    rpc_system: str = metric_group.GroupEnum.TRPC
    for meta in node.get("system") or []:
        if meta.get("name") == metric_group.GroupEnum.TRPC:
            is_trpc = True
        extra_data: dict[str, Any] = meta.get("extra_data") or {}
        if extra_data.get("rpc_system"):
            rpc_system = extra_data["rpc_system"]
            break

    if not is_trpc:
        logger.info("[apm][discover_config_from_node_or_none] system not found: node -> %s", node)
        return None

    # G 和 Tars 框架的指标类型为 Gauge。
    temporality: str = (MetricTemporality.CUMULATIVE, MetricTemporality.DELTA)[
        Vendor.has_sdk(node.get("sdk"), Vendor.G) or rpc_system == "tars"
    ]
    logger.info("[apm][discover_config_from_node_or_none] temporality -> %s, node -> %s", temporality, node)
    return MetricTemporality.get_metric_config(temporality)


def discover_config_from_metric_or_none(
    bk_biz_id: int, app_name: str, table_id: str, service_name: str
) -> dict[str, Any] | None:
    metric_fields: list[str] = [
        metric_group.TrpcMetricGroup.METRIC_FIELDS[SeriesAliasType.CALLER.value]["rpc_handled_total"],
        metric_group.TrpcMetricGroup.METRIC_FIELDS[SeriesAliasType.CALLEE.value]["rpc_handled_total"],
    ]
    metric_exists: bool = MetricListCache.objects.filter(
        bk_tenant_id=bk_biz_id_to_bk_tenant_id(bk_biz_id),
        result_table_id=table_id,
        data_source_label=DataSourceLabel.CUSTOM,
        data_type_label=DataTypeLabel.TIME_SERIES,
        metric_field__in=metric_fields,
    ).exists()
    if not metric_exists:
        logger.info("[apm][discover_config_from_metric_or_none] rpc metric not found: table_id -> %s", table_id)
        return None

    def _fetch_server_list():
        discover_result["server_list"] = group.fetch_server_list()

    def _get_server_config():
        discover_result["server_config"] = group.get_server_config(server=service_name)

    discover_result: dict[str, dict[str, Any] | list[str]] = {}
    group: metric_group.TrpcMetricGroup = metric_group.MetricGroupRegistry.get(
        metric_group.GroupEnum.TRPC, bk_biz_id, app_name
    )
    run_threads([InheritParentThread(target=_fetch_server_list), InheritParentThread(target=_get_server_config)])

    # run_threads 会吃掉异常，这里需要二次检查补偿，有异常也要在外层抛出
    if "server_list" not in discover_result:
        _fetch_server_list()

    if "server_config" not in discover_result:
        _get_server_config()

    logger.info("[apm][discover_config_from_metric_or_none] discover_result -> %s", discover_result)
    if service_name not in discover_result["server_list"]:
        return None

    return discover_result["server_config"]


@using_cache(CacheType.APM(60 * 2))
def discover_caller_callee(
    bk_biz_id: int, app_name: str, table_id: str, service_name: str
) -> dict[str, dict[str, Any] | list[str]]:
    """RPC 服务发现
    页面请求顺序：get_scene_view_list -> get_scene_view 依次调用这段逻辑，缓存 1min 以复用上一次的服务发现结果，加速页面加载。
    :param bk_biz_id: 业务 ID
    :param app_name: 应用名称
    :param table_id: 指标 Table ID
    :param service_name: 服务名称
    :return:
    """
    discover_result: dict[str, dict[str, Any] | bool] = {"exists": False}
    node: dict[str, Any] | None = None
    try:
        # Q：为什么不直接传具体的 service_name?
        # A：方便串行复用 LRU Cache。
        for _node in ServiceHandler.list_nodes(bk_biz_id, app_name):
            if _node["topo_key"] == service_name:
                node = _node
                break
    except ValueError:
        pass

    if not node:
        # 服务还没被发现（页面没有），直接跳过
        logger.info("[apm][discover_caller_callee] node not found: %s / %s / %s", bk_biz_id, app_name, service_name)
        return discover_result

    server_config: dict[str, Any] | None = discover_config_from_node_or_none(
        node
    ) or discover_config_from_metric_or_none(bk_biz_id, app_name, table_id, service_name)
    if not server_config:
        return discover_result

    code_redefined_config = CodeRedefinedConfigRelation.objects.filter(
        bk_biz_id=bk_biz_id, app_name=app_name, service_name=service_name
    ).first()
    if code_redefined_config:
        server_config["ret_code_as_exception"] = code_redefined_config.ret_code_as_exception
    else:
        server_config["ret_code_as_exception"] = False

    # 模调指标可能来源于用户自定义，因为框架/协议原因无法补充「服务」字段，此处允许动态设置「服务」配置以满足该 case。
    server_config.update(settings.APM_CUSTOM_METRIC_SDK_MAPPING_CONFIG.get(f"{bk_biz_id}-{app_name}") or {})
    discover_result["server_config"] = server_config
    discover_result["exists"] = True
    logger.info(
        "[apm][discover_caller_callee] %s / %s / %s, discover_result -> %s",
        bk_biz_id,
        app_name,
        service_name,
        discover_result,
    )
    return discover_result


class ApmBuiltinProcessor(BuiltinProcessor):
    SCENE_ID = "apm"
    builtin_views: dict = None
    _lock: threading.Lock = threading.Lock()

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
        "apm_service-component-db-db",
        "apm_service-component-messaging-endpoint",
        "apm_service-service-default-caller_callee",
        "apm_service-service-default-endpoint",
        "apm_service-service-default-error",
        "apm_service-service-default-host",
        "apm_service-service-default-container",
        "apm_service-service-default-instance",
        "apm_service-service-default-log",
        "apm_service-service-default-event",
        "apm_service-service-default-overview",
        "apm_service-service-default-profiling",
        "apm_service-service-default-topo",
        "apm_service-service-default-db",
        "apm_service-service-default-custom_metric",
        "apm_service-remote_service-http-overview",
        # ⬇️ APMTrace检索场景视图
        "apm_trace-log",
        "apm_trace-host",
        "apm_trace-container",
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
        "service-default-container",
    ]

    # 只需要列表信息时，需要进一步进行渲染的 Tab
    # 列表只关注需要展示哪些 Tab，可以跳过具体的 view_config 生成逻辑，以加快页面渲染
    NEED_RENDER_IF_ONLY_SIMPLE_INFO: list[str] = [
        # 调用分析页面需要另外判断是否展示，不直接跳过
        "apm_service-service-default-caller_callee",
    ]

    APM_TRACE_PREFIX = "apm_trace"

    @classmethod
    def load_builtin_views(cls):
        if cls.builtin_views:
            return

        with cls._lock:
            # 双重检查，等待锁期间可能已经有其他线程「完成」初始化，返回以减少重复读取文件。
            if cls.builtin_views:
                return

            builtin_views: dict[str, dict[str, Any]] = {
                filename: cls._read_builtin_view_config(filename) for filename in cls.filenames
            }
            # 一次性赋值以确保原子性。
            cls.builtin_views = builtin_views

    @classmethod
    def exists_views(cls, name):
        """是否存在指定的视图"""
        return bool(next((i for i in cls.filenames if name in i), None))

    @classmethod
    def create_or_update_view(
        cls, bk_biz_id: int, scene_id: str, view_type: str, view_id: str, view_config: dict
    ) -> SceneViewModel | None:
        view = SceneViewModel.objects.get(bk_biz_id=bk_biz_id, scene_id=scene_id, type=view_type, id=view_id)
        if "order" in view_config:
            view.order = view_config["order"]
        view.save()
        return view

    @classmethod
    def get_view_config(cls, view: SceneViewModel, params: dict = None, *args, **kwargs) -> dict:
        """APM下不需要区分视图的type类型(overview/detail)"""
        # 根据params类型判断是什么类型 找不到则使用default
        cls.load_builtin_views()

        bk_biz_id = view.bk_biz_id
        app_name = params["app_name"]
        service_name = params["service_name"]
        view_switches = params.get("view_switches", {})

        builtin_view = f"{view.scene_id}-{view.id}"
        view_config = cls.builtin_views[builtin_view]
        if params.get("only_simple_info") and builtin_view not in cls.NEED_RENDER_IF_ONLY_SIMPLE_INFO:
            # ViewList 不需要渲染数据，直接返回。
            return view_config

        # 替换 table_id
        table_id = Application.get_metric_table_id(bk_biz_id, app_name)
        view_config = cls._replace_variable(view_config, "${table_id}", table_id)
        view_config = cls._replace_variable(view_config, "${bk_biz_id}", bk_biz_id)

        if builtin_view.startswith(cls.APM_TRACE_PREFIX):
            # APM Trace检索处

            if builtin_view == f"{cls.APM_TRACE_PREFIX}-host":
                span_id = params.get("span_id")
                if not span_id or not service_name:
                    raise ValueError(_("缺少 SpanId / ServiceName 参数"))

                host_predicate = any(
                    [
                        bool(HostHandler.find_host_in_span(bk_biz_id, app_name, span_id)),
                        bool(
                            HostHandler.has_hosts_relation(
                                view.bk_biz_id,
                                app_name,
                                service_name,
                                start_time=params.get("start_time"),
                                end_time=params.get("end_time"),
                            )
                        ),
                    ]
                )
                if host_predicate:
                    cls._add_config_from_host(view, view_config)
                    # Trace 检索主机特殊配置：直接固定图表配置中的变量
                    view_config = cls._replace_variable(view_config, "${app_name}", app_name)
                    view_config = cls._replace_variable(view_config, "${service_name}", service_name)
                    view_config = cls._replace_variable(view_config, "${span_id}", span_id)
                    # trace检索处将图表的维度全部改为显示在下方 而不是右边
                    for i in view_config.get("overview_panels", []):
                        for j in i.get("panels", []):
                            j.update({"options": {"legend": {"placement": "bottom", "displayMode": "list"}}})

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
            elif builtin_view == f"{cls.APM_TRACE_PREFIX}-container":
                return cls.get_container_view(
                    params,
                    bk_biz_id,
                    app_name,
                    service_name,
                    view,
                    view_config,
                    builtin_view,
                    display_with_sidebar=False,
                )
            return view_config

        # APM观测场景处
        # 主机场景
        if builtin_view == "apm_service-service-default-host":
            if (
                app_name
                and service_name
                and HostHandler.has_hosts_relation(
                    view.bk_biz_id,
                    app_name,
                    service_name,
                    start_time=params.get("start_time"),
                    end_time=params.get("end_time"),
                )
            ):
                apm_host_detail_config = copy.deepcopy(DEFAULT_APM_HOST_DETAIL)
                view_config["overview_panels"] = apm_host_detail_config["overview_panels"]

                if "overview_panel" in view_config.get("options"):
                    # 去除顶部栏中的策略告警信息
                    del view_config["options"]["overview_panel"]

                # 兼容前端对 selector_panel 类型为 target_list 做的特殊处理 直接直接替换变量
                view_config["options"]["selector_panel"]["targets"][0]["data"] = {
                    "app_name": app_name,
                    "service_name": service_name,
                }
                return view_config

            return cls._get_non_host_view_config(builtin_view, params)

        # k8s 场景
        if builtin_view == "apm_service-service-default-container":
            return cls.get_container_view(params, bk_biz_id, app_name, service_name, view, view_config, builtin_view)

        # 主被调场景
        if builtin_view == "apm_service-service-default-caller_callee":
            discover_result: dict[str, dict[str, Any] | list[str]] = discover_caller_callee(
                bk_biz_id, app_name, table_id, params["service_name"]
            )
            # 探测服务，存在再展示页面
            view_config["hidden"] = not discover_result["exists"]
            if view_config["hidden"] or params.get("only_simple_info"):
                # 如果页面隐藏或者只需要列表信息，提前返回减少渲染耗时
                return view_config

            server_config: dict[str, Any] = discover_result["server_config"]
            if server_config["temporality"] == MetricTemporality.CUMULATIVE:
                # 指标为累加类型，需要添加 increase 函数
                cls._add_functions(view_config, [{"id": "increase", "params": [{"id": "window", "value": "1m"}]}])

            view_config = cls._replace_variable(view_config, "${temporality}", server_config["temporality"])
            view_config = cls._replace_variable(view_config, "${server}", server_config["server_field"])
            view_config = cls._replace_variable(view_config, "${service_name}", server_config["service_field"])
            view_config = cls._replace_variable(
                view_config, "${server_filter_method}", server_config["server_filter_method"]
            )

            ret_code_as_exception: bool = server_config.get("ret_code_as_exception", False)
            if ret_code_as_exception:
                success_rate_panel_data: dict[str, Any] = view_config["overview_panels"][0]["extra_panels"][1][
                    "targets"
                ][0]["data"]
                code_condition: dict[str, Any] = {
                    "key": "code",
                    "method": "eq",
                    "value": ["0", "ret_0"],
                    "condition": "and",
                }
                success_rate_panel_data["query_configs"][0]["where"][1] = code_condition
                success_rate_panel_data["unify_query_param"]["query_configs"][0]["where"][1] = code_condition

                view_config["overview_panels"][0]["extra_panels"][2]["options"]["child_panels_selector_variables"][0][
                    "variables"
                ] = {
                    "code_field": "code",
                    "code_values": ["0", "ret_0"],
                    "code_method": "neq",
                    # 排除非 0 返回码可能是 timeout 的情况
                    "code_extra_where": {
                        "key": "code_type",
                        "method": "neq",
                        "value": ["timeout"],
                        "condition": "and",
                    },
                }

            view_config = cls._replace_variable(
                view_config, "${ret_code_as_exception}", ("false", "true")[ret_code_as_exception]
            )

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
            group_panel_template = view_config["overview_panels"].pop(0)
            metric_panel_template = group_panel_template["panels"].pop(0)

            metric_queryset = MetricListCache.objects.filter(
                bk_tenant_id=bk_biz_id_to_bk_tenant_id(bk_biz_id),
                result_table_id=result_table_id,
                data_source_label=DataSourceLabel.CUSTOM,
                data_type_label=DataTypeLabel.TIME_SERIES,
            )
            metric_count = metric_queryset.count()

            target_key = f"{bk_biz_id}-{app_name}.{service_name}"
            if target_key in settings.APM_CUSTOM_METRIC_SDK_MAPPING_CONFIG:
                metric_config = settings.APM_CUSTOM_METRIC_SDK_MAPPING_CONFIG[target_key]
            else:
                metric_config = settings.APM_CUSTOM_METRIC_SDK_MAPPING_CONFIG.get("default") or {}

            view_variables = {}
            if not view_switches.get("only_dimension", False):
                server_config: dict[str, Any] = MetricTemporality.get_metric_config(MetricTemporality.DELTA)
                discover_result: dict[str, dict[str, Any] | list[str]] = discover_caller_callee(
                    bk_biz_id, app_name, result_table_id, params["service_name"]
                )
                if discover_result["exists"]:
                    server_config = discover_result["server_config"]

                if server_config["temporality"] == MetricTemporality.CUMULATIVE:
                    # 指标为累加类型，需要添加 increase 函数
                    cls._add_functions(view_config, [{"id": "increase", "params": [{"id": "window", "value": "1m"}]}])

                view_variables = {
                    "temporality": server_config["temporality"],
                    "server": server_config["server_field"],
                    "service_name": server_config["service_field"],
                    "server_filter_method": server_config["server_filter_method"],
                    "ret_code_as_exception": server_config.get("ret_code_as_exception", False),
                }

            if metric_count > 0:
                # 使用非内部指标设置monitor_info_mapping, 优先使用缓存
                monitor_info_mapping = {}
                if "redis" in caches:
                    cache_agent = caches["redis"]
                    cache_key = ApmCacheKey.APP_SCOPE_NAME_KEY.format(
                        bk_biz_id=bk_biz_id, application_id=application.application_id
                    )
                    try:
                        cached_data = cache_agent.get(cache_key)
                        monitor_info_mapping = deserialize_and_decompress(cached_data) if cached_data else {}
                    except Exception as e:  # pylint: disable=broad-except
                        logger.warning(f"当前条件下 {cache_key} 暂无scope_name缓存: {e}")
                        monitor_info_mapping = {}
                if not monitor_info_mapping or not monitor_info_mapping.get(service_name):
                    monitor_info_mapping = metric_group.MetricHelper.get_monitor_info(
                        bk_biz_id,
                        result_table_id,
                        service_name=service_name,
                        count=metric_count,
                        start_time=params.get("start_time"),
                        end_time=params.get("end_time"),
                        **metric_config,
                    )

                for idx, i in enumerate(metric_queryset):
                    # 过滤内置指标
                    if any([str(i.metric_field).startswith("apm_"), str(i.metric_field).startswith("bk_apm_")]):
                        continue
                    # 根据dimension获取monitor_name监控项, 获取不到的则跳过
                    metric_info = monitor_info_mapping.get(service_name, {}).get(i.metric_field)
                    if not metric_info:
                        continue
                    # 进行panels的变量渲染
                    variables = {
                        "table_id": i.result_table_id,
                        "metric_field": i.metric_field,
                        "readable_name": i.readable_name,
                        "data_source_label": i.data_source_label,
                        "data_type_label": i.data_type_label,
                        "service_name_value": service_name,
                    }
                    metric_panel = copy.deepcopy(metric_panel_template)
                    if view_variables:
                        variables.update(view_variables)
                    metric_panel = cls._multi_replace_variables(metric_panel, variables)

                    monitor_name_list = metric_info.get("monitor_name_list") or ["default"]
                    for monitor_name in monitor_name_list:
                        if monitor_name not in metric_group_mapping:
                            group_id = len(metric_group_mapping)
                            group_panel = copy.deepcopy(group_panel_template)
                            group_variables = {
                                "group_id": group_id,
                                "group_name": monitor_name,
                            }
                            group_panel = cls._multi_replace_variables(group_panel, group_variables)
                            metric_group_mapping[monitor_name] = group_panel
                        metric_panel_instance = copy.deepcopy(metric_panel)
                        # 设置monitor_name的id
                        graph_idx = gen_string_md5(f"{monitor_name}_{idx}")
                        metric_panel_instance = cls._replace_variable(metric_panel_instance, "${id}", graph_idx)
                        # 设置monitor_name和metric_panel
                        metric_panel_instance = cls._replace_variable(
                            metric_panel_instance, "${scope_name_value}", monitor_name
                        )
                        metric_group_mapping[monitor_name]["panels"].append(metric_panel_instance)
                view_config["overview_panels"] = list(metric_group_mapping.values())
            if not view_config["overview_panels"]:
                cls._generate_non_custom_metric_view_config(view_config)

            option_variables = {"request_total_name": _("请求总数")}
            view_config = cls._multi_replace_variables(view_config, option_variables)
        return view_config

    @classmethod
    def get_container_view(
        cls,
        params,
        bk_biz_id,
        app_name,
        service_name,
        view,
        view_config,
        builtin_view,
        display_with_sidebar=True,
    ):
        # display_with_sidebar: 是否页面配置展示为侧边栏(在观测场景处显示为侧边栏，在主机场景处显示为顶部栏下拉框)
        # 获取观测场景或 span 检索处关联容器的图表配置
        # 时间范围必传
        start_time = params.get("start_time")
        end_time = params.get("end_time")
        if not start_time or not end_time:
            raise ValueError("没有传递 start_time, end_time")

        if app_name and service_name:
            from apm_web.container.resources import ListServicePodsResource

            response = ListServicePodsResource()(
                bk_biz_id=bk_biz_id,
                app_name=app_name,
                service_name=service_name,
                start_time=start_time,
                end_time=end_time,
            )

            if response:
                # 实际有 Pod 数据才返回
                return cls._add_config_from_container(app_name, service_name, view, view_config, display_with_sidebar)

        return cls._get_non_container_view_config(builtin_view, params)

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
    def _multi_replace_variables(cls, replace_config, variables_mapping):
        replace_content = json.dumps(replace_config)
        for var_name, var_value in variables_mapping.items():
            replace_content = replace_content.replace(f"${{{var_name}}}", str(var_value))
        return json.loads(replace_content)

    @classmethod
    def _replace_variable(cls, view_config, target, value):
        """替换模版中的变量"""
        content = json.dumps(view_config)
        return json.loads(content.replace(target, json.dumps(str(value))[1:-1]))

    @classmethod
    def _add_functions(cls, view_config: dict[str, Any], functions: list[dict[str, Any]]):
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
    def _add_config_from_container(cls, app_name, service_name, view, view_config, display_with_sidebar):
        """获取容器 Pod 图表配置"""
        from monitor_web.scene_view.builtin.kubernetes import KubernetesBuiltinProcessor

        if not KubernetesBuiltinProcessor.builtin_views:
            KubernetesBuiltinProcessor.load_builtin_views()

        # 因为 kubernetes 场景不需要 type 字段(在接口处已处理) 这里查询 type 为空的数据
        pod_view = SceneViewModel.objects.filter(
            bk_biz_id=view.bk_biz_id,
            scene_id="kubernetes",
            name="pod",
            type="",
        )
        if pod_view.exists():
            pod_view = pod_view.first()
        else:
            create_default_views(bk_biz_id=view.bk_biz_id, scene_id="kubernetes", view_type="", existed_views=pod_view)
            pod_view = pod_view.first()

        pod_view_config = json.loads(json.dumps(KubernetesBuiltinProcessor.builtin_views["kubernetes-pod"]))
        pod_view = KubernetesBuiltinProcessor.get_pod_view_config(pod_view, pod_view_config, view_position="APM")

        # 调整配置
        pod_view["id"], pod_view["name"] = view_config["id"], view_config["name"]
        pod_view["options"] = view_config["options"]
        pod_view["variables"] = view_config["variables"]
        if "panels" in pod_view:
            pod_view["overview_panels"] = pod_view["panels"]
            del pod_view["panels"]

        if display_with_sidebar:
            pod_view["options"]["selector_panel"]["targets"][0]["data"].update(
                {
                    "app_name": app_name,
                    "service_name": service_name,
                }
            )
        else:
            pod_view["variables"][0]["targets"][0]["data"].update(
                {
                    "app_name": app_name,
                    "service_name": service_name,
                }
            )
            # 将图表的维度全部改为显示在下方 而不是右边
            for i in pod_view.get("overview_panels", []):
                for j in i.get("panels", []):
                    j.update({"options": {"legend": {"placement": "bottom", "displayMode": "list"}}})

        # 不展示事件页面 和 图表为空列表的分类
        o_views = []
        for i in pod_view["overview_panels"]:
            if i["id"] == "bk_monitor.time_series.k8s.events":
                continue
            if not i["panels"]:
                continue
            o_views.append(i)
        pod_view["overview_panels"] = o_views
        return pod_view

    @classmethod
    def _add_config_from_host(cls, view, view_config):
        """从主机监控中获取并增加配置"""
        from monitor_web.scene_view.builtin.host import get_auto_view_panels

        # 特殊处理服务主机页面 -> 为主机监控panel配置
        host_view = SceneViewModel.objects.filter(bk_biz_id=view.bk_biz_id, scene_id="host", type="detail")
        if not host_view.exists():
            create_default_views(bk_biz_id=view.bk_biz_id, scene_id="host", view_type="detail", existed_views=host_view)

        view_config["overview_panels"], view_config["order"] = get_auto_view_panels(view)
        if "overview_panel" in view_config.get("options"):
            # 去除顶部栏中的策略告警信息
            del view_config["options"]["overview_panel"]

    @classmethod
    def create_default_views(cls, bk_biz_id: int, scene_id: str, view_type: str, existed_views):
        cls.load_builtin_views()

        builtin_view_ids = {v.split("-", 1)[-1] for v in cls.builtin_views if v.startswith(f"{scene_id}-")}
        existed_view_ids: set[str] = {v.id for v in existed_views}
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
                        "container",
                        "log",
                        "event",
                        "profiling",
                        "custom_metric",
                    ]
                },
            )

    @classmethod
    def is_builtin_scene(cls, scene_id: str) -> bool:
        return scene_id.startswith(cls.SCENE_ID)

    @classmethod
    def _get_non_container_view_config(cls, builtin_view, params):
        return {
            "id": "container",
            "type": "overview",
            "mode": "auto",
            "name": _("k8s"),
            "panels": [],
            "overview_panels": [
                {
                    "id": 1,
                    "title": "",
                    "type": "exception-guide",
                    "targets": [
                        {
                            "data": {
                                "type": "empty",
                                "title": _("暂未发现关联 Pod"),
                                "subTitle": _(
                                    "如何发现容器信息:\n"
                                    "1. [推荐] 将上报地址切换为集群内上报，即可自动获取关联。\n"
                                    "2. 手动补充以下全部集群信息字段，也可以进行关联："
                                    "k8s.bcs.cluster.id(集群 Id), "
                                    "k8s.pod.name(Pod 名称), "
                                    "k8s.namespace.name(Pod 所在命名空间)。\n"
                                    "如果还是没有数据，可能是由于所选时间段的 Pod 已经销毁。\n",
                                ),
                            }
                        }
                    ],
                    "gridPos": {"x": 0, "y": 0, "w": 24, "h": 24},
                }
            ],
            "order": [],
        }

    @classmethod
    def _get_non_host_view_config(cls, builtin_view, params):
        # 不同场景下返回不同的无数据配置
        link = {}
        if builtin_view.startswith(cls.APM_TRACE_PREFIX):
            title = _("暂未在 Span 中发现主机")
            sub_title = _(
                "如何发现主机:\n1. 上报时增加 IP 信息。"
                "如果是非容器环境，"
                "需要补充 resource.net.host.ip(机器的 IP 地址) 字段。"
                "如果是容器环境，"
                "可将上报地址切换为集群内上报，即可自动获得关联。\n",
            )

        else:
            title = _("暂未发现主机")
            sub_title = _(
                "如何发现主机:\n1. 上报时增加IP信息。"
                "如果是非容器环境，"
                "需要补充 resource.net.host.ip(机器的 IP 地址) 字段。"
                "如果是容器环境，"
                "可将上报地址切换为集群内上报，即可自动获得关联。\n"
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
    def _generate_non_custom_metric_view_config(cls, view_config):
        view_config["variables"] = []
        view_config["options"] = {}
        view_config["overview_panels"] = [
            {
                "id": 1,
                "title": "",
                "type": "apm_custom_graph",
                "targets": [],
                "gridPos": {"x": 0, "y": 0, "w": 24, "h": 24},
            }
        ]

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
                "start_time": params.get("start_time"),
                "end_time": params.get("end_time"),
            }

        converted_params = {
            "app_name": params.get("apm_app_name"),
            "service_name": params.get("apm_service_name"),
            "only_simple_info": params.get("only_simple_info") or False,
            "view_switches": params.get("view_switches", {}),
        }
        # 自定义参数透传
        if scene_id == "apm_service" and params.get("id") in [
            "service-default-custom_metric",
            "service-default-container",
        ]:
            if "start_time" in params:
                converted_params["start_time"] = params["start_time"]
            if "end_time" in params:
                converted_params["end_time"] = params["end_time"]
        return converted_params

    @classmethod
    def is_custom_view_list(cls) -> bool:
        return True

    @classmethod
    def list_view_list(cls, scene_id, views: list[SceneViewModel], params):
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
            # 自定义服务 无实例、 Profiling 、 DB 、 k8s
            ignore_tabs = ["db", "instance", "profiling", "container"]
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
