# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import datetime
import json
import logging
import operator
from collections import defaultdict
from typing import List

from django.utils.translation import gettext_lazy as _lazy
from django.utils.translation import ugettext as _
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes
from rest_framework import serializers

from apm_web.constants import (
    APDEX_VIEW_ITEM_LEN,
    COLLECT_SERVICE_CONFIG_KEY,
    DEFAULT_EMPTY_NUMBER,
    AlertLevel,
    AlertStatus,
    Apdex,
    CategoryEnum,
    DataStatus,
    SceneEventKey,
    ServiceStatus,
    TopoNodeKind,
    component_where_mapping,
)
from apm_web.handlers.application_handler import ApplicationHandler
from apm_web.handlers.component_handler import ComponentHandler
from apm_web.handlers.host_handler import HostHandler
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.icon import get_icon
from apm_web.metric.handler.top_n import get_top_n_query_type, load_top_n_handler
from apm_web.metric_handler import (
    ApdexInstance,
    ApdexRange,
    AvgDurationInstance,
    ErrorRateInstance,
    RequestCountInstance,
)
from apm_web.metrics import (
    COMPONENT_DATA_STATUS,
    ENDPOINT_DETAIL_LIST,
    ENDPOINT_LIST,
    INSTANCE_LIST,
    REMOTE_SERVICE_DATA_STATUS,
    REMOTE_SERVICE_LIST,
    SERVICE_DATA_STATUS,
    SERVICE_LIST,
)
from apm_web.models import ApmMetaConfig, Application
from apm_web.profile.doris.querier import QueryTemplate
from apm_web.resources import (
    AsyncColumnsListResource,
    ServiceAndComponentCompatibleResource,
)
from apm_web.serializers import (
    AsyncSerializer,
    ComponentInstanceIdDynamicField,
    ServiceParamsSerializer,
)
from apm_web.utils import Calculator, group_by, handle_filter_fields
from bkmonitor.share.api_auth_resource import ApiAuthResource
from bkmonitor.utils.request import get_request
from constants.apm import ApmMetrics, OtlpKey, SpanKind
from core.drf_resource import Resource, api, resource
from core.unit import load_unit
from monitor_web.scene_view.resources.base import PageListResource
from monitor_web.scene_view.table_format import (
    CollectTableFormat,
    CustomProgressTableFormat,
    LinkListTableFormat,
    LinkTableFormat,
    NumberTableFormat,
    OverviewDataTableFormat,
    ProgressTableFormat,
    ServiceComponentAdaptLinkFormat,
    StackLinkOverviewDataTableFormat,
    StackLinkTableFormat,
    StatusTableFormat,
    StringLabelTableFormat,
    StringTableFormat,
    SyncTimeLinkTableFormat,
)

logger = logging.getLogger(__name__)


class UnifyQueryResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")
        unify_query_param = serializers.DictField(label="统一接口参数")

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]

        try:
            application = Application.objects.get(app_name=validated_request_data["app_name"], bk_biz_id=bk_biz_id)
        except Application.DoesNotExist:
            raise ValueError("Application does not exist")
        metric_result_table_id = application.metric_result_table_id
        unify_query_param = validated_request_data["unify_query_param"]
        for query_config in unify_query_param.get("query_configs", []):
            query_config["table"] = metric_result_table_id

        for param_key in ["start_time", "end_time", "bk_biz_id"]:
            unify_query_param[param_key] = validated_request_data[param_key]

        return resource.grafana.graph_unify_query(validated_request_data["unify_query_param"])


class DynamicUnifyQueryResource(Resource):
    """
    组件指标值查询
    不同分类的组件 查询unify-query参数会有所变化 此接口提供给apm_service-component-*.json使用
    """

    class RequestSerializer(serializers.Serializer):
        app_name = serializers.CharField(label="应用名称")
        service_name = serializers.CharField(label="服务名称")
        category = serializers.CharField(label="分类")
        kind = serializers.CharField(label="类型")
        predicate_value = serializers.CharField(label="具体值", allow_blank=True)
        unify_query_param = serializers.DictField(label="unify-query参数")

        bk_biz_id = serializers.IntegerField(label="业务ID")
        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")
        component_instance_id = ComponentInstanceIdDynamicField(required=False, label="组件实例id(组件页面下有效)")

    def perform_request(self, validate_data):
        unify_query_params = {
            **validate_data["unify_query_param"],
            "start_time": validate_data["start_time"],
            "end_time": validate_data["end_time"],
            "bk_biz_id": validate_data["bk_biz_id"],
        }

        resource.monitor_web.grafana.graph_unify_query.RequestSerializer(data=unify_query_params).is_valid(
            raise_exception=True
        )

        # 替换service_name
        pure_service_name = ComponentHandler.get_component_belong_service(
            validate_data["service_name"], validate_data["predicate_value"]
        )

        if validate_data["category"] not in component_where_mapping:
            raise ValueError(_lazy(f"组件指标值查询不支持{validate_data['category']}分类"))

        # 追加where条件
        for config in unify_query_params["query_configs"]:
            # 增加组件实例查询条件
            if validate_data.get("component_instance_id"):
                component_filter = ComponentHandler.get_component_instance_query_params(
                    validate_data["bk_biz_id"],
                    validate_data["app_name"],
                    validate_data["kind"],
                    validate_data["category"],
                    validate_data["component_instance_id"],
                    config["where"],
                    template=ComponentHandler.unify_query_operator,
                    key_generator=OtlpKey.get_metric_dimension_key,
                )
                config["where"] += component_filter
            else:
                # 没有组件实例时 单独添加组件类型的条件
                where = component_where_mapping[validate_data["category"]]
                if validate_data.get("predicate_value"):
                    config["where"].append(
                        json.loads(json.dumps(where).replace("{predicate_value}", validate_data["predicate_value"]))
                    )

        # 替换service名称
        unify_query_params = json.loads(
            json.dumps(unify_query_params).replace(validate_data["service_name"], pure_service_name)
        )

        return resource.grafana.graph_unify_query(unify_query_params)


