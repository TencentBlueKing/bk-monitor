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
import functools
import json
import logging
import operator
from collections import defaultdict
from json import JSONDecodeError

from django.core.cache import cache
from django.utils.translation import gettext_lazy as _lazy
from django.utils.translation import ugettext as _
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes
from rest_framework import serializers

from apm_web.constants import (
    COLLECT_SERVICE_CONFIG_KEY,
    AlertLevel,
    AlertStatus,
    Apdex,
    ApmCacheKey,
    CategoryEnum,
    DataStatus,
    SceneEventKey,
    ServiceStatus,
    TopoNodeKind,
    component_filter_mapping,
    component_where_mapping,
)
from apm_web.db.db_utils import get_service_from_params
from apm_web.handlers.application_handler import ApplicationHandler
from apm_web.handlers.component_handler import ComponentHandler
from apm_web.handlers.host_handler import HostHandler
from apm_web.handlers.service_handler import ServiceHandler
from apm_web.icon import get_icon
from apm_web.metric.constants import (
    ErrorMetricCategory,
    SeriesAliasType,
    StatisticsMetric,
)
from apm_web.metric.handler.statistics import ServiceMetricStatistics
from apm_web.metric.handler.top_n import get_top_n_query_type, load_top_n_handler
from apm_web.metric_handler import (
    ApdexInstance,
    ApdexRange,
    AvgDurationInstance,
    DurationBucket,
    ErrorRateInstance,
    RequestCountInstance,
)
from apm_web.metrics import ENDPOINT_DETAIL_LIST, ENDPOINT_LIST, INSTANCE_LIST
from apm_web.models import ApmMetaConfig, Application
from apm_web.resources import (
    AsyncColumnsListResource,
    ServiceAndComponentCompatibleResource,
)
from apm_web.serializers import AsyncSerializer, ComponentInstanceIdDynamicField
from apm_web.topo.handle.relation.relation_metric import RelationMetricHandler
from apm_web.utils import (
    Calculator,
    fill_series,
    get_bar_interval_number,
    handle_filter_fields,
)
from bkmonitor.share.api_auth_resource import ApiAuthResource
from bkmonitor.utils import group_by
from bkmonitor.utils.request import get_request
from bkmonitor.utils.thread_backend import ThreadPool
from bkmonitor.utils.time_tools import get_datetime_range
from constants.apm import ApmMetrics, OtlpKey, SpanKind, TelemetryDataType
from core.drf_resource import Resource, api, resource
from core.unit import load_unit
from monitor_web.scene_view.resources.base import PageListResource
from monitor_web.scene_view.table_format import (
    CollectTableFormat,
    CustomProgressTableFormat,
    DataPointsTableFormat,
    DataStatusTableFormat,
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
    不同分类的组件 查询unify-query参数会有所变化
    支持以下类型：
    1. 普通服务：不处理
    2. 组件服务：增加 predicate_value 等查询参数
    3. 自定义服务：增加 peer_service 等查询参数
    参数解释:
    alias_prefix / alias_suffix: 用于控制主被调需要调转的时候 例如进入了 xxx-mysql 时页面显示的是被调但是实际查询走的是主调查询
    fill_bar: 补充柱子，让页面上所有指标图标的柱子数量一致，能够让页面实现多图表联动
    extra_filter_dict: 额外的查询条件，有时候只知道 service_name 并不能获取所有的查询条件。
                       例如在接口页面，接口区分了类型(如 celery等)但是此时 node 并没有这个信息所有需要别的地方传进来。
    """

    class RequestSerializer(serializers.Serializer):
        app_name = serializers.CharField(label="应用名称")
        service_name = serializers.CharField(label="服务名称", default=False)
        unify_query_param = serializers.DictField(label="unify-query参数")
        bk_biz_id = serializers.IntegerField(label="业务ID")
        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")
        component_instance_id = ComponentInstanceIdDynamicField(required=False, label="组件实例id(组件页面下有效)")
        unit = serializers.CharField(label="图表单位(多指标计算时手动返回)", default=False)
        fill_bar = serializers.BooleanField(label="是否需要补充柱子(用于特殊配置的场景 仅影响 interval)", required=False)
        alias_prefix = serializers.ChoiceField(
            label="动态主被调当前值",
            choices=SeriesAliasType.get_choices(),
            required=False,
        )
        alias_suffix = serializers.CharField(label="动态 alias 后缀", required=False)
        extra_filter_dict = serializers.DictField(label="额外查询条件", required=False)

    def perform_request(self, validate_data):
        unify_query_params = {
            **validate_data["unify_query_param"],
            "start_time": validate_data["start_time"],
            "end_time": validate_data["end_time"],
            "bk_biz_id": validate_data["bk_biz_id"],
        }

        require_fill_series = False
        if validate_data.get("fill_bar"):
            interval = get_bar_interval_number(
                validate_data["start_time"],
                validate_data["end_time"],
            )
            for config in unify_query_params["query_configs"]:
                config["interval"] = interval

            require_fill_series = True

        if validate_data.get("extra_filter_dict"):
            for config in unify_query_params["query_configs"]:
                config["filter_dict"].update(validate_data["extra_filter_dict"])

        if not validate_data.get("service_name"):
            return self.fill_unit_and_series(
                resource.grafana.graph_unify_query(unify_query_params),
                validate_data,
                require_fill_series,
            )

        node = ServiceHandler.get_node(
            validate_data["bk_biz_id"],
            validate_data["app_name"],
            validate_data["service_name"],
            raise_exception=False,
        )
        if not node:
            return self.fill_unit_and_series(
                resource.grafana.graph_unify_query(unify_query_params),
                validate_data,
                require_fill_series,
            )

        if ComponentHandler.is_component_by_node(node):
            # 替换service_name
            pure_service_name = ComponentHandler.get_component_belong_service(validate_data["service_name"])

            if node["extra_data"]["category"] not in component_where_mapping:
                raise ValueError(_lazy(f"组件指标值查询不支持{validate_data['category']}分类"))

            # 追加where条件
            for config in unify_query_params["query_configs"]:
                # 增加组件实例查询条件
                if validate_data.get("component_instance_id"):
                    contain_or_condition = any(i.get("condition", "and") == "or" for i in config["where"])
                    if contain_or_condition:
                        # 如果包含 or 条件 那么不能使用 where 构建查询了因为 where 不支持 (a OR b) AND c 的查询
                        filter_dict = ComponentHandler.get_component_instance_query_dict(
                            validate_data["bk_biz_id"],
                            validate_data["app_name"],
                            node["extra_data"]["kind"],
                            node["extra_data"]["category"],
                            validate_data["component_instance_id"],
                        )
                        config["filter_dict"].update(filter_dict)
                    else:
                        component_filter = ComponentHandler.get_component_instance_query_params(
                            validate_data["bk_biz_id"],
                            validate_data["app_name"],
                            node["extra_data"]["kind"],
                            node["extra_data"]["category"],
                            validate_data["component_instance_id"],
                            config["where"],
                            template=ComponentHandler.unify_query_operator,
                            key_generator=OtlpKey.get_metric_dimension_key,
                        )
                        config["where"] += component_filter

                else:
                    # 没有组件实例时 单独添加组件类型的条件
                    filter_dict = component_filter_mapping[node["extra_data"]["category"]]
                    config["filter_dict"].update(
                        json.loads(
                            json.dumps(filter_dict).replace("{predicate_value}", node["extra_data"]["predicate_value"])
                        )
                    )

            # 替换service名称
            unify_query_params = json.loads(
                json.dumps(unify_query_params).replace(validate_data["service_name"], pure_service_name)
            )
        elif ServiceHandler.is_remote_service_by_node(node):
            pure_service_name = ServiceHandler.get_remote_service_origin_name(validate_data["service_name"])
            for config in unify_query_params["query_configs"]:
                config["filter_dict"]["peer_service"] = pure_service_name
                config["filter_dict"].pop("service_name", None)
            # 替换service名称
            unify_query_params = json.loads(
                json.dumps(unify_query_params).replace(validate_data["service_name"], pure_service_name)
            )

        return self.fill_unit_and_series(
            resource.grafana.graph_unify_query(unify_query_params),
            validate_data,
            require_fill_series,
            node=node,
        )

    @classmethod
    def fill_unit_and_series(cls, response, validate_data, require_fill_series=False, node=None):
        """补充单位、时间点、展示名称"""
        unit = validate_data.get("unit")
        start_time = validate_data["start_time"]
        end_time = validate_data["end_time"]

        if require_fill_series:
            response = {
                "metrics": response.get("metrics"),
                "series": fill_series(response.get("series", []), start_time, end_time),
            }

        if validate_data.get("unit"):
            for i in response.get("series", []):
                i["unit"] = unit

        if validate_data.get("alias_prefix") and node:
            # 如果同时配置了 alias 判断类型和后缀 则进行更名
            prefix = validate_data["alias_prefix"]
            suffix = validate_data.get("alias_suffix", "")

            if ComponentHandler.is_component_by_node(node) or ServiceHandler.is_remote_service_by_node(node):
                prefix = SeriesAliasType.get_choice_label(SeriesAliasType.get_opposite(prefix).value)
                # 如果是组件类服务或者自定义服务 将图表的主调改为被调
            else:
                prefix = SeriesAliasType.get_choice_label(prefix)
            for i in response.get("series", []):
                i["target"] = prefix + _(f"{suffix}")

        return response


class ServiceListResource(PageListResource):
    """服务列表接口"""

    def get_columns(self, column_type=None):
        return [
            CollectTableFormat(
                id="collect",
                name="",
                checked=True,
                width=40,
                api="apm_metric.collectService",
                params_get=lambda item: {
                    "service_name": item["service_name"],
                    "app_name": item["app_name"],
                },
                filterable=False,
                disabled=True,
            ),
            SyncTimeLinkTableFormat(
                id="service_name",
                width=200,
                name=_lazy("服务名称"),
                checked=True,
                url_format="/service/?filter-service_name={service_name}&filter-app_name={app_name}",
                icon_get=lambda row: get_icon(row["category"]),
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
            DataPointsTableFormat(
                id="request_count",
                name=_lazy("调用次数"),
                checked=True,
                asyncable=True,
                min_width=160,
            ),
            DataPointsTableFormat(
                id="error_rate",
                name=_lazy("错误率"),
                checked=True,
                asyncable=True,
                unit="percentunit",
                min_width=160,
            ),
            DataPointsTableFormat(
                id="avg_duration",
                name=_lazy("平均响应耗时"),
                checked=True,
                unit="ns",
                asyncable=True,
                min_width=160,
            ),
            NumberTableFormat(
                id="p50",
                name=_lazy("P50"),
                checked=True,
                unit="ns",
                decimal=2,
                asyncable=True,
                width=80,
            ),
            NumberTableFormat(
                id="p90",
                name=_lazy("P90"),
                checked=True,
                unit="ns",
                decimal=2,
                asyncable=True,
                width=80,
            ),
            # 四个数据状态 ↓
            DataStatusTableFormat(
                id="metric_data_status",
                name=_lazy("指标"),
                width=55,
                checked=True,
                filterable=False,
                props={
                    "align": "center",
                },
            ),
            DataStatusTableFormat(
                id="log_data_status",
                name=_lazy("日志"),
                width=55,
                checked=True,
                filterable=False,
                props={
                    "align": "center",
                },
            ),
            DataStatusTableFormat(
                id="trace_data_status",
                name=_lazy("调用链"),
                width=70,
                checked=True,
                filterable=False,
                props={
                    "align": "center",
                },
            ),
            DataStatusTableFormat(
                id="profiling_data_status",
                name=_lazy("性能分析"),
                width=80,
                checked=True,
                filterable=False,
                props={
                    "align": "center",
                },
            ),
            NumberTableFormat(
                id="strategy_count",
                name=_lazy("策略数"),
                checked=True,
                decimal=0,
                asyncable=True,
                display_handler=lambda d: d.get("view_mode") == self.RequestSerializer.VIEW_MODE_SERVICES,
            ),
            StatusTableFormat(
                id="alert_status",
                name=_lazy("告警状态"),
                checked=True,
                status_map_cls=ServiceStatus,
                asyncable=True,
                display_handler=lambda d: d.get("view_mode") == self.RequestSerializer.VIEW_MODE_SERVICES,
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
                width=80,
                link_handler=lambda i: i.get("kind") in [TopoNodeKind.SERVICE, TopoNodeKind.REMOTE_SERVICE],
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

        class FieldConditionSerializer(serializers.Serializer):
            key = serializers.CharField()
            value = serializers.ListField(child=serializers.CharField(), min_length=1)

        bk_biz_id = serializers.IntegerField(label="业务id")
        app_name = serializers.CharField(label="应用名称")
        keyword = serializers.CharField(required=False, label="查询关键词", allow_blank=True)
        start_time = serializers.IntegerField(required=True, label="数据开始时间")
        end_time = serializers.IntegerField(required=True, label="数据结束时间")
        page = serializers.IntegerField(required=False, label="页码")
        page_size = serializers.IntegerField(required=False, label="每页条数")
        sort = serializers.CharField(required=False, label="排序方式", allow_blank=True)
        filter = serializers.CharField(required=False, label="分类过滤条件", default="all", allow_blank=True)
        filter_dict = serializers.DictField(required=False, label="筛选条件", default={})
        field_conditions = serializers.ListField(
            required=False, default=[], label="or 条件列表", child=FieldConditionSerializer()
        )
        view_mode = serializers.ChoiceField(
            required=False,
            label="展示模式",
            choices=VIEW_MODE_CHOICES,
            default=VIEW_MODE_SERVICES,
        )

        def validate(self, attrs):
            res = super(ServiceListResource.RequestSerializer, self).validate(attrs)
            if not res.get("filter"):
                # 兼容服务 tab 页面前端无法传递 all 的问题
                res["filter"] = "all"
            return res

    def get_filter_fields(self):
        return ["service_name", "language", "type"]

    def get_sort_fields(self):
        return ["-collect"]

    class FieldStatistics:
        """根据字段统计"""

        key = None
        all_fields = None
        ignore_ids = {}

        @classmethod
        def list_filter_fields(cls, services):
            count_mapping = defaultdict(int)
            for item in services:
                if item.get(cls.key):
                    count_mapping[item[cls.key]] += 1
            res = []
            if cls.all_fields:
                for f in cls.all_fields:
                    if f["id"] in cls.ignore_ids:
                        continue

                    res.append(
                        {
                            "id": f["id"],
                            "name": f["name"],
                            "count": count_mapping[f["id"]],
                        }
                    )
            else:
                for k, v in count_mapping.items():
                    res.append(
                        {
                            "id": k,
                            "name": k,
                            "count": v,
                        }
                    )
            return res

        @classmethod
        def filter_by_fields(cls, values, services):
            res = []
            for i in services:
                if i.get(cls.key) in values:
                    res.append(i)
            return res

    class StatisticsCategory(FieldStatistics):
        key = "category"
        name = _("分类")
        all_fields = CategoryEnum.get_filter_fields()
        ignore_ids = ["all"]

    class StatisticsLanguage(FieldStatistics):
        key = "language"
        name = _("语言")

    class StatisticsApplyModule:
        key = "apply_module"
        name = _("数据上报")

        @classmethod
        def list_filter_fields(cls, services):
            count_mapping = defaultdict(int)
            # 只要功能开启了 就计数
            valid_data_status = [DataStatus.NORMAL, DataStatus.NO_DATA]
            for item in services:
                if item.get("metric_data_status") in valid_data_status:
                    count_mapping["metric"] += 1
                if item.get("log_data_status") in valid_data_status:
                    count_mapping["log"] += 1
                if item.get("trace_data_status") in valid_data_status:
                    count_mapping["trace"] += 1
                if item.get("profiling_data_status") in valid_data_status:
                    count_mapping["profiling"] += 1
            res = []
            for f in TelemetryDataType.get_filter_fields():
                res.append(
                    {
                        "id": f["id"],
                        "name": f["name"],
                        "count": count_mapping[f["id"]],
                    }
                )
            return res

        @classmethod
        def filter_by_fields(cls, values, services):
            res = []
            valid_data_status = [DataStatus.NORMAL, DataStatus.NO_DATA]
            for i in services:
                for j in values:
                    if j == "metric" and i.get("metric_data_status") in valid_data_status:
                        res.append(i)
                    elif j == "log" and i.get("log_data_status") in valid_data_status:
                        res.append(i)
                    elif j == "trace" and i.get("trace_data_status") in valid_data_status:
                        res.append(i)
                    elif j == "profiling" and i.get("profiling_data_status") in valid_data_status:
                        res.append(i)
            return res

    class StatisticsHaveData:
        key = "have_data"
        name = _("数据状态")

        @classmethod
        def list_filter_fields(cls, services):
            # 区分有数据 / 无数据
            module_fields = ["metric", "log", "trace", "profiling"]
            return [
                {
                    "id": "true",
                    "name": _("有数据"),
                    "count": len(
                        [
                            i
                            for i in services
                            if any(i.get(f"{j}_data_status") == DataStatus.NORMAL for j in module_fields)
                        ]
                    ),
                },
                {
                    "id": "false",
                    "name": _("无数据"),
                    "count": len(
                        [
                            i
                            for i in services
                            if all(i.get(f"{j}_data_status") != DataStatus.NORMAL for j in module_fields)
                        ]
                    ),
                },
            ]

        @classmethod
        def filter_by_fields(cls, values, services):
            module_fields = ["metric", "log", "trace", "profiling"]
            res = []
            for i in services:
                ds = any(i.get(f"{j}_data_status") == DataStatus.NORMAL for j in module_fields)
                # 因为前端传过来是字符串 这里进行一次转换
                ds = "true" if ds else "false"
                if ds in values:
                    res.append(i)

            return res

    class Labels:
        key = "labels"
        name = _("自定义标签")

        @classmethod
        def list_filter_fields(cls, services):
            count_mapping = defaultdict(int)
            for i in services:
                for j in i.get("labels", []):
                    count_mapping[j] += 1
            res = []
            for label, c in count_mapping.items():
                res.append({"id": label, "name": label, "count": c})
            return res

        @classmethod
        def filter_by_fields(cls, values, services):
            res = []
            for i in services:
                for v in values:
                    if v in i.get("labels", []):
                        res.append(i)

            return res

    def _get_filter_fields_by_services(self, services):
        """根据服务数据获取筛选项目"""
        fields = [
            self.StatisticsCategory,
            self.StatisticsLanguage,
            self.StatisticsApplyModule,
            self.StatisticsHaveData,
            self.Labels,
        ]
        res = []
        for f in fields:
            res.append({"id": f.key, "name": f.name, "data": f.list_filter_fields(services)})
        return res

    def _filter_by_fields(self, services, field_conditions):
        """根据字段过滤进行过滤服务"""
        key_mapping = {
            i.key: i
            for i in [
                self.StatisticsCategory,
                self.StatisticsLanguage,
                self.StatisticsApplyModule,
                self.StatisticsHaveData,
                self.Labels,
            ]
        }
        res = []
        for condition in field_conditions:
            instance = key_mapping.get(condition["key"])
            if instance:
                res.extend(instance.filter_by_fields(condition["value"], services))

        return list({i["service_name"]: i for i in res}.values())

    def perform_request(self, validate_data):
        bk_biz_id = validate_data["bk_biz_id"]
        app_name = validate_data["app_name"]
        application = Application.objects.get(bk_biz_id=bk_biz_id, app_name=app_name)

        # 获取服务列表
        services = ServiceHandler.list_services(application)
        # 获取服务收藏列表
        collects = CollectServiceResource.get_collect_config(application).config_value

        res = []
        # 先获取缓存数据
        cache_key = ApmCacheKey.APP_SERVICE_STATUS_KEY.format(application_id=application.application_id)
        data_status_mapping = cache.get(cache_key)
        if data_status_mapping:
            try:
                data_status_mapping = json.loads(data_status_mapping)
            except JSONDecodeError:
                pass
        if not data_status_mapping:
            data_status_mapping = ServiceHandler.get_service_data_status_mapping(
                application,
                validate_data["start_time"],
                validate_data["end_time"],
                services,
            )
            cache.set(cache_key, json.dumps(data_status_mapping))

        labels_mapping = group_by(
            ApmMetaConfig.list_service_config_values(bk_biz_id, app_name, [i["topo_key"] for i in services], "labels"),
            operator.attrgetter("level_key"),
        )
        for service in services:
            # 分类过滤
            if validate_data["filter"] != "all" and validate_data["filter"] != service["extra_data"]["category"]:
                continue
            name = service["topo_key"]
            labels = []
            if ApmMetaConfig.get_service_level_key(bk_biz_id, app_name, name) in labels_mapping:
                labels = json.loads(
                    labels_mapping[ApmMetaConfig.get_service_level_key(bk_biz_id, app_name, name)][0].config_value,
                )
            res.append(
                {
                    "app_name": application.app_name,
                    "collect": name in collects,
                    "service_name": name,
                    "type": CategoryEnum.get_label_by_key(service["extra_data"]["category"]),
                    "language": service["extra_data"]["service_language"] or _("其他语言"),
                    "metric_data_status": data_status_mapping[name].get(
                        TelemetryDataType.METRIC.value, DataStatus.DISABLED
                    ),
                    "log_data_status": data_status_mapping[name].get(TelemetryDataType.LOG.value, DataStatus.DISABLED),
                    "trace_data_status": data_status_mapping[name].get(
                        TelemetryDataType.TRACE.value, DataStatus.DISABLED
                    ),
                    "profiling_data_status": data_status_mapping[name].get(
                        TelemetryDataType.PROFILING.value, DataStatus.DISABLED
                    ),
                    "operation": {
                        "config": _lazy("配置"),
                    },
                    # category 附加数据 不显示
                    "category": service["extra_data"]["category"],
                    # kind 附加数据 不显示
                    "kind": service["extra_data"]["kind"],
                    "labels": labels,
                }
            )

        filter_fields = []
        # 获取顶部过滤项 (服务 tab 页)
        if validate_data["view_mode"] == self.RequestSerializer.VIEW_MODE_SERVICES:
            filter_fields = CategoryEnum.get_filter_fields()
        elif validate_data["view_mode"] == self.RequestSerializer.VIEW_MODE_HOME:
            filter_fields = self._get_filter_fields_by_services(res)

        if validate_data["field_conditions"]:
            res = self._filter_by_fields(res, validate_data["field_conditions"])

        paginated_data = self.get_pagination_data(res, validate_data)
        paginated_data["filter"] = filter_fields
        return paginated_data


class ServiceListAsyncResource(AsyncColumnsListResource):
    """
    服务列表异步接口
    """

    METRIC_MAP = {
        "avg_duration": {"metric": AvgDurationInstance, "type": "range"},
        "request_count": {"metric": RequestCountInstance, "type": "range"},
        "error_rate": {"metric": ErrorRateInstance, "ignore_keys": ["status_code"], "type": "range"},
        "p50": {
            "metric": functools.partial(
                DurationBucket,
                functions=[{"id": "histogram_quantile", "params": [{"id": "scalar", "value": "0.5"}]}],
            ),
            "ignore_keys": ["le"],
            "type": "instant",
        },
        "p90": {
            "metric": functools.partial(
                DurationBucket,
                functions=[{"id": "histogram_quantile", "params": [{"id": "scalar", "value": "0.9"}]}],
            ),
            "ignore_keys": ["le"],
            "type": "instant",
        },
        # strategy_count 特殊处理
        "strategy_count": {},
        # alert_status 特殊处理
        "alert_status": {},
    }

    SyncResource = ServiceListResource

    class RequestSerializer(AsyncSerializer):
        app_name = serializers.CharField(label="应用名称")
        service_names = serializers.ListSerializer(child=serializers.CharField(), default=[], label="服务列表")
        start_time = serializers.IntegerField(required=True, label="数据开始时间")
        end_time = serializers.IntegerField(required=True, label="数据结束时间")

    @classmethod
    def _get_column_metric_mapping(cls, column_metric, metric_params):
        """
        获取服务异步列数据映射 (指标)
        """

        if column_metric.get("type") == "instant":
            return ServiceHandler.get_service_metric_instant_mapping(
                column_metric["metric"],
                **metric_params,
                ignore_keys=column_metric.get("ignore_keys"),
            )

        return ServiceHandler.get_service_metric_range_mapping(
            column_metric["metric"],
            **metric_params,
            ignore_keys=column_metric.get("ignore_keys"),
        )

    @classmethod
    def _get_condition_service_names(cls, strategy: dict):
        """获取策略配置的条件，检查是否有配置 service_name=xxx"""
        service_names = []
        for item in strategy.get("items", []):
            for query_config in item.get("query_configs", []):
                for condition in query_config.get("agg_condition", []):
                    if condition.get("key") == "service_name" and condition.get("value"):
                        service_names.extend(condition["value"])
        return service_names

    @classmethod
    def _get_service_strategy_mapping(cls, application, start_time, end_time):
        """获取服务的策略和告警信息"""
        query_params = {
            "bk_biz_id": application.bk_biz_id,
            "conditions": [
                {
                    "key": "metric_id",
                    "value": [f"custom.{application.metric_result_table_id}.{m}" for m, _, _ in ApmMetrics.all()],
                }
            ],
            "page": 0,
            "page_size": 1000,
        }
        strategies = resource.strategies.get_strategy_list_v2(**query_params).get("strategy_config_list", [])
        # 获取指标的告警事件
        query_params = {
            "bk_biz_ids": [application.bk_biz_id],
            "query_string": f"metric: custom.{application.metric_result_table_id}.*",
            "start_time": start_time,
            "end_time": end_time,
            "page_size": 1000,
        }
        alert_infos = resource.fta_web.alert.search_alert(**query_params).get("alerts", [])

        strategy_events_mapping = {}
        service_alert_level_count_mapping = defaultdict(
            lambda: {
                AlertLevel.ERROR: 0,
                AlertLevel.WARN: 0,
                AlertLevel.INFO: 0,
            }
        )
        for strategy in strategies:
            events = [i for i in alert_infos if i["strategy_id"] == strategy["id"]]
            strategy_events_mapping[strategy["id"]] = {
                "info": strategy,
                "events": events,
            }

        service_strategy_count_mapping = defaultdict(int)
        for items in strategy_events_mapping.values():
            # Step1: 检查策略配置中是否包含服务的值 记录为服务的策略数
            service_names = cls._get_condition_service_names(items["info"])
            for name in service_names:
                service_strategy_count_mapping[name] += 1

            # Step2: 检查告警事件中是否包含服务的值 记录为服务的告警数
            for alert in items["events"]:
                alert_service_name = next(
                    (i.get("value") for i in alert.get("dimensions", []) if i.get("key") == "tags.service_name"), None
                )
                if not alert_service_name:
                    continue

                service_alert_level_count_mapping[alert_service_name][alert["severity"]] += 1

        service_alert_status_mapping = defaultdict(int)
        for svr, alert_status in service_alert_level_count_mapping.items():
            err_count = alert_status[AlertLevel.ERROR]
            warn_count = alert_status[AlertLevel.WARN]
            info_count = alert_status[AlertLevel.INFO]
            if err_count:
                service_alert_status_mapping[svr] = ServiceStatus.FATAL
            elif warn_count:
                service_alert_status_mapping[svr] = ServiceStatus.WARNING
            elif info_count:
                service_alert_status_mapping[svr] = ServiceStatus.REMIND
            else:
                service_alert_status_mapping[svr] = ServiceStatus.NORMAL

        return service_strategy_count_mapping, service_alert_status_mapping

    def perform_request(self, validated_data):
        column = validated_data["column"]
        res = []
        if column not in self.METRIC_MAP or not validated_data.get("service_names"):
            return res

        m = self.METRIC_MAP[column]
        app = Application.objects.get(bk_biz_id=validated_data["bk_biz_id"], app_name=validated_data["app_name"])
        metric_params = {
            "application": app,
            "start_time": validated_data["start_time"],
            "end_time": validated_data["end_time"],
        }

        if column in ["strategy_count", "alert_status"]:
            info_mapping = self._get_service_strategy_mapping(**metric_params)
        else:
            info_mapping = self._get_column_metric_mapping(m, metric_params)

        for service_name in validated_data["service_names"]:
            res.append(
                {
                    "service_name": service_name,
                    **self.get_async_column_item({column: info_mapping.get(service_name)}, column),
                }
            )

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
    """获取实例列表"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        service_name = serializers.CharField(label="服务名称", required=False, allow_blank=True)
        keyword = serializers.CharField(label="关键字", required=False, allow_blank=True)
        category = serializers.CharField(label="分类", required=False)

    def perform_request(self, validated_data):
        # 获取存储周期
        app = Application.objects.get(bk_biz_id=validated_data["bk_biz_id"], app_name=validated_data["app_name"])
        start_time, end_time = get_datetime_range(period="day", distance=app.es_retention, rounding=False)

        instances = RelationMetricHandler.list_instances(
            validated_data["bk_biz_id"],
            validated_data["app_name"],
            int(start_time.timestamp()),
            int(end_time.timestamp()),
            service_name=validated_data.get("service_name"),
        )
        return self.convert_to_response(validated_data["app_name"], validated_data.get("keyword"), instances)

    def convert_to_response(self, app_name, keyword, instances):
        data = []
        for instance in instances:
            data.append(
                {
                    "id": instance["apm_service_instance_name"],
                    "name": instance["apm_service_instance_name"],
                    "app_name": app_name,
                }
            )
        return self.filter_keyword(data, keyword)

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
            url_format="/?bizId={bk_biz_id}/#/apm/service/?filter-service_name={service}&filter-app_name={app_name}",
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
                        + '&start_time={start_time}&end_time={end_time}'
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
            "fields": [
                "resource.service.name",
                "span_name",
                "trace_id",
                "events.attributes.exception.type",
                "events.name",
                "time",
            ],
        }

        # 分类可以通过两种方式进行查询
        # 1. 通过filter_dict: {"category": "http"}
        # 2. 通过filter: "http"
        if data["filter"]:
            query_params["category"] = data["filter"]

        if data["service_name"]:
            node = ServiceHandler.get_node(bk_biz_id, app_name, data["service_name"])
            if ComponentHandler.is_component_by_node(node):
                ComponentHandler.build_component_filter_params(
                    data["bk_biz_id"],
                    data["app_name"],
                    data["service_name"],
                    query_params["filter_params"],
                )
            elif ServiceHandler.is_remote_service_by_node(node):
                query_params["filter_params"].append(
                    {
                        "key": OtlpKey.get_attributes_key(SpanAttributes.PEER_SERVICE),
                        "op": "=",
                        "value": [ServiceHandler.get_remote_service_origin_name(data["service_name"])],
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

        has_exception = False
        for error in errors:
            times.add(error["time"])
            exception_types |= {i.get("attributes", {}).get("exception.type") for i in error.get("events", [])}
            if not has_exception:
                has_exception = self.has_events(error.get("events", []))
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
            "error_count": len(errors),
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
        service_mappings = {i["topo_key"]: i for i in ServiceHandler.list_nodes(bk_biz_id, self.app_name)}

        error_map = {}

        for span in error_spans:
            service = span[OtlpKey.RESOURCE].get(ResourceAttributes.SERVICE_NAME)
            if not service:
                continue

            endpoint = span[OtlpKey.SPAN_NAME]

            if span.get("events"):
                for event in span["events"]:
                    exception_type = event.get(OtlpKey.ATTRIBUTES, {}).get(
                        SpanAttributes.EXCEPTION_TYPE, self.UNKNOWN_EXCEPTION_TYPE
                    )
                    key = (service, endpoint, exception_type)

                    self.handle_error_map(error_map, key, service, endpoint, span)
            else:
                exception_type = self.UNKNOWN_EXCEPTION_TYPE
                key = (service, endpoint, exception_type)
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


class TopNQueryResource(ApiAuthResource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")
        size = serializers.IntegerField(label="查询数量", default=5)
        query_type = serializers.ChoiceField(label="查询类型", choices=get_top_n_query_type())
        filter_dict = serializers.DictField(label="过滤条件", required=False)

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
            response = ApdexRange(
                application, start_time, end_time, interval=get_bar_interval_number(start_time, end_time)
            ).query_range()
            return {"metrics": [], "series": fill_series(response.get("series", []), start_time, end_time)}

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
                    {"id": "request_count", "status": "request_count", "name": _lazy("请求数"), "tips": _lazy("请求数")},
                    {"id": "error_count", "status": "error_count", "name": _lazy("错误数"), "tips": _lazy("错误数")},
                    {"id": "avg_duration", "status": "avg_duration", "name": _lazy("耗时"), "tips": _lazy("耗时")},
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
                {"id": "request_count", "status": "request_count", "name": _lazy("请求数"), "tips": _lazy("请求数")},
                {"id": "error_count", "status": "error_count", "name": _lazy("错误数"), "tips": _lazy("错误数")},
                {"id": "avg_duration", "status": "avg_duration", "name": _lazy("耗时"), "tips": _lazy("耗时")},
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
            url_format="/?bizId={bk_biz_id}/#/apm/service/?filter-service_name={service}&filter-app_name={app_name}",
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
                url_format="/service/?filter-service_name={service}&filter-app_name={app_name}&"
                "dashboardId=service-default-overview&sceneId=apm_service&sceneType=overview",
            )
        # columns 默认顺序: 接口、调用类型、调用次数、错误次数、错误率、平均响应时间、状态、类型、分类、服务、操作
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
            StatusTableFormat(
                id="apdex",
                name=_lazy("Apdex"),
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
                        + '&start_time={start_time}&end_time={end_time}'
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
    def _build_group_key(cls, endpoint, ignore_index=None, overwrite_service_name=None):
        category = []
        for category_k in CategoryEnum.list_span_keys():
            if category_k == endpoint["category_kind"]["key"]:
                category.append(str(endpoint["category_kind"]["value"]))
                continue
            category.append("")

        if ignore_index:
            category = category[:ignore_index]

        return "|".join(
            [
                endpoint["endpoint_name"],
                str(endpoint["kind"]),
                overwrite_service_name or endpoint["service_name"],
            ]
            + category
        )

    @classmethod
    def _build_status_count_group_key(cls, endpoint, value_getter=lambda i: i):
        category = []
        for category_k in CategoryEnum.list_span_keys():
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

    def perform_request(self, validate_data):
        service_name = validate_data["service_name"]

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
        }
        if "bk_instance_id" in data.get("view_options", {}):
            query_param["bk_instance_id"] = data["view_options"]["bk_instance_id"]

        if data.get("filter"):
            query_param["category"] = data["filter"]

        application = Application.objects.get(bk_biz_id=data["bk_biz_id"], app_name=data["app_name"])

        node_mapping = {}
        pool = ThreadPool()
        endpoint_metrics_param = {
            "application": application,
            "start_time": data["start_time"],
            "end_time": data["end_time"],
        }
        if service_name:
            node = ServiceHandler.get_node(bk_biz_id, app_name, service_name)
            if ComponentHandler.is_component_by_node(node):
                query_param["category"] = node["extra_data"]["category"]
                query_param["service_name"] = ComponentHandler.get_component_belong_service(service_name)
                query_param["category_kind_value"] = node["extra_data"]["predicate_value"]
                endpoints_metric_res = pool.apply_async(
                    ENDPOINT_LIST,
                    kwds={
                        **endpoint_metrics_param,
                        "where": ComponentHandler.get_component_metric_filter_params(
                            bk_biz_id,
                            app_name,
                            service_name,
                            query_param.get("bk_instance_id"),
                        )
                        + [
                            {
                                "key": "service_name",
                                "method": "eq",
                                "value": [ComponentHandler.get_component_belong_service(service_name)],
                            }
                        ],
                    },
                )

            elif ServiceHandler.is_remote_service_by_node(node):
                query_param["service_name"] = service_name
                endpoints_metric_res = pool.apply_async(
                    ENDPOINT_LIST,
                    kwds={
                        **endpoint_metrics_param,
                        "where": [
                            {
                                "key": "peer_service",
                                "method": "eq",
                                "value": [ServiceHandler.get_remote_service_origin_name(service_name)],
                            }
                        ],
                    },
                )

            else:
                query_param["service_name"] = service_name
                endpoints_metric_res = pool.apply_async(
                    ENDPOINT_LIST,
                    kwds={
                        **endpoint_metrics_param,
                        "where": [{"key": "service_name", "method": "eq", "value": [service_name]}],
                    },
                )

            node_mapping[service_name] = node
        else:
            # 如果无指定服务 需要在数据获取时获取服务信息
            endpoints_metric_res = pool.apply_async(ENDPOINT_LIST, kwds=endpoint_metrics_param)

        endpoints_res = pool.apply_async(api.apm_api.query_endpoint, kwds=query_param)
        pool.close()
        pool.join()

        endpoints = endpoints_res.get()

        # 获取时间范围内endpoint的指标
        endpoints_metric = endpoints_metric_res.get()
        request_all_count = 0
        error_all_count = 0
        duration_all_count = 0
        for i in endpoints:
            node_name = i["service_name"]
            if i.get("category_kind", {}).get("key") in [SpanAttributes.DB_SYSTEM, SpanAttributes.MESSAGING_SYSTEM]:
                node_name = ComponentHandler.generate_component_name(node_name, i["category_kind"]["value"])

            if node_name not in node_mapping:
                node_mapping[node_name] = ServiceHandler.get_node(
                    bk_biz_id,
                    app_name,
                    node_name,
                    raise_exception=False,
                )
            metric = self.get_endpoint_metric(endpoints_metric, node_mapping.get(node_name), i)

            request_all_count += metric.get("request_count", 0)
            error_all_count += metric.get("error_count", 0)
            duration_all_count += metric.get("avg_duration", 0)

        logger.info(f"[apm] endpoint_list request_all_count: {request_all_count}")

        for endpoint in endpoints:
            node_name = endpoint["service_name"]

            # 添加额外的查询条件 让右侧图标查询指标时查到正确的数据(通过图标配置中 metric_condition 指定)
            extra_filter_dict = {"kind": endpoint["kind"]}
            category_kind_key = endpoint.get("category_kind", {}).get("key")
            if category_kind_key in CategoryEnum.list_component_generate_keys():
                # 如果此接口是 db\messaging 类型 那么需要获取这个接口的服务名称(添加上后缀)
                node_name = ComponentHandler.generate_component_name(node_name, endpoint["category_kind"]["value"])
            if category_kind_key:
                extra_filter_dict.update(
                    {
                        OtlpKey.get_metric_dimension_key(category_kind_key): endpoint["category_kind"]["value"],
                    }
                )
            # 放入 value 字段中(兼容前端的格式)
            endpoint["extra_filter_dict"] = {"value": extra_filter_dict}

            metric = self.get_endpoint_metric(endpoints_metric, node_mapping.get(node_name), endpoint)

            request_count = metric.get("request_count")
            if request_count:
                request_count_percent = round((request_count / request_all_count) * 100, 2) if request_all_count else 0
                endpoint["request_count"] = {"value": request_count_percent, "label": request_count}
            else:
                endpoint["request_count"] = {"value": 0, "label": 0}

            error_count = metric.get("error_count")
            if error_count:
                error_count_percent = round((error_count / error_all_count) * 100, 2) if error_all_count else 0
                endpoint["error_count"] = {"value": error_count_percent, "label": error_count}
            else:
                endpoint["error_count"] = {"value": 0, "label": 0}

            avg_duration = metric.get("avg_duration")
            if avg_duration:
                endpoint["avg_duration"] = avg_duration
            else:
                endpoint["avg_duration"] = None

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
            else:
                endpoint["apdex"] = None
            if metric.get("error_rate") is not None:
                endpoint["error_rate"] = metric.get("error_rate")
            else:
                endpoint["error_rate"] = None

        return endpoints, endpoints_metric

    @classmethod
    def get_endpoint_metric(cls, metric, node, endpoint):
        if node and ServiceHandler.is_remote_service_by_node(node):
            # 自定义服务需要忽略掉调用方的服务名称来匹配指标
            remote_service_prefix = "|".join([endpoint["endpoint_name"], str(endpoint["kind"])])
            remote_service_suffix = "|".join([endpoint["category_kind"]["value"], ""])
            return next(
                (
                    v
                    for k, v in metric.items()
                    if k.startswith(remote_service_prefix) and k.endswith(remote_service_suffix)
                ),
                {},
            )
        elif node and ComponentHandler.is_component_by_node(node):
            if node["extra_data"]["category"] == CategoryEnum.DB:
                # 如果是 DB 类服务 则直接对比所有项目 服务名称需要改为原始名称
                component_prefix = cls._build_group_key(
                    endpoint,
                    overwrite_service_name=ComponentHandler.get_component_belong_service(node["topo_key"]),
                )
            elif node["extra_data"]["category"] == CategoryEnum.MESSAGING:
                # 如果是 Messaging 类服务 不对比最后一项
                # (messaging.destination, 因为消息队列场景中可能同时存在 message.system 和 message.destination
                # 又因为拓扑发现中没有针对多个category_kind场景做处理所以这里忽略最后一项)
                component_prefix = cls._build_group_key(
                    endpoint,
                    ignore_index=-1,
                    overwrite_service_name=ComponentHandler.get_component_belong_service(node["topo_key"]),
                )
            else:
                component_prefix = cls._build_group_key(endpoint)

            # 组件类服务因为 endpoints 表已经根据特征字段(predicate_key)进行区分 所以直接对比前三项即可
            return next((v for k, v in metric.items() if k.startswith(component_prefix)), {})

        else:
            return metric.get(cls._build_group_key(endpoint), {})


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
        # 蓝色提醒-时刻
        blue_time_list = {}
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
                            elif level == AlertLevel.WARN:
                                yellow_time_list[item_data[0]] = num
                            else:
                                blue_time_list[item_data[0]] = num
                                # yellow_time_list.append(item_data[0])
                # 用"提示"-"已恢复"的时刻列表，去获取所有的时刻列表
                elif level == AlertLevel.INFO and name == AlertStatus.RECOVERED:
                    for item_data in data_list:
                        all_time_list[item_data[0]] = item_data[1] if item_data[1] else 0
                        # all_time_list.append(item_data[0])

        for time, value in all_time_list.items():
            if time in red_time_list:
                item = [[1, red_time_list[time]], time]
            elif time in yellow_time_list:
                item = [[2, yellow_time_list[time]], time]
            elif time in blue_time_list:
                item = [[3, blue_time_list[time]], time]
            else:
                item = [[4, 0], time]
            result_time.append(item)

        return result_time

    def get_alert_params(self, *params):
        application, bk_biz_id, start_time, end_time, level, strategy_id = params
        para = {
            "bk_biz_ids": [bk_biz_id],
            "start_time": start_time,
            "end_time": end_time,
            "interval": get_bar_interval_number(start_time, end_time),
            "query_string": f"metric: custom.{application.metric_result_table_id}.*",
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
            response = resource.fta_web.alert.alert_date_histogram(para)
            series = []
            for i in response["series"]:
                # 查询告警这个接口会返回多一个点 这里将时间点控制为符合 bar_size 的个数
                series.append({**i, "data": i["data"]})
            alert_level_result[level] = {"series": series, "unit": ""}
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
            series = [{"datapoints": time_list[:-1], "dimensions": {}, "target": "alert", "type": "bar", "unit": ""}]

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

        node = ServiceHandler.get_node(
            validated_request_data["bk_biz_id"],
            validated_request_data["app_name"],
            validated_request_data["service_name"],
        )

        if ComponentHandler.is_component_by_node(node):
            metric_data = ComponentHandler.get_service_component_instance_metrics(
                application,
                ComponentHandler.get_component_belong_service(node["topo_key"]),
                node["extra_data"]["kind"],
                node["extra_data"]["category"],
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

        instances = RelationMetricHandler.list_instances(
            validated_request_data["bk_biz_id"],
            validated_request_data["app_name"],
            validated_request_data["start_time"],
            validated_request_data["end_time"],
            service_name=validated_request_data["service_name"],
        )

        for instance in instances:
            instance["app_name"] = validated_request_data["app_name"]
            instance["bk_instance_id"] = instance["apm_service_instance_name"]
            instance["service"] = validated_request_data["service_name"]

            instance.update(metric_data.get(instance["apm_service_instance_name"], {}))

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
        component_instance_id = serializers.CharField(required=False, label="组件实例id(组件页面下有效)")

    def get_columns(self, column_type=None):
        return [
            StringTableFormat(id="span_name", name="Span Name", checked=True),
            NumberTableFormat(id="count", name=_lazy("出现次数"), checked=True, sortable=True),
            LinkTableFormat(
                id="operate",
                name=_lazy("调用链"),
                url_format='/?bizId={bk_biz_id}/#/trace/home/?app_name={app_name}'
                + '&search_type=scope'
                + '&listType=trace'
                + '&start_time={start_time}&end_time={end_time}'
                + '&query=status.code:+2+'
                + '&conditionList={{"resource.service.name": '
                + '{{"selectedCondition": {{"label": "=","value": "equal"}},'
                + '"selectedConditionValue": ["{service_name}"]}},'
                + '"span_name": {{"selectedCondition": {{"label": "=","value": "equal"}},'
                + '"selectedConditionValue": ["{span_name}"]}},'
                + '"resource.bk.instance.id": {{"selectedCondition": {{"label": "=","value": "equal"}},'
                + '"selectedConditionValue": ["{bk_instance_id}"]}}}}',
                target="blank",
                event_key=SceneEventKey.SWITCH_SCENES_TYPE,
            ),
        ]

    def add_extra_params(self, params):
        return {"start_time": int(params["start_time"]) * 1000, "end_time": int(params["end_time"]) * 1000}

    def build_filter_params(self, filter_dict):
        result = [{"key": "status.code", "op": "=", "value": ["2"]}]
        for key, value in filter_dict.items():
            if value == "undefined":
                continue
            result.append({"key": key, "op": "=", "value": value if isinstance(value, list) else [value]})
        return result

    def perform_request(self, data):
        filter_params = self.build_filter_params(data["filter_params"])
        service_name = get_service_from_params(filter_params)
        if service_name:
            node = ServiceHandler.get_node(data["bk_biz_id"], data["app_name"], service_name)
            if ComponentHandler.is_component_by_node(node):
                ComponentHandler.build_component_filter_params(
                    data["bk_biz_id"],
                    data["app_name"],
                    service_name,
                    filter_params,
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


class MetricDetailStatisticsResource(Resource):
    """获取指标详情表格"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        app_name = serializers.CharField(label="应用名称")
        start_time = serializers.IntegerField(label="开始时间")
        end_time = serializers.IntegerField(label="结束时间")
        service_name = serializers.CharField(label="服务名称过滤", required=False)
        option_kind = serializers.CharField(label="选项主调/被调")
        data_type = serializers.ChoiceField(label="指标类型", choices=StatisticsMetric.get_choices())
        # 请求数无维度 错误数维度为 总数量+状态码 响应耗时维度为 平均耗时+MAX/MIN/P90/...
        dimension = serializers.CharField(label="下拉框维度", required=False, default="default")
        dimension_category = serializers.ChoiceField(
            label="下拉框维度分类",
            choices=ErrorMetricCategory.get_choices(),
            required=False,
        )

    def perform_request(self, validated_data):
        template = ServiceMetricStatistics.get_template(
            validated_data["data_type"],
            validated_data.get("option_kind"),
            validated_data.pop("dimension"),
            validated_data.get("service_name"),
            validated_data.get("dimension_category"),
        )
        s = ServiceMetricStatistics(**validated_data)
        return s.list(template)