class ServiceListResource(PageListResource):
    """服务列表接口"""

    def get_columns(self, column_type=None):
        return [
            CollectTableFormat(
                id="collect",
                name=_lazy("收藏"),
                checked=True,
                width=80,
                api="apm_metric.collectService",
                params_get=lambda item: {
                    "service_name": item["service_name"],
                    "app_name": item["app_name"],
                },
                filterable=True,
                disabled=True,
            ),
            SyncTimeLinkTableFormat(
                id="service_name",
                width=200,
                name=_lazy("服务名称"),
                checked=True,
                url_format="/service/?filter-service_name={service_name}"
                "&filter-app_name={app_name}"
                "&filter-category={category}"
                "&filter-kind={kind}"
                "&filter-predicate_value={predicate_value}",
                icon_get=lambda row: get_icon(row["service_name"].split(":")[0])
                if row["kind"] == TopoNodeKind.REMOTE_SERVICE
                else get_icon(row["category"]),
                sortable=True,
                disabled=True,
            ),
            StringTableFormat(
                id="type",
                name=_lazy("类型"),
                checked=False,
                filterable=True,
                display_handler=lambda d: d.get("view_mode") == self.RequestSerializer.VIEW_MODE_SERVICES,
            ),
            StringTableFormat(
                id="language",
                name=_lazy("语言"),
                checked=False,
                filterable=True,
                display_handler=lambda d: d.get("view_mode") == self.RequestSerializer.VIEW_MODE_SERVICES,
            ),
            StatusTableFormat(
                id="status", name=_lazy("Tracing 状态"), checked=True, status_map_cls=DataStatus, filterable=True
            ),
            NumberTableFormat(id="request_count", name=_lazy("调用次数"), checked=True, sortable=True, asyncable=True),
            ProgressTableFormat(id="error_rate", name=_lazy("错误率"), sortable=True, asyncable=True),
            NumberTableFormat(
                id="avg_duration",
                name=_lazy("平均响应耗时"),
                checked=True,
                unit="ns",
                decimal=2,
                sortable=True,
                asyncable=True,
            ),
            NumberTableFormat(
                id="strategy_count",
                name=_lazy("策略数"),
                checked=True,
                decimal=0,
                sortable=True,
                display_handler=lambda d: d.get("view_mode") == self.RequestSerializer.VIEW_MODE_SERVICES,
            ),
            StatusTableFormat(
                id="alert_status",
                name=_lazy("告警状态"),
                checked=True,
                status_map_cls=ServiceStatus,
                filterable=True,
                display_handler=lambda d: d.get("view_mode") == self.RequestSerializer.VIEW_MODE_SERVICES,
            ),
            StatusTableFormat(
                id="profiling_data_status",
                name=_lazy("Profiling 状态"),
                checked=True,
                status_map_cls=DataStatus,
                filterable=True,
            ),
            NumberTableFormat(
                id="profiling_data_count",
                name=_lazy("数据量"),
                checked=True,
                decimal=0,
                sortable=True,
                asyncable=True,
            ),
            LinkListTableFormat(
                id="operation",
                name=_lazy("操作"),
                checked=True,
                links=[
                    LinkTableFormat(
                        id="config",
                        name=_lazy("配置"),
                        url_format="/service-config?app_name={app_name}&service_name={service_name}",
                    ),
                ],
                disabled=True,
                link_handler=lambda i: i.get("kind") in [TopoNodeKind.SERVICE, TopoNodeKind.REMOTE_SERVICE],
                display_handler=lambda d: d.get("view_mode") == self.RequestSerializer.VIEW_MODE_SERVICES,
            ),
        ]

    class RequestSerializer(serializers.Serializer):
        # 服务列表有两种观察模式 一种是首页 另一个是服务列表 两个返回的 columns 不一致 所以加以区分
        VIEW_MODE_HOME = "page_home"
        VIEW_MODE_SERVICES = "page_services"

        VIEW_MODE_CHOICES = (
            (VIEW_MODE_HOME, "首页"),
            (VIEW_MODE_SERVICES, "服务列表页"),
        )

        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称")
        keyword = serializers.CharField(required=False, label="查询关键词", allow_blank=True)
        start_time = serializers.IntegerField(required=True, label="数据开始时间")
        end_time = serializers.IntegerField(required=True, label="数据结束时间")
        page = serializers.IntegerField(required=False, label="页码")
        page_size = serializers.IntegerField(required=False, label="每页条数")
        sort = serializers.CharField(required=False, label="排序方式", allow_blank=True)
        filter = serializers.CharField(required=False, label="筛选条件", allow_blank=True)
        filter_dict = serializers.DictField(required=False, label="筛选条件", default={})
        view_mode = serializers.ChoiceField(
            required=False,
            label="展示模式",
            choices=VIEW_MODE_CHOICES,
            default=VIEW_MODE_SERVICES,
        )

        def validate_filter(self, value):
            if value == CategoryEnum.ALL:
                return ""
            return value

    def get_filter_fields(self):
        return ["service_name", "language", "http"]

    def get_sort_fields(self):
        return ["-collect", "-strategy_count", "-error_rate", "-avg_duration", "-request_count"]

    def combine_data(
        self,
        services: List[dict],
        config: ApmMetaConfig,
        app_name: str,
        strategy_service_map: dict,
        strategy_alert_map: dict,
        request_count_info: dict,
        profiling_count_info: dict,
    ):
        return [
            {
                "collect": service["topo_key"] in config.config_value,
                "service_name": service["topo_key"],
                "type": CategoryEnum.get_label_by_key(service["extra_data"]["category"]),
                "language": service["extra_data"]["service_language"],
                "strategy_count": strategy_service_map.get(service["topo_key"], DEFAULT_EMPTY_NUMBER),
                "alert_status": strategy_alert_map.get(service["topo_key"], ServiceStatus.NORMAL),
                "category": service["extra_data"]["category"],
                "kind": service["extra_data"]["kind"],
                "operation": {
                    "config": _lazy("配置"),
                    "relation": _lazy("关联"),
                },
                "app_name": app_name,
                "predicate_value": service["extra_data"]["predicate_value"],
                "status": DataStatus.NORMAL
                if request_count_info.get(service["topo_key"], {}).get("request_count")
                else DataStatus.NO_DATA,
                "profiling_data_status": DataStatus.NORMAL
                if profiling_count_info.get(service["topo_key"], {}).get("profiling_data_count")
                else DataStatus.NO_DATA,
            }
            for service in services
        ]

    def keyword_filter(self, data: List, keyword: str = None, filter_param: str = None):
        if not keyword and not filter_param:
            return data
        if filter_param:
            data = [service_data for service_data in data if service_data["category"] == filter_param]
        return data

    def has_service_condition(self, strategy: dict):
        resp = [False, set()]
        # 逐条遍历 items
        for item in strategy.get("items", []):
            for query_config in item.get("query_configs", []):
                for condition in query_config.get("agg_condition", []):
                    # 含有 service name
                    if condition.get("key") == "service_name":
                        resp[0] = True
                        resp[1].update(condition.get("value", []))
        return resp

    def combine_strategy_with_alert(self, app: Application, start_time: int, end_time: int):
        # 获取策略信息
        query_params = {
            "bk_biz_id": app.bk_biz_id,
            "conditions": [
                {
                    "key": "metric_id",
                    "value": [f"custom.{app.metric_result_table_id}.{m}" for m, _, _ in ApmMetrics.all()],
                }
            ],
            "page": 0,
        }
        strategies = resource.strategies.get_strategy_list_v2(**query_params).get("strategy_config_list", [])
        strategy_map = {strategy["id"]: strategy for strategy in strategies}
        # 获取告警信息
        query_params = {
            "bk_biz_ids": [app.bk_biz_id],
            "conditions": [
                {
                    "key": "metric_id",
                    "value": [f"custom.{app.metric_result_table_id}.{m}" for m, _, _ in ApmMetrics.all()],
                }
            ],
            "start_time": start_time,
            "end_time": end_time,
        }
        alert_infos = resource.fta_web.alert.search_alert(**query_params).get("alerts", [])
        # 组装告警信息到策略信息中
        for alert_info in alert_infos:
            strategy = strategy_map.get(alert_info["strategy_id"])
            # 只展示未处理的最高级别告警
            if (
                strategy is not None
                and not alert_info["is_handled"]
                and strategy.get("severity", ServiceStatus.NORMAL) > alert_info["severity"]
            ):
                strategy["severity"] = alert_info["severity"]
        return strategy_map

    def perform_request(self, validate_data):
        start_time = validate_data["start_time"]
        end_time = validate_data["end_time"]
        # 获取应用
        app = Application.objects.filter(
            bk_biz_id=validate_data["bk_biz_id"], app_name=validate_data["app_name"]
        ).first()
        if not app:
            raise ValueError(_lazy("应用{}不存在").format(validate_data['app_name']))

        # 获取应用的服务列表
        services = ServiceHandler.list_services(app)
        # 获取服务的收藏信息
        config = CollectServiceResource.get_collect_config(app)

        # 获取策略信息
        strategy_map = self.combine_strategy_with_alert(app, start_time, end_time)
        strategy_service_map = defaultdict(int)
        strategy_alert_map = defaultdict(ServiceStatus.get_default)
        for strategy in strategy_map.values():
            has_service, service_list = self.has_service_condition(strategy)
            if has_service:
                for name in service_list:
                    strategy_service_map[name] += 1
                    # 已有告警级别没有策略告警级别高才更新
                    if strategy_alert_map[name] > strategy.get("severity", ServiceStatus.NORMAL):
                        strategy_alert_map[name] = strategy.get("severity", ServiceStatus.NORMAL)

        # 仅获取状态列 其他列通过异步接口获取
        request_count_info = {
            **SERVICE_DATA_STATUS(app, start_time=validate_data["start_time"], end_time=validate_data["end_time"]),
            **REMOTE_SERVICE_DATA_STATUS(
                app, start_time=validate_data["start_time"], end_time=validate_data["end_time"]
            ),
            **ComponentHandler.get_service_component_name_metrics(
                app,
                validate_data["start_time"],
                validate_data["end_time"],
                COMPONENT_DATA_STATUS,
            ),
        }
        # 获取 profile 服务指标
        if app.is_enabled_profiling:
            profiling_request_info = QueryTemplate(
                validate_data["bk_biz_id"], validate_data["app_name"]
            ).list_services_request_info(validate_data["start_time"] * 1000, validate_data["end_time"] * 1000)
        else:
            profiling_request_info = {}

        # 处理响应数据
        raw_data = self.combine_data(
            services,
            config,
            validate_data["app_name"],
            strategy_service_map,
            strategy_alert_map,
            request_count_info,
            profiling_request_info,
        )

        filtered_data = self.keyword_filter(raw_data, validate_data["keyword"], validate_data["filter"])
        paginated_data = self.get_pagination_data(filtered_data, validate_data)
        paginated_data["filter"] = CategoryEnum.get_filter_fields()
        return paginated_data


class ServiceListAsyncResource(AsyncColumnsListResource):
    """
    服务列表异步接口
    """

    SyncResource = ServiceListResource

    class RequestSerializer(AsyncSerializer):
        app_name = serializers.CharField(label="应用名称")
        service_names = serializers.ListSerializer(child=serializers.CharField(), default=[], label="服务列表")
        start_time = serializers.IntegerField(required=True, label="数据开始时间")
        end_time = serializers.IntegerField(required=True, label="数据结束时间")

    def perform_request(self, validated_data):
        res = []
        if not validated_data.get("service_names"):
            return res

        app = Application.objects.filter(
            bk_biz_id=validated_data["bk_biz_id"], app_name=validated_data["app_name"]
        ).first()
        if not app:
            raise ValueError(_("应用{}不存在").format(validated_data['app_name']))

        service_metric_info = {
            **SERVICE_LIST(app, start_time=validated_data["start_time"], end_time=validated_data["end_time"]),
            **REMOTE_SERVICE_LIST(app, start_time=validated_data["start_time"], end_time=validated_data["end_time"]),
        }
        component_metric_info = ComponentHandler.get_service_component_metrics(
            app,
            validated_data["start_time"],
            validated_data["end_time"],
        )
        if app.is_enabled_profiling:
            profiling_metric_info = QueryTemplate(
                validated_data["bk_biz_id"], validated_data["app_name"]
            ).list_services_request_info(validated_data["start_time"] * 1000, validated_data["end_time"] * 1000)
        else:
            profiling_metric_info = {}

        services = ServiceHandler.list_services(app)
        column = validated_data["column"]
        for service_name in validated_data["service_names"]:
            service = next((i for i in services if i["topo_key"] == service_name), None)
            if not service:
                continue

            metric_info = {}
            if service["extra_data"]["kind"] == TopoNodeKind.REMOTE_SERVICE:
                metric_info = service_metric_info.get(service_name.split(":")[-1], {})
            elif service["extra_data"]["kind"] == TopoNodeKind.SERVICE:
                metric_info = service_metric_info.get(service_name, {})
            elif service["extra_data"]["kind"] == TopoNodeKind.COMPONENT:
                metric_info = component_metric_info.get(service["from_service"], {}).get(
                    service["extra_data"]["predicate_value"], {}
                )

            if service["topo_key"] in profiling_metric_info:
                # 补充 profiling 数据
                metric_info.update(profiling_metric_info[service["topo_key"]])

            res.append({"service_name": service_name, **self.get_async_column_item(metric_info, column)})

        return self.get_async_data(res, validated_data["column"])


class CollectServiceResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        service_name = serializers.CharField(label="服务名称", required=False, allow_blank=True)

    def add_or_remove(self, config_instance: ApmMetaConfig, service_name: str):
        if service_name in config_instance.config_value:
            config_instance.config_value.remove(service_name)
        else:
            config_instance.config_value.append(service_name)
        config_instance.save()

    @staticmethod
    def get_collect_config(app: Application):
        try:
            return ApmMetaConfig.objects.get(
                config_level=ApmMetaConfig.APPLICATION_LEVEL,
                level_key=app.application_id,
                config_key=COLLECT_SERVICE_CONFIG_KEY,
            )
        except ApmMetaConfig.DoesNotExist:
            return ApmMetaConfig(
                config_level=ApmMetaConfig.APPLICATION_LEVEL,
                level_key=app.application_id,
                config_key=COLLECT_SERVICE_CONFIG_KEY,
                config_value=[],
            )

    @staticmethod
    def get_or_create_collect(app: Application, service_name: str):
        return ApmMetaConfig.objects.get_or_create(
            config_level=ApmMetaConfig.APPLICATION_LEVEL,
            level_key=app.application_id,
            config_key=COLLECT_SERVICE_CONFIG_KEY,
            defaults={"config_value": [service_name] if service_name is not None else []},
        )

    def perform_request(self, validated_request_data):
        # 获取应用id
        try:
            app = Application.objects.get(
                bk_biz_id=validated_request_data["bk_biz_id"], app_name=validated_request_data["app_name"]
            )
        except Application.DoesNotExist:
            raise ValueError(_lazy("应用不存在"))
        # 获取配置信息
        config, is_created = self.get_or_create_collect(app, validated_request_data["service_name"])
        # 新创建直接返回
        if is_created:
            return
        # 收藏或取消收藏
        self.add_or_remove(config, validated_request_data["service_name"])
        return


class InstanceListResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        service_name = serializers.CharField(label="服务名称", required=False, allow_blank=True)
        keyword = serializers.CharField(label="关键字", required=False, allow_blank=True)
        service_params = ServiceParamsSerializer(required=False, label="服务节点额外参数")
        category = serializers.ListField(label="分类", required=False, default=[])

    def perform_request(self, validated_request_data):
        query_dict = {"bk_biz_id": validated_request_data["bk_biz_id"], "app_name": validated_request_data["app_name"]}
        if "service_name" in validated_request_data.keys():
            query_dict["service_name"] = [validated_request_data["service_name"]]

        if ComponentHandler.is_component(validated_request_data.get("service_params")):
            service_params = validated_request_data["service_params"]
            if "service_name" in query_dict:
                query_dict["service_name"] = [
                    ComponentHandler.get_component_belong_service(
                        query_dict["service_name"][0], service_params["predicate_value"]
                    )
                ]
            query_dict["filters"] = {
                "instance_topo_kind": TopoNodeKind.COMPONENT,
                "component_instance_category": service_params["category"],
                "component_instance_predicate_value": service_params["predicate_value"],
            }
        elif validated_request_data.get("category"):
            query_dict["filters"] = {
                "component_instance_category__in": validated_request_data.get("category"),
                "instance_topo_kind": TopoNodeKind.COMPONENT,
            }
        else:
            query_dict["filters"] = {"instance_topo_kind": TopoNodeKind.SERVICE}

        instances = api.apm_api.query_instance(query_dict).get("data", [])
        data = []
        for instance in instances:
            data.append(
                {
                    "id": instance["instance_id"],
                    "name": instance["instance_id"],
                    "topo_node_key": instance["topo_node_key"],
                    "service_name": instance["topo_node_key"],
                    "app_name": validated_request_data["app_name"],
                }
            )
        return self.filter_keyword(data, validated_request_data.get("keyword"))

    def filter_keyword(self, data, keyword):
        if not keyword:
            return data

        res = []
        for item in data:
            if keyword.lower() in item["name"].lower():
                res.append(item)

        return res


class ErrorListResource(ServiceAndComponentCompatibleResource):
    app_name = ""
    UNKNOWN_EXCEPTION_TYPE = "unknown"

    need_dynamic_sort_column = True
    need_overview = True

    return_time_range = True
    timestamp_fields = ["start_time", "end_time"]

    def get_sort_fields(self):
        return ["error_count"]

    def get_filter_fields(self):
        return ["service", "exception_type", "endpoint"]

    def get_status_filter(self):
        # 状态过滤条件
        return [{"id": "has_stack", "name": _lazy("有堆栈")}]

    def get_columns(self, column_type=None):
        service_format = LinkTableFormat(
            id="service",
            name=_lazy("服务"),
            checked=True,
            target="blank",
            event_key=SceneEventKey.SWITCH_SCENES_TYPE,
            filterable=True,
            url_format="/?bizId={bk_biz_id}/#/apm/service/?filter-service_name={service}"
            + "&filter-app_name={app_name}&"
            "filter-category={service_category}&"
            "filter-kind={service_kind}&"
            "filter-predicate_value={service_predicate_value}",
            min_width=120,
        )
        if column_type:
            service_format = ServiceComponentAdaptLinkFormat(
                id="service",
                name=_lazy("服务"),
                checked=True,
                target="event",
                event_key=SceneEventKey.SWITCH_SCENES_TYPE,
                filterable=True,
                url_format="/service/?filter-service_name={service}" + "&filter-app_name={app_name}&"
                "filter-category={service_category}&"
                "filter-kind={service_kind}&"
                "filter-predicate_value={service_predicate_value}&"
                "dashboardId=service-default-overview&sceneId=apm_service&sceneType=overview",
                min_width=120,
            )

        return [
            StackLinkOverviewDataTableFormat(
                id="message",
                title=_lazy("错误概览"),
                name=_lazy("错误"),
                checked=True,
                disabled=True,
                width=248,
                min_width=120,
                max_width=400,
            ),
            StringTableFormat(
                id="endpoint",
                name="Span Name",
                checked=True,
                min_width=120,
            ),
            StringLabelTableFormat(
                id="category",
                name=_lazy("分类"),
                checked=True,
                filterable=True,
                label_getter=CategoryEnum.get_label_by_key,
                icon_getter=lambda row: get_icon(row["category"]),
                min_width=120,
            ),
            service_format,
            StringTableFormat(id="first_time", name=_lazy("首次出现时间"), checked=True),
            StringTableFormat(id="last_time", name=_lazy("最新出现时间"), checked=True),
            CustomProgressTableFormat(
                id="error_count",
                name=_lazy("错误次数"),
                checked=True,
                overview_calculator=Calculator.sum(),
                color_getter=lambda _: "FAILED",
                max_if_overview=True,
                min_width=120,
                clear_if_not_sorted=True,
            ),
            LinkListTableFormat(
                id="operations",
                name=_lazy("操作"),
                links=[
                    LinkTableFormat(
                        id="operate",
                        name=_lazy("调用链"),
                        url_format='/?bizId={bk_biz_id}/#/trace/home/?app_name={app_name}'
                        + '&search_type=scope'
                        + '&start_tiem={start_time}&end_tiem={end_time}'
                        + '&conditionList={{"resource.service.name": '
                        '{{"selectedCondition": {{"label": "=","value": "equal"}},'
                        '"selectedConditionValue": ["{service}"]}},'
                        '"span_name": {{"selectedCondition": {{"label": "=","value": "equal"}},'
                        '"selectedConditionValue": ["{endpoint}"]}}}}' + '&query=status.code:+2+',
                        target="blank",
                        event_key=SceneEventKey.SWITCH_SCENES_TYPE,
                    ),
                ],
                min_width=120,
            ),
        ]

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")
        keyword = serializers.CharField(label="关键字", allow_blank=True)
        filter = serializers.CharField(label="条件", allow_blank=True, default="")
        service_name = serializers.CharField(label="服务", allow_blank=True, default="")
        page = serializers.IntegerField(required=False, label="页码")
        page_size = serializers.IntegerField(required=False, label="每页条数")
        sort = serializers.CharField(required=False, label="排序方法", allow_blank=True)
        filter_dict = serializers.DictField(required=False, label="筛选条件", default={})
        filter_fields = serializers.DictField(required=False, label="匹配条件", default={})
        check_filter_dict = serializers.DictField(required=False, label="勾选条件", default={})
        status = serializers.CharField(required=False, label="状态筛选")
        service_params = ServiceParamsSerializer(required=False, label="服务节点额外参数")

        def validate_filter(self, value):
            if value == "all":
                return ""
            return value

    def list_error_event_spans(self, data):
        bk_biz_id = data["bk_biz_id"]
        app_name = data["app_name"]

        query_params = {
            "bk_biz_id": data["bk_biz_id"],
            "app_name": data["app_name"],
            "filter_params": [{"key": "status.code", "op": "=", "value": ["2"]}],
            "start_time": data["start_time"],
            "end_time": data["end_time"],
        }

        # 分类可以通过两种方式进行查询
        # 1. 通过filter_dict: {"category": "http"}
        # 2. 通过filter: "http"
        if data["filter"]:
            query_params["category"] = data["filter"]

        if data["service_name"]:
            # 如果是服务下错误->判断此服务是否是自定义服务
            if ServiceHandler.is_remote_service(bk_biz_id, app_name, data["service_name"]):
                query_params["filter_params"].append(
                    {
                        "key": OtlpKey.get_attributes_key(SpanAttributes.PEER_SERVICE),
                        "op": "=",
                        "value": [data["service_name"].split(":")[-1]],
                    }
                )
            else:
                query_params["filter_params"].append(
                    {
                        "key": OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME),
                        "op": "=",
                        "value": [data["service_name"]],
                    }
                )

        ComponentHandler.build_component_filter_params(
            data["bk_biz_id"], data["app_name"], query_params["filter_params"], data.get("service_params")
        )
        return api.apm_api.query_span(query_params)

    def format_time(self, time_int):
        return datetime.datetime.fromtimestamp(int(time_int) // 1000).strftime("%Y-%m-%d %H:%M:%S")

    def compare_time(self, times: list):
        times.sort()
        max_length = len(times)
        return self.format_time(times[0]), self.format_time(times[max_length - 1])

    def compare_message(self, messages):
        for message in messages:
            if message:
                return message
        return None

    def compare_exception_type(self, exception_types):
        for i in exception_types:
            if i:
                return i

        return None

    def has_events(self, events):
        for event in events:
            if event["name"] == "exception":
                return True
        return False

    def compare_exception_stacks(self, exception_stacks):
        for i in exception_stacks:
            if i:
                return i

        return None

    def combine_errors(self, bk_biz_id, service_mappings, trace_ids, service, endpoint, errors):
        times = set()
        exception_types = set()

        error_count = DEFAULT_EMPTY_NUMBER
        has_exception = False
        for error in errors:
            error_count += 1
            times.add(error["time"])
            exception_types |= {i.get("attributes", {}).get("exception.type") for i in error["events"]}
            if not has_exception:
                has_exception = self.has_events(error["events"])
        first_time, last_time = self.compare_time(list(times))
        exception_type = self.compare_exception_type(list(exception_types))
        exception_type = exception_type if exception_type else self.UNKNOWN_EXCEPTION_TYPE

        trace_id = trace_ids[-1]

        return {
            "bk_biz_id": bk_biz_id,
            "first_time": first_time,
            "last_time": last_time,
            "endpoint": endpoint,
            "message": {
                "title": f"{endpoint}: {exception_type}",
                "subtitle": "",  # 保持原框架 subtitle值为空
                "is_stack": _lazy("有Stack") if has_exception else _lazy("没有Stack"),
            },
            "category": service_mappings.get(service, {}).get("extra_data", {}).get("category"),
            "error_count": error_count,
            "service": service,
            "trace_id": trace_id,
            "app_name": self.app_name,
            "operations": {"operate": _lazy("调用链")},
            "exception_type": exception_type,
        }

    def handle_error_map(self, error_map, key, service, endpoint, span):
        if key in error_map:
            error_map[key]["trace_ids"].append(span["trace_id"])
            error_map[key]["errors"].append(span)
        else:
            error_map[key] = {
                "service": service,
                "endpoint": endpoint,
                "errors": [span],
                "trace_ids": [span["trace_id"]],
            }

    def parse_errors(self, bk_biz_id, error_spans):
        # 获取service
        service_mappings = {
            i["topo_key"]: i for i in api.apm_api.query_topo_node({"bk_biz_id": bk_biz_id, "app_name": self.app_name})
        }

        error_map = {}

        has_event_trace_id = [i["trace_id"] for i in error_spans if i["events"]]

        for span in error_spans:
            service = span[OtlpKey.RESOURCE].get(ResourceAttributes.SERVICE_NAME)
            if not service:
                continue

            endpoint = span[OtlpKey.SPAN_NAME]

            if span["events"]:
                for event in span["events"]:
                    exception_type = event[OtlpKey.ATTRIBUTES].get(
                        SpanAttributes.EXCEPTION_TYPE, self.UNKNOWN_EXCEPTION_TYPE
                    )
                    key = (service, endpoint, exception_type)

                    self.handle_error_map(error_map, key, service, endpoint, span)
            else:
                exception_type = self.UNKNOWN_EXCEPTION_TYPE
                key = (service, endpoint, exception_type)
                if span["trace_id"] not in has_event_trace_id:
                    self.handle_error_map(error_map, key, service, endpoint, span)

        return [
            self.combine_errors(bk_biz_id, service_mappings, **service_error_map)
            for service_error_map in error_map.values()
        ]

    def has_stack_filter(self, data, validated_data):
        """
        过滤是否有堆栈
        同时兼容两种的过滤方式:
        1. 通过stats:"has_stack" 过滤有堆栈
        2. 通过check_filter_dict: {"is_stack": True}
        """
        filter_from_filter_dict = validated_data.get("check_filter_dict", {}).get("is_stack", False)
        filter_from_status = validated_data.get("status") == "has_stack"

        if filter_from_filter_dict or filter_from_status:
            res = []
            for item in data:
                if True if item["message"]["is_stack"] == _lazy("有Stack") else False:
                    res.append(item)

            return res

        return data

    def get_data(self, data):
        self.app_name = data["app_name"]
        error_spans = self.list_error_event_spans(data)
        error_data = self.parse_errors(data["bk_biz_id"], error_spans)
        return self.has_stack_filter(error_data, data)

    def perform_request(self, data):
        error_data = self.get_data(data)
        # 统计错误次数百分比 此接口在多处用到(告警中心trace错误) 故暂不从get_data方法更改
        error_all_count = sum([i.get("error_count") for i in error_data])

        for i in error_data:
            i["error_count"] = {
                "value": round((i["error_count"] / error_all_count) * 100, 2) if error_all_count else 0,
                "label": i["error_count"],
            }

        error_data = handle_filter_fields(
            error_data, data.get("filter_fields"), value_getter=lambda k, i: i.get("title") if k == "message" else i
        )
        paginated_data = self.get_pagination_data(error_data, data, data["service_name"])
        paginated_data["filter"] = self.get_status_filter()
        return paginated_data

    def get_pagination_data(self, origin_data, params, column_type=None):
        data = super(ErrorListResource, self).get_pagination_data(origin_data, params, column_type)

        # 因为在组件页面下 点击侧边栏需要传递额外参数 所以这里兼容组件的页面配置(见组件错误页面配置selector_panel.target.fields)
        component_extra_data = ["category", "kind", "predicate_value", "service_name"]

        param = {
            **params.get("service_params", {}),
            "service_name": params.get("service_name"),
        }

        is_all_exists = all(bool(param.get(i)) for i in component_extra_data)
        if not is_all_exists:
            return data

        add_data = {}
        for key in component_extra_data:
            add_data[f"component_{key}"] = param[key]

        for i in data["data"]:
            i.update(add_data)

        return data


class TopNQueryResource(ApiAuthResource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")
        size = serializers.IntegerField(label="查询数量", default=5)
        query_type = serializers.ChoiceField(label="查询类型", choices=get_top_n_query_type())
        filter_dict = serializers.DictField(label="过滤条件", required=False)
        service_params = ServiceParamsSerializer(required=False, label="服务节点额外参数")

    def perform_request(self, validated_request_data):
        start_time = validated_request_data["start_time"]
        end_time = validated_request_data["end_time"]
        try:
            application = Application.objects.get(
                app_name=validated_request_data["app_name"], bk_biz_id=validated_request_data["bk_biz_id"]
            )
        except Application.DoesNotExist:
            raise ValueError("Application does not exist")
        result = load_top_n_handler(validated_request_data["query_type"])(
            application,
            start_time,
            end_time,
            validated_request_data["size"],
            validated_request_data.get("filter_dict"),
            validated_request_data.get("service_params"),
        ).get_topo_n_data()
        return {"data": result}


class ApdexQueryResource(ApiAuthResource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        app_name = validated_request_data["app_name"]
        start_time = validated_request_data["start_time"]
        end_time = validated_request_data["end_time"]
        try:
            application = Application.objects.get(app_name=app_name, bk_biz_id=bk_biz_id)
        except Application.DoesNotExist:
            raise ValueError("Application does not exist")

        if ApplicationHandler.have_data(application, start_time, end_time):
            interval = (end_time - start_time) // APDEX_VIEW_ITEM_LEN
            return ApdexRange(application, start_time, end_time, interval=interval).query_range()
        return {"metrics": [], "series": []}


class EndpointDetailListResource(Resource):
    STATUS_SORT = ["success", "failed", "disabled"]

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        service_name = serializers.CharField(label="服务名称", required=False, default="")
        show_type = serializers.CharField(label="显示类型", default="list")
        filter = serializers.CharField(label="条件", allow_blank=True, required=False)
        keyword = serializers.CharField(label="关键词", allow_blank=True, required=False)

    def get_status(self, metric):
        if not metric:
            return {"text": _lazy("无数据"), "type": "disabled"}

        if metric.get("error_count", 0):
            return {
                "text": _lazy("异常"),
                "type": "failed",
            }
        if metric.get("request_count", 0):
            return {
                "text": _lazy("正常"),
                "type": "success",
            }
        return {"text": _lazy("无数据"), "type": "disabled"}

    def filter_keyword(self, data, keyword):
        if not keyword:
            return data

        res = []
        for item in data:
            if keyword.lower() in item["name"].lower():
                res.append(item)

        return res

    def calc_percecnt(self, item_count, all_count):
        return round((item_count / all_count) * 100, 2) if all_count else 0

    def perform_request(self, validated_request_data):
        try:
            app = Application.objects.get(
                app_name=validated_request_data["app_name"], bk_biz_id=validated_request_data["bk_biz_id"]
            )
        except Application.DoesNotExist:
            raise ValueError("Application does not exist")

        query_params = {
            "bk_biz_id": validated_request_data["bk_biz_id"],
            "app_name": validated_request_data["app_name"],
            "service_name": validated_request_data["service_name"],
        }
        if validated_request_data.get("filter"):
            query_params["category"] = validated_request_data["filter"]

        endpoints = api.apm_api.query_endpoint(query_params)
        endpoints_metric = ENDPOINT_DETAIL_LIST(app)
        endpoint_set = set()

        status_count = {"success": 0, "failed": 0, "disabled": 0}
        request_all_count = sum([i.get("request_count", 0) for i in endpoints_metric.values()])
        error_all_count = sum([i.get("error_count", 0) for i in endpoints_metric.values()])
        duration_all_count = sum([i.get("avg_duration") for i in endpoints_metric.values()])

        if validated_request_data["show_type"] == "topo":
            res = []
            for endpoint in endpoints:
                service_name = endpoint["service_name"]
                endpoint_name = endpoint["endpoint_name"]
                name = f"{service_name}: {endpoint_name}"
                endpoint_id = f"{endpoint_name}|{service_name}"

                endpoint_metric = endpoints_metric.get(
                    endpoint_id, {"request_count": 0, "error_count": 0, "avg_duration": 0}
                )
                status_count[self.get_status(endpoint_metric)["type"]] += 1

                if endpoint_id in endpoint_set:
                    continue
                endpoint_set.add(endpoint_id)

                request_percent = self.calc_percecnt(endpoint_metric.get("request_count", 0), request_all_count)
                error_percent = self.calc_percecnt(endpoint_metric.get("error_count", 0), error_all_count)
                avg_percent = self.calc_percecnt(endpoint_metric.get("avg_duration", 0), duration_all_count)

                res.append(
                    {
                        "id": f"{validated_request_data['app_name']}|{service_name}|{endpoint_name}",
                        "name": name,
                        "app_name": validated_request_data["app_name"],
                        "service_name": service_name,
                        "endpoint": endpoint_name,
                        "status": self.get_status(endpoint_metric),
                        "metric": {
                            "request_count": {
                                "value": endpoint_metric.get("request_count", 0),
                                "percent": request_percent,
                            },
                            "error_count": {
                                "value": endpoint_metric.get("error_count", 0),
                                "percent": error_percent,
                            },
                            "avg_duration": {
                                "value": endpoint_metric.get("avg_duration", 0),
                                "percent": avg_percent,
                            },
                        },
                    }
                )

            for item in res:
                value, unit = load_unit("ns").auto_convert(item["metric"]["avg_duration"]["value"], decimal=2)
                item["metric"]["avg_duration"]["value"] = f"{value}{unit}"

            return {
                "data": self.filter_keyword(res, validated_request_data.get("keyword")),
                "filter": [
                    {"id": "success", "status": "success", "name": status_count["success"], "tips": _lazy("1小时内无异常")},
                    {"id": "failed", "status": "failed", "name": status_count["failed"], "tips": _lazy("1小时内有异常")},
                    {
                        "id": "disabled",
                        "status": "disabled",
                        "name": status_count["disabled"],
                        "tips": _lazy("1小时内无数据"),
                    },
                ],
                "sort": [
                    {"id": "request_count", "status": "request_count", "name": _lazy("请求数量"), "tips": _lazy("请求数量")},
                    {"id": "error_count", "status": "error_count", "name": _lazy("错误数量"), "tips": _lazy("错误数量")},
                    {"id": "avg_duration", "status": "avg_duration", "name": _lazy("响应耗时"), "tips": _lazy("响应耗时")},
                ],
            }

        result = []

        for endpoint in endpoints:
            endpoint_id = f"{endpoint['endpoint_name']}|{endpoint['service_name']}"
            if endpoint_id in endpoint_set:
                continue
            endpoint_set.add(endpoint_id)
            endpoint_metric = endpoints_metric.get(
                endpoint_id, {"request_count": 0, "error_count": 0, "avg_duration": 0}
            )
            status_count[self.get_status(endpoint_metric)["type"]] += 1

            request_percent = self.calc_percecnt(endpoint_metric.get("request_count", 0), request_all_count)
            error_percent = self.calc_percecnt(endpoint_metric.get("error_count", 0), error_all_count)
            avg_percent = self.calc_percecnt(endpoint_metric.get("avg_duration", 0), duration_all_count)

            result.append(
                {
                    "id": f"{validated_request_data['app_name']}"
                    f"|{endpoint['service_name']}|{endpoint['endpoint_name']}",
                    "name": endpoint["endpoint_name"],
                    "endpoint": endpoint["endpoint_name"],
                    "service_name": endpoint["service_name"],
                    "app_name": validated_request_data["app_name"],
                    "status": self.get_status(endpoint_metric),
                    "metric": {
                        "request_count": {
                            "value": endpoint_metric.get("request_count", 0),
                            "percent": request_percent,
                        },
                        "error_count": {
                            "value": endpoint_metric.get("error_count", 0),
                            "percent": error_percent,
                        },
                        "avg_duration": {
                            "value": endpoint_metric.get("avg_duration", 0),
                            "percent": avg_percent,
                        },
                    },
                }
            )
        result.sort(key=lambda x: self.STATUS_SORT.index(x["status"]["type"]))

        for item in result:
            value, unit = load_unit("ns").auto_convert(item["metric"]["avg_duration"]["value"], decimal=2)
            item["metric"]["avg_duration"]["value"] = f"{value}{unit}"

        return {
            "data": self.filter_keyword(result, validated_request_data.get("keyword")),
            "filter": [
                {"id": "success", "status": "success", "name": status_count["success"], "tips": _lazy("1小时内无异常")},
                {"id": "failed", "status": "failed", "name": status_count["failed"], "tips": _lazy("1小时内有异常")},
                {"id": "disabled", "status": "disabled", "name": status_count["disabled"], "tips": _lazy("1小时内无数据")},
            ],
            "sort": [
                {"id": "request_count", "status": "request_count", "name": _lazy("请求数量"), "tips": _lazy("请求数量")},
                {"id": "error_count", "status": "error_count", "name": _lazy("错误数量"), "tips": _lazy("错误数量")},
                {"id": "avg_duration", "status": "avg_duration", "name": _lazy("响应耗时"), "tips": _lazy("响应耗时")},
            ],
        }


class EndpointListResource(ServiceAndComponentCompatibleResource):
    need_overview = True
    need_dynamic_sort_column = True

    return_time_range = True
    timestamp_fields = ["start_time", "end_time"]

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        view_options = serializers.JSONField(label="页面设置", required=False)
        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")
        keyword = serializers.CharField(label="关键字", allow_blank=True)
        filter = serializers.CharField(label="条件", allow_blank=True, required=False)
        service_name = serializers.CharField(label="服务", allow_blank=True, default="")
        page = serializers.IntegerField(required=False, label="页码")
        page_size = serializers.IntegerField(required=False, label="每页条数")
        filter_dict = serializers.DictField(required=False, label="筛选条件", default={})
        filter_fields = serializers.DictField(required=False, label="匹配条件", default={})
        sort = serializers.CharField(required=False, label="排序条件", allow_blank=True)
        status = serializers.CharField(required=False, label="状态过滤", allow_blank=True)
        category = serializers.CharField(label="分类(服务视图下)", required=False)
        kind = serializers.CharField(label="类型(服务视图下)", required=False)
        predicate_value = serializers.CharField(label="分类具体值(服务视图下)", required=False)

    def get_sort_fields(self):
        return ["request_count", "error_rate", "error_count", "avg_duration"]

    def get_filter_fields(self):
        return ["service", "endpoint_name"]

    @staticmethod
    def overview_error_rate(data):
        request_count_sum = sum(
            i.get("request_count", {}).get("label", 0)
            if isinstance(i.get("request_count"), dict)
            else i.get("request_count", 0)
            for i in data
        )

        error_count = sum(
            i.get("error_count", {}).get("label", 0)
            if isinstance(i.get("error_count"), dict)
            else i.get("error_count", 0)
            for i in data
        )

        return round((error_count / request_count_sum) * 100, 2) if request_count_sum else None

    def get_columns(self, column_type=None):
        service_format = LinkTableFormat(
            id="service",
            name=_lazy("服务名称"),
            min_width=120,
            checked=True,
            target="blank",
            filterable=True,
            event_key=SceneEventKey.SWITCH_SCENES_TYPE,
            url_format="/?bizId={bk_biz_id}/#/apm/service/?filter-service_name={service}"
            + "&filter-app_name={app_name}&"
            "filter-category={service_category}&"
            "filter-kind={service_kind}&"
            "filter-predicate_value={service_predicate_value}",
        )
        if column_type:
            service_format = ServiceComponentAdaptLinkFormat(
                id="service",
                name=_lazy("服务名称"),
                min_width=120,
                checked=True,
                target="event",
                filterable=True,
                event_key=SceneEventKey.SWITCH_SCENES_TYPE,
                url_format="/service/?filter-service_name={service}" + "&filter-app_name={app_name}&"
                "filter-category={service_category}&"
                "filter-kind={service_kind}&"
                "filter-predicate_value={service_predicate_value}&"
                "dashboardId=service-default-overview&sceneId=apm_service&sceneType=overview",
            )
        columns = [
            OverviewDataTableFormat(
                id="endpoint_name",
                title=_lazy("接口概览"),
                name=_lazy("接口"),
                checked=True,
                disabled=True,
                width=248,
                min_width=120,
                max_width=300,
            ),
            StatusTableFormat(
                id="apdex",
                name=_lazy("状态"),
                checked=True,
                status_map_cls=Apdex,
                filterable=True,
                min_width=120,
            ),
            StringTableFormat(
                id="category_kind",
                name=_lazy("类型"),
                checked=True,
                filterable=True,
                min_width=120,
            ),
            StringLabelTableFormat(
                id="category",
                name=_lazy("分类"),
                checked=True,
                filterable=True,
                label_getter=CategoryEnum.get_label_by_key,
                icon_getter=lambda row: get_icon(row["category"]),
                min_width=120,
            ),
            service_format,
            StringTableFormat(
                id="kind",
                name=_lazy("调用类型"),
                checked=True,
                filterable=True,
                min_width=120,
            ),
            CustomProgressTableFormat(
                id="request_count",
                name=_lazy("调用次数"),
                overview_calculator=Calculator.sum(),
                color_getter=lambda _: "SUCCESS",
                max_if_overview=True,
                min_width=120,
                clear_if_not_sorted=True,
            ),
            CustomProgressTableFormat(
                id="error_count",
                name=_lazy("错误次数"),
                overview_calculator=Calculator.sum(),
                color_getter=lambda _: "FAILED",
                max_if_overview=True,
                min_width=120,
                clear_if_not_sorted=True,
            ),
            ProgressTableFormat(
                id="error_rate",
                name=_lazy("错误率"),
                overview_calculate_handler=EndpointListResource.overview_error_rate,
                color_getter=lambda _: "FAILED",
                min_width=120,
            ),
            NumberTableFormat(
                id="avg_duration",
                name=_lazy("平均响应时间"),
                checked=True,
                overview_calculator=Calculator.avg(),
                min_width=120,
                unit="ns",
                decimal=2,
            ),
            LinkListTableFormat(
                id="operation",
                name=_lazy("操作"),
                checked=True,
                disabled=True,
                links=[
                    LinkTableFormat(
                        id="trace",
                        name=_lazy("调用链"),
                        url_format='/?bizId={bk_biz_id}/#/trace/home/?app_name={app_name}'
                        + '&search_type=scope'
                        + '&start_tiem={start_time}&end_tiem={end_time}'
                        + '&conditionList={{"resource.service.name": {{'
                        '"selectedCondition": {{"label": "=","value": "equal"}},'
                        '"selectedConditionValue": ["{service_name}"]}},'
                        '"span_name": {{"selectedCondition": {{"label": "=","value": "equal"}},'
                        '"selectedConditionValue": ["{endpoint_name}"]}}}}',
                        target="blank",
                        event_key=SceneEventKey.SWITCH_SCENES_TYPE,
                    )
                ],
                min_width=120,
            ),
        ]

        # 临时分享处理返回链接数据
        request = get_request(peaceful=True)
        if request and getattr(request, "token", None):
            columns = [column for column in columns if column.id != "operation"]

        return columns

    @classmethod
    def _build_group_key(cls, endpoint):
        category = []
        for category_k in cls._get_category_keys():
            if category_k == endpoint["category_kind"]["key"]:
                category.append(str(endpoint["category_kind"]["value"]))
                continue
            category.append("")
        return "|".join(
            [
                endpoint["endpoint_name"],
                str(endpoint["kind"]),
                endpoint["service_name"],
            ]
            + category
        )

    @classmethod
    def _build_status_count_group_key(cls, endpoint, value_getter=lambda i: i):
        category = []
        for category_k in cls._get_category_keys():
            if category_k == endpoint["origin_category_kind"]["key"]:
                category.append(str(endpoint["origin_category_kind"]["value"]))
                continue
            category.append("")
        return "|".join(
            [
                value_getter(endpoint["endpoint_name"]),
                str(endpoint["origin_kind"]),
                value_getter(endpoint["service_name"]),
            ]
            + category
        )

    @classmethod
    def _get_category_keys(cls):
        return [
            SpanAttributes.DB_SYSTEM,
            SpanAttributes.MESSAGING_SYSTEM,
            SpanAttributes.RPC_SYSTEM,
            SpanAttributes.HTTP_METHOD,
            SpanAttributes.MESSAGING_DESTINATION,
        ]

    def perform_request(self, validate_data):
        bk_biz_id = validate_data["bk_biz_id"]
        app_name = validate_data["app_name"]
        service_name = validate_data["service_name"]

        if ServiceHandler.is_remote_service(bk_biz_id, app_name, service_name):
            # 如果为远程服务 -> 获取所有调用方的数据
            response = api.apm_api.query_topo_relation(bk_biz_id=bk_biz_id, app_name=app_name, to_topo_key=service_name)
            res = []
            endpoints_metrics = {}
            from_service_names = {i["from_topo_key"] for i in response}
            for service_name in from_service_names:
                r, m = self.list_endpoints(validate_data, service_name)
                res += r
                endpoints_metrics.update(m)

            # 根据调用方进行过滤接口
            query_params = {
                "bk_biz_id": bk_biz_id,
                "app_name": app_name,
                "topo_node_key": service_name,
            }
            if validate_data.get("filter"):
                query_params["category"] = validate_data["filter"]

            relations = api.apm_api.query_remote_service_relation(**query_params)
            driving_endpoints = [i["from_endpoint_name"] for i in relations]
            res = [r for r in res if r["endpoint_name"] in driving_endpoints]

            status_count = self.calc_status_count(res, endpoints_metrics)
            res = self.filter_status(validate_data, res)
            res = handle_filter_fields(res, validate_data.get("filter_fields"))
            data = self.get_pagination_data(res, validate_data, True)
            data["filter"] = self.get_filter(status_count)
            return data

        else:
            endpoints, metric = self.list_endpoints(validate_data, service_name)
            status_count = self.get_status_count(validate_data, endpoints, service_name, metric)
            endpoints = self.filter_status(validate_data, endpoints)
            endpoints = handle_filter_fields(endpoints, validate_data.get("filter_fields"))
            res = self.get_pagination_data(endpoints, validate_data, service_name)
            res["filter"] = self.get_filter(status_count)
            return res

    def get_status_count(self, params, endpoints, service_name, metric):
        # 获取过滤数量 需要根据keyword、filter_dict过滤
        _, column_format_map = self.get_columns_config(endpoints, service_name)
        data = self.handle_filter(params, endpoints, column_format_map)
        return self.calc_status_count(data, metric)

    def filter_status(self, data, endpoints):
        res = []
        if data.get("status", "all") == "all":
            return endpoints

        require_status = data.get("status")
        for item in endpoints:
            if item["status"]["type"] == require_status:
                res.append(item)

        return res

    def calc_status_count(self, data, endpoints_metric):
        status_count = {"success": 0, "failed": 0, "disabled": 0}

        for i in data:
            endpoint_metric = endpoints_metric.get(self._build_status_count_group_key(i), {})
            status_count[self.get_status(endpoint_metric)["type"]] += 1

        return status_count

    def get_filter(self, status_count):
        return [
            {"id": "success", "status": "success", "name": status_count["success"], "tips": _lazy("1小时内无异常")},
            {"id": "failed", "status": "failed", "name": status_count["failed"], "tips": _lazy("1小时内有异常")},
            {"id": "disabled", "status": "disabled", "name": status_count["disabled"], "tips": _lazy("1小时内无数据")},
        ]

    def get_status(self, metric):
        if not metric:
            return {"text": _lazy("无数据"), "type": "disabled"}

        if metric.get("error_count", 0):
            return {
                "text": _lazy("异常"),
                "type": "failed",
            }
        if metric.get("request_count", 0):
            return {
                "text": _lazy("正常"),
                "type": "success",
            }
        return {"text": _lazy("无数据"), "type": "disabled"}

    def list_endpoints(self, data, service_name):
        bk_biz_id = data["bk_biz_id"]
        app_name = data["app_name"]

        query_param = {
            "bk_biz_id": bk_biz_id,
            "app_name": app_name,
            "service_name": service_name,
        }
        if "bk_instance_id" in data.get("view_options", {}):
            query_param["bk_instance_id"] = data["view_options"]["bk_instance_id"]

        if data.get("filter"):
            query_param["category"] = data["filter"]

        if ComponentHandler.is_component(data):
            predicate_value = data["predicate_value"]
            query_param["category"] = data["category"]
            query_param["service_name"] = ComponentHandler.get_component_belong_service(service_name, predicate_value)
            query_param["category_kind_value"] = predicate_value

        endpoints = api.apm_api.query_endpoint(query_param)

        application = Application.objects.get(bk_biz_id=data["bk_biz_id"], app_name=data["app_name"])

        # 获取时间范围内endpoint的指标
        endpoints_metric = ENDPOINT_LIST(application, start_time=data["start_time"], end_time=data["end_time"])

        request_all_count = 0
        error_all_count = 0
        duration_all_count = 0
        for i in endpoints:
            metric = endpoints_metric.get(self._build_group_key(i), {})
            request_all_count += metric.get("request_count", 0)
            error_all_count += metric.get("error_count", 0)
            duration_all_count += metric.get("avg_duration", 0)

        for endpoint in endpoints:
            metric = endpoints_metric.get(self._build_group_key(endpoint), {})

            request_count = metric.get("request_count")
            if request_count:
                request_count_percent = round((request_count / request_all_count) * 100, 2) if request_all_count else 0
                endpoint["request_count"] = {"value": request_count_percent, "label": request_count}
            elif request_count == 0:
                endpoint["request_count"] = {"value": 0, "label": 0}

            error_count = metric.get("error_count")
            if error_count:
                error_count_percent = round((error_count / error_all_count) * 100, 2) if error_all_count else 0
                endpoint["error_count"] = {"value": error_count_percent, "label": error_count}
            else:
                if request_count:
                    endpoint["error_count"] = {"value": 0, "label": 0}

            avg_duration = metric.get("avg_duration", 0)
            if avg_duration:
                endpoint["avg_duration"] = avg_duration

            endpoint["origin_kind"] = endpoint["kind"]
            endpoint["kind"] = SpanKind.get_label_by_key(endpoint["kind"])
            endpoint["app_name"] = application.app_name
            endpoint["operation"] = {"trace": _lazy("调用链")}
            endpoint["origin_category_kind"] = endpoint["category_kind"]
            endpoint["category_kind"] = endpoint["category_kind"]["value"] or "--"
            endpoint["bk_biz_id"] = data["bk_biz_id"]
            endpoint["status"] = self.get_status(metric)
            endpoint["service"] = endpoint["service_name"]
            if metric.get("apdex"):
                endpoint["apdex"] = metric.get("apdex")
            if metric.get("error_rate"):
                endpoint["error_rate"] = metric.get("error_rate")

        return endpoints, endpoints_metric


class AlertQueryResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")
        strategy_id = serializers.IntegerField(label="策略ID", required=False)

    def format_alert_data(self, alert_level_result):
        # 所有时刻
        all_time_list = {}
        # 红色预警-时刻
        red_time_list = {}
        # 黄色预警-时刻
        yellow_time_list = {}
        # 存储各个时刻的颜色
        result_time = []
        for level in alert_level_result:
            series_dict = alert_level_result.get(level, {})
            series = series_dict.get("series", [])
            for data_series in series:
                name = data_series.get("name", "")
                data_list = data_series.get("data", [])
                # 如果是未恢复
                if name == AlertStatus.ABNORMAL:
                    for item_data in data_list:
                        num = item_data[1] if item_data[1] else 0
                        if num > 0:
                            if level == AlertLevel.ERROR:
                                red_time_list[item_data[0]] = num
                                # red_time_list.append(item_data[0])
                            else:
                                yellow_time_list[item_data[0]] = num
                                # yellow_time_list.append(item_data[0])
                # 用"提示"-"已恢复"的时刻列表，去获取所有的时刻列表
                elif level == AlertLevel.INFO and name == AlertStatus.RECOVERED:
                    for item_data in data_list:
                        all_time_list[item_data[0]] = item_data[1] if item_data[1] else 0
                        # all_time_list.append(item_data[0])

        for time, value in all_time_list.items():
            if time in red_time_list:
                # item = {"value": [time, 1], "status": AlertColor.RED}
                item = [[1, red_time_list[time]], time]
            elif time in yellow_time_list:
                # item = {"value": [time, 1], "status": AlertColor.YELLOW}
                item = [[2, yellow_time_list[time]], time]
            else:
                # item = {"value": [time, 1], "status": AlertColor.GREEN}
                item = [[3, 0], time]
            result_time.append(item)

        return result_time

    def get_alert_params(self, *params):
        application, bk_biz_id, start_time, end_time, level, strategy_id = params
        database, _ = application.metric_result_table_id.split(".")
        interval = (end_time - start_time) // APDEX_VIEW_ITEM_LEN
        para = {
            "bk_biz_ids": [bk_biz_id],
            "start_time": start_time,
            "end_time": end_time,
            "interval": interval,
            "query_string": f"metric: custom.{database}*",
            "conditions": [
                {"key": "severity", "value": [level]},
            ],
        }
        if strategy_id is not None:
            para["conditions"].append({"key": "strategy_id", "value": [strategy_id]})
        return para

    def get_alert_data(self, *params):
        application, bk_biz_id, start_time, end_time, strategy_id = params
        alert_level = [AlertLevel.ERROR, AlertLevel.WARN, AlertLevel.INFO]
        alert_level_result = {}
        for level in alert_level:
            para = self.get_alert_params(application, bk_biz_id, start_time, end_time, level, strategy_id)
            series = resource.fta_web.alert.alert_date_histogram(para)
            alert_level_result[level] = series
        return alert_level_result

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        app_name = validated_request_data["app_name"]
        start_time = validated_request_data["start_time"]
        end_time = validated_request_data["end_time"]
        strategy_id = validated_request_data.get("strategy_id", None)
        try:
            application = Application.objects.get(app_name=app_name, bk_biz_id=bk_biz_id)
        except Application.DoesNotExist:
            raise ValueError("Application does not exist")

        series = []
        if ApplicationHandler.have_data(application, start_time, end_time):
            format_alert_data = self.get_alert_data(application, bk_biz_id, start_time, end_time, strategy_id)
            time_list = self.format_alert_data(format_alert_data)
            series = [{"datapoints": time_list, "dimensions": {}, "target": "alert", "type": "bar", "unit": ""}]

        return {
            "metrics": [],
            "series": series,
        }


class ServiceInstancesResource(ServiceAndComponentCompatibleResource):
    need_dynamic_sort_column = True
    need_overview = True

    def get_sort_fields(self):
        return ["request_count", "error_rate"]

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        view_options = serializers.JSONField(label="页面设置", required=False)
        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")
        keyword = serializers.CharField(label="关键字", allow_blank=True)
        service_name = serializers.CharField(label="服务", allow_blank=True, default="")
        page = serializers.IntegerField(required=False, label="页码")
        page_size = serializers.IntegerField(required=False, label="每页条数")
        sort = serializers.CharField(required=False, label="排序条件", allow_blank=True)
        filter_dict = serializers.DictField(required=False, label="筛选条件", default={})
        filter_fields = serializers.DictField(required=False, label="匹配条件", default={})
        service_params = ServiceParamsSerializer(required=False, label="服务节点额外参数")

    def get_columns(self, column_type=None):
        return [
            OverviewDataTableFormat(
                id="bk_instance_id",
                title=_lazy("实例概览"),
                name=_lazy("实例"),
                checked=True,
                disabled=True,
                width=248,
                min_width=120,
                max_width=300,
            ),
            StatusTableFormat(
                id="apdex",
                name=_lazy("状态"),
                checked=True,
                status_map_cls=Apdex,
                filterable=True,
                min_width=120,
            ),
            NumberTableFormat(
                id="request_count",
                name=_lazy("调用次数"),
                checked=True,
                overview_calculator=Calculator.sum(),
                min_width=120,
            ),
            NumberTableFormat(
                id="error_rate",
                name=_lazy("错误率"),
                checked=True,
                unit="percent",
                decimal=2,
                overview_calculator=Calculator.avg(),
                min_width=120,
            ),
            NumberTableFormat(
                id="avg_duration",
                name=_lazy("平均响应时间"),
                checked=True,
                unit="ns",
                decimal=2,
                overview_calculator=Calculator.avg(),
                min_width=120,
            ),
        ]

    def get_metric_handlers(self):
        return [
            RequestCountInstance,
            ApdexInstance,
            ErrorRateInstance,
            AvgDurationInstance,
        ]

    def get_filter_fields(self):
        return ["instance_id"]

    def perform_request(self, validated_request_data):
        application = Application.objects.filter(
            bk_biz_id=validated_request_data["bk_biz_id"], app_name=validated_request_data["app_name"]
        ).first()

        query_dict = {
            "bk_biz_id": validated_request_data["bk_biz_id"],
            "app_name": validated_request_data["app_name"],
            "service_name": [validated_request_data["service_name"]],
        }

        if ComponentHandler.is_component(validated_request_data.get("service_params")):
            service_params = validated_request_data["service_params"]
            if "service_name" in query_dict:
                query_dict["service_name"] = [
                    ComponentHandler.get_component_belong_service(
                        query_dict["service_name"][0], service_params["predicate_value"]
                    )
                ]
            query_dict["filters"] = {
                "instance_topo_kind": TopoNodeKind.COMPONENT,
                "component_instance_category": service_params["category"],
                "component_instance_predicate_value": service_params["predicate_value"],
            }
            metric_data = ComponentHandler.get_service_component_instance_metrics(
                application,
                service_params["kind"],
                service_params["category"],
                validated_request_data["start_time"],
                validated_request_data["end_time"],
            )

        else:
            query_dict["filters"] = {
                "instance_topo_kind": TopoNodeKind.SERVICE,
            }

            metric_data = INSTANCE_LIST(
                application,
                start_time=validated_request_data["start_time"],
                end_time=validated_request_data["end_time"],
            )

        instances = api.apm_api.query_instance(query_dict).get("data", [])

        for instance in instances:
            instance["app_name"] = validated_request_data["app_name"]
            instance["bk_instance_id"] = instance.pop("instance_id")
            instance["service"] = validated_request_data["service_name"]

            instance.update(metric_data.get(instance["bk_instance_id"], {}))

        instances = handle_filter_fields(instances, validated_request_data.get("filter_fields"))
        return self.get_pagination_data(instances, validated_request_data)


class ServiceQueryExceptionResource(PageListResource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称")
        page = serializers.IntegerField(required=False, label="页码")
        page_size = serializers.IntegerField(required=False, label="每页条数")
        start_time = serializers.IntegerField(required=True, label="数据开始时间")
        end_time = serializers.IntegerField(required=True, label="数据开始时间")
        filter_dict = serializers.DictField(required=False, label="过滤条件", default={})
        filter_params = serializers.DictField(required=False, label="过滤参数", default={})
        sort = serializers.CharField(required=False, label="排序条件", allow_blank=True)
        service_params = ServiceParamsSerializer(required=False, label="服务节点额外参数")
        component_instance_id = serializers.CharField(required=False, label="组件实例id(组件页面下有效)")

    def get_columns(self, column_type=None):
        return [
            StringTableFormat(id="span_name", name="Span Name", checked=True),
            NumberTableFormat(id="count", name=_lazy("出现次数"), checked=True, sortable=True),
            LinkTableFormat(
                id="operate",
                name=_lazy("调用链"),
                url_format='/?bizId={bk_biz_id}/#/trace/home/?app_name={app_name}'
                + '&search_type=scope&filter_dict={{"service":["{service_name}"],"instance":["{bk_instance_id}"]}}'
                + '&query_string=status.code:+2+AND+span_name:+"{span_name}"+',
                target="blank",
                event_key=SceneEventKey.SWITCH_SCENES_TYPE,
            ),
        ]

    def build_filter_params(self, filter_dict):
        result = [{"key": "status.code", "op": "=", "value": ["2"]}]
        for key, value in filter_dict.items():
            if value == "undefined":
                continue
            result.append({"key": key, "op": "=", "value": value if isinstance(value, list) else [value]})
        return result

    def perform_request(self, data):
        filter_params = self.build_filter_params(data["filter_params"])
        ComponentHandler.build_component_filter_params(
            data["bk_biz_id"],
            data["app_name"],
            filter_params,
            data.get("service_params"),
            data.get("component_instance_id"),
        )

        query_dict = {
            "start_time": data["start_time"],
            "end_time": data["end_time"],
            "app_name": data["app_name"],
            "bk_biz_id": data["bk_biz_id"],
            "filter_params": filter_params,
        }

        exception_spans = api.apm_api.query_span(query_dict)
        mappings = {}

        service_name = data["filter_params"].get(OtlpKey.get_resource_key(ResourceAttributes.SERVICE_NAME))

        # 相同span, stats.message的作为一组
        for span in exception_spans:
            span_name = span[OtlpKey.SPAN_NAME]
            message = span.get(OtlpKey.STATUS, {}).get("message", "")
            if span["events"]:
                for event in span["events"]:
                    stacktrace = event.get(OtlpKey.ATTRIBUTES, {}).get(SpanAttributes.EXCEPTION_STACKTRACE, "")
                    key = (stacktrace, message, span_name)
                    if key in mappings:
                        mappings[key]["count"] += 1
                    else:
                        mappings[key] = {
                            "service_name": service_name,
                            "app_name": data["app_name"],
                            "bk_biz_id": data["bk_biz_id"],
                            "bk_instance_id": span[OtlpKey.RESOURCE].get(OtlpKey.BK_INSTANCE_ID),
                            "span_name": span_name,
                            "content": f"{message}\n{stacktrace}" if message or stacktrace else None,
                            "count": 1,
                            "operate": _lazy("调用链"),
                        }
            else:
                key = (None, message, span_name)
                if key in mappings:
                    mappings[key]["count"] += 1
                else:
                    mappings[key] = {
                        "service_name": service_name,
                        "app_name": data["app_name"],
                        "bk_biz_id": data["bk_biz_id"],
                        "bk_instance_id": span[OtlpKey.RESOURCE].get(OtlpKey.BK_INSTANCE_ID),
                        "span_name": span_name,
                        "content": message if message else None,
                        "count": 1,
                        "operate": _lazy("调用链"),
                    }

        return self.get_pagination_data(list(mappings.values()), data)


class ExceptionDetailListResource(Resource):
    UNKNOWN_EXCEPTION = "unknown"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")
        filter_dict = serializers.DictField(label="过滤条件", required=False, default={})
        filter = serializers.CharField(label="条件", allow_blank=True, required=False)
        keyword = serializers.CharField(label="关键字", allow_blank=True, required=False)
        is_stack = serializers.BooleanField(label="是否有堆栈", required=False)

    def build_filter_params(self, filter_dict):
        result = [{"key": "status.code", "op": "=", "value": ["2"]}]
        for key, value in filter_dict.items():
            if value == "undefined":
                continue
            result.append({"key": key, "op": "=", "value": value if isinstance(value, list) else [value]})

        return result

    def handle_exception_type(self, type_mapping, app_name, total_count, span_name, service_name, exception_type):
        key = f"{span_name}: {exception_type}"
        if key in type_mapping:
            type_mapping[key]["count"] += 1
            percent = f"{round((type_mapping[key]['count'] / total_count) * 100, 2)}%"
            type_mapping[key]["percent"] = percent
        else:
            type_mapping[key] = {
                "id": f"{app_name}|{exception_type}",
                "name": key,
                "app_name": app_name,
                "exception_type": exception_type,
                "count": 1,
                "percent": f"{round((1 / total_count) * 100, 2)}%",
                "service_name": service_name,
                "endpoint_name": span_name,
            }

    def perform_request(self, validated_request_data):
        query_dict = {
            "start_time": validated_request_data["start_time"],
            "end_time": validated_request_data["end_time"],
            "app_name": validated_request_data["app_name"],
            "bk_biz_id": validated_request_data["bk_biz_id"],
            "filter_params": self.build_filter_params(validated_request_data["filter_dict"]),
        }
        if validated_request_data.get("filter"):
            query_dict["category"] = validated_request_data["filter"]

        exception_spans = api.apm_api.query_span(query_dict)
        trace_mapping = group_by(exception_spans, operator.itemgetter("trace_id"))

        mappings = {}
        total_count = 0
        for trace_id, spans in trace_mapping.items():
            event_errors = [span for span in (e for e in spans) if span["events"]]
            if not event_errors:
                total_count += len(spans)
                mappings[trace_id] = spans
            else:
                total_count += len(event_errors)
                mappings[trace_id] = event_errors

        type_mapping = {}
        # 不同的trace_id可能有相同的异常类型
        for trace_id, spans in mappings.items():
            for span in spans:
                span_name = span.get(OtlpKey.SPAN_NAME)
                service_name = span.get(OtlpKey.RESOURCE, {}).get(ResourceAttributes.SERVICE_NAME)
                if span["events"]:
                    # 此span有异常事件

                    for event in span["events"]:
                        exception_type = event.get(OtlpKey.ATTRIBUTES, {}).get(
                            SpanAttributes.EXCEPTION_TYPE, self.UNKNOWN_EXCEPTION
                        )
                        self.handle_exception_type(
                            type_mapping,
                            validated_request_data["app_name"],
                            total_count,
                            span_name,
                            service_name,
                            exception_type,
                        )
                else:
                    if not validated_request_data.get("is_stack", False):
                        self.handle_exception_type(
                            type_mapping,
                            validated_request_data["app_name"],
                            total_count,
                            span_name,
                            service_name,
                            self.UNKNOWN_EXCEPTION,
                        )

        return {
            "data": self.filter_keyword(
                sorted(list(type_mapping.values()), key=lambda i: i["count"], reverse=True),
                validated_request_data.get("keyword"),
            ),
            "filter": [],
            "sort": [],
        }

    def filter_keyword(self, data, keyword):
        if not keyword:
            return data

        res = []
        for r in data:
            if (
                keyword.lower() in r["name"].lower()
                or keyword.lower() in r["service_name"].lower()
                or keyword.lower() in r["endpoint_name"]
                or keyword.lower() in r["exception_type"]
            ):
                res.append(r)

        return res


class ErrorListByTraceIdsResource(PageListResource):
    def get_columns(self, column_type=None):
        endpoint_format = LinkTableFormat(
            id="endpoint",
            name=_lazy("接口"),
            checked=True,
            url_format="/application/?filter-endpoint_name={endpoint}"
            + "&filter-service_name={service_name}"
            + "&filter-app_name={app_name}&dashboardId=endpoint&sceneType=detail&sceneId=apm_application",
            target="event",
            event_key=SceneEventKey.SWITCH_SCENES_TYPE,
        )
        error_format = StackLinkTableFormat(
            id="message",
            name=_lazy("错误"),
            checked=True,
            url_format="/application/?filter-endpoint_name={endpoint}"
            + "&filter-exception_type={exception_type}&filter-service_name={service_name}"
            + "&filter-app_name={app_name}&dashboardId=error&sceneType=detail&sceneId=apm_application",
            target="event",
            event_key=SceneEventKey.SWITCH_SCENES_TYPE,
        )
        return [
            error_format,
            endpoint_format,
            LinkTableFormat(
                id="service_name",
                name=_lazy("服务"),
                checked=True,
                url_format="/service/?filter-service_name={service_name}&filter-app_name={app_name}",
                sortable=True,
            ),
            StringTableFormat(id="first_time", name=_lazy("首次出现时间"), checked=True, sortable=True),
            StringTableFormat(id="last_time", name=_lazy("最新出现时间"), checked=True, sortable=True),
            NumberTableFormat(id="error_count", name=_lazy("错误次数"), checked=True, sortable=True),
            LinkListTableFormat(
                id="operations",
                name=_lazy("操作"),
                links=[
                    LinkTableFormat(
                        id="operate",
                        name=_lazy("调用链"),
                        url_format='/?bizId={bk_biz_id}/#/trace/home/?app_name={app_name}'
                        + '&search_type=scope'
                        + '&filter_dict={{"service":["{service_name}"],"endpoint":["{endpoint}"]}}'
                        + '&query_string=status.code:+2+',
                        target="blank",
                        event_key=SceneEventKey.SWITCH_SCENES_TYPE,
                    ),
                ],
            ),
        ]

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.CharField(label="业务ID")
        trace_ids = serializers.ListField(child=serializers.CharField(), label="traceId列表")
        view_options = serializers.JSONField(label="页面设置", required=False)
        start_time = serializers.CharField(label="开始时间")
        end_time = serializers.CharField(label="结束时间")
        keyword = serializers.CharField(label="关键字", allow_blank=True)
        filter = serializers.CharField(label="条件", allow_blank=True)
        service_name = serializers.CharField(label="服务", allow_blank=True, default="")
        page = serializers.IntegerField(required=False, label="页码")
        page_size = serializers.IntegerField(required=False, label="每页条数")
        sort = serializers.CharField(required=False, label="排序方法", allow_blank=True)
        filter_dict = serializers.DictField(required=False, label="筛选条件", default={})
        check_filter_dict = serializers.DictField(required=False, label="勾选条件", default={})

    def perform_request(self, validated_request_data):
        res = []
        app_relation = api.apm_api.query_app_by_trace(
            trace_ids=validated_request_data.pop("trace_ids"),
            bk_biz_id=validated_request_data["bk_biz_id"],
            start_time=validated_request_data["start_time"],
            end_time=validated_request_data["end_time"],
        )

        app_names = {(item["bk_biz_id"], item["app_name"]) for _, item in app_relation.items()}
        for bk_biz_id, app in app_names:
            request_data = dict(validated_request_data)
            request_data["bk_biz_id"] = bk_biz_id
            request_data["app_name"] = app
            res += ErrorListResource().get_data(request_data)

        paginated_data = self.get_pagination_data(res, validated_request_data)
        paginated_data["filter"] = CategoryEnum.get_filter_fields()
        paginated_data["check_filter"] = []

        return paginated_data


class HostInstanceDetailListResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        service_name = serializers.CharField(label="服务名称")
        keyword = serializers.CharField(label="关键字", allow_blank=True, required=False)

    def perform_request(self, data):
        keyword = data.pop("keyword", None)

        host_instances = HostHandler.list_application_hosts(**data)

        host_instance = [
            {"id": index, "name": f"{i['bk_host_innerip']}({i['bk_cloud_id']})", **i}
            for index, i in enumerate(host_instances, 1)
        ]
        return {"data": self.filter_keyword(host_instance, keyword), "filter": [], "sort": []}

    def filter_keyword(self, data, keyword):
        if not keyword:
            return data

        res = []
        for item in data:
            if keyword in item["bk_host_innerip"]:
                res.append(item)

        return res
