"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import time
import re
from collections import defaultdict
from typing import Any
from dataclasses import asdict

import arrow
from django.conf import settings
from django.core.paginator import Paginator
from django.db import models
from django.db.transaction import atomic
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkm_space.define import SpaceTypeEnum
from bkm_space.errors import NoRelatedResourceError
from bkmonitor.models import MetricListCache, QueryConfigModel, StrategyModel
from bkmonitor.utils.request import get_request_tenant_id, get_request_username
from bkmonitor.utils.user import get_admin_username
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api, resource
from core.drf_resource.base import Resource
from core.errors.api import BKAPIError
from core.errors.custom_report import (
    CustomValidationLabelError,
    CustomValidationNameError,
)
from monitor_web.constants import ETL_CONFIG
from monitor_web.custom_report.constants import UNGROUP_SCOPE_NAME, CustomTSMetricType, DEFAULT_FIELD_SCOPE
from monitor_web.custom_report.serializers.metric import (
    BaseCustomTSSerializer,
    CustomTSScopeRequestSerializer,
    CustomTSTableSerializer,
    BasicMetricRequestSerializer,
    BasicScopeSerializer,
    DimensionConfigRequestSerializer,
    MetricConfigRequestSerializer,
    ImportExportScopeSerializer,
    DimensionConfigResponseSerializer,
    MetricConfigResponseSerializer,
    CustomTSScopeResponseSerializer,
    BaseCustomTSTableSerializer,
)
from monitor_web.models.custom_report import (
    CustomTSTable,
)
from monitor_web.custom_report.handlers.metric.query import (
    ScopeQueryConverter,
    ScopeQueryResponseDTO,
    ScopeCURequestDTO,
    ScopeQueryMetricResponseDTO,
)
from monitor_web.custom_report.handlers.metric.service import (
    FieldsModifyService,
    ModifyMetric,
    ModifyDimension,
    ModifyDimensionConfig,
    ModifyMetricConfig,
)
from monitor_web.strategies.resources import GetMetricListV2Resource


logger = logging.getLogger(__name__)


def get_label_display_dict():
    label_display_dict = {}
    try:
        labels = resource.commons.get_label()
        for label in labels:
            for child in label["children"]:
                label_display_dict[child["id"]] = [label["name"], child["name"]]
    except Exception:
        pass
    return label_display_dict


def count_rt_bound_strategies(table_ids, data_source_label, data_type_label, bk_biz_id: int | None = None):
    """
    统计与结果表绑定的策略数量
    """
    if not table_ids:
        return {}

    # 先查询策略ID（当有业务过滤条件时）
    strategy_ids = None
    if bk_biz_id:
        strategy_ids = set(StrategyModel.objects.filter(bk_biz_id=bk_biz_id).values_list("pk", flat=True))

    # 查询自定义时间序列类型的查询配置
    query_configs_queryset = (
        QueryConfigModel.objects.annotate(result_table_id=models.F("config__result_table_id"))
        .filter(
            data_source_label=data_source_label,
            data_type_label=data_type_label,
        )
        .values("result_table_id", "strategy_id")
    )

    # 如果有业务过滤条件，进一步筛选query_configs
    if strategy_ids:
        query_configs_queryset = query_configs_queryset.filter(strategy_id__in=strategy_ids)

    query_configs = list(query_configs_queryset)

    # 构建结果表ID到策略ID的映射关系
    table_id_strategy_mapping = defaultdict(set)
    table_ids = set(table_ids)
    for query_config in query_configs:
        result_table_id = query_config["result_table_id"]
        if result_table_id in table_ids:
            table_id_strategy_mapping[query_config["result_table_id"]].add(query_config["strategy_id"])

    return {key: len(value) for key, value in table_id_strategy_mapping.items()}


class CustomTSScopeMixin:
    def get_query_scope_filters(self, params: dict) -> dict:
        """
        :param params: 请求参数
        :return: 过滤条件字典，将作为 **kwargs 传递给 query_time_series_scope
        """
        return {}

    def get_default_scope_name(self, params: dict):
        """
        :return: 默认分组名
        """
        return UNGROUP_SCOPE_NAME


class ProxyHostInfo(Resource):
    """
    Proxy主机信息
    """

    DEFAULT_PROXY_PORT = 10205

    def get_listen_port(self):
        return getattr(settings, "BK_MONITOR_PROXY_LISTEN_PORT", ProxyHostInfo.DEFAULT_PROXY_PORT)

    def perform_request(self, validated_request_data):
        port = self.get_listen_port()
        proxy_host_info = []
        bk_biz_id = validated_request_data["bk_biz_id"]
        proxy_hosts = []
        try:
            proxy_hosts = api.node_man.get_proxies_by_biz(bk_biz_id=bk_biz_id)
        except NoRelatedResourceError:
            logger.warning("bk_biz_id: %s not found related resource", bk_biz_id)
        except Exception as e:
            logger.warning("get proxies by bk_biz_id(%s) error, %s", bk_biz_id, e)

        for host in proxy_hosts:
            bk_cloud_id = int(host["bk_cloud_id"])
            # 默认云区域上报proxy，以settings配置为准！
            if bk_cloud_id == 0:
                continue
            ip = host.get("conn_ip") or host.get("inner_ip")
            proxy_host_info.append({"ip": ip, "bk_cloud_id": bk_cloud_id, "port": port})

        default_cloud_display = settings.CUSTOM_REPORT_DEFAULT_PROXY_DOMAIN or settings.CUSTOM_REPORT_DEFAULT_PROXY_IP
        for proxy_ip in default_cloud_display:
            proxy_host_info.append({"ip": proxy_ip, "bk_cloud_id": 0, "port": port})
        return proxy_host_info


class ValidateCustomTsGroupName(Resource):
    """
    校验自定义指标名称是否合法
    注: esb 开放接口，需要维持入参出参一致性
    """

    class RequestSerializer(serializers.Serializer):
        time_series_group_id = serializers.IntegerField(required=False)
        name = serializers.CharField(required=True)
        bk_biz_id = serializers.IntegerField(required=True)

    def perform_request(self, validated_request_data):
        try:
            custom_ts_groups = api.metadata.query_time_series_group(
                time_series_group_name=validated_request_data["name"], bk_biz_id=validated_request_data["bk_biz_id"]
            )
            if validated_request_data.get("time_series_group_id"):
                custom_ts_groups = [
                    g
                    for g in custom_ts_groups
                    if g["time_series_group_id"] != validated_request_data["time_series_group_id"]
                ]
            is_exist = bool(custom_ts_groups)
        except Exception:
            queryset = CustomTSTable.objects.filter(
                name=validated_request_data["name"], bk_biz_id=validated_request_data["bk_biz_id"]
            )
            if validated_request_data.get("time_series_group_id"):
                queryset = queryset.exclude(time_series_group_id=validated_request_data["time_series_group_id"])
            is_exist = queryset.exists()
        if is_exist:
            raise CustomValidationNameError(msg=_("自定义指标名称已存在"))
        return True


class ValidateCustomTsGroupLabel(Resource):
    """
    校验自定义指标数据名称是否合法
    1. 创建场景：调用metadata接口校验是否与存量ResultTable的data_label重复
    2. 编辑场景：除了time_series_group_id参数对应CustomTSTable的data_label外，是否与存量ResultTable的data_label重复
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        time_series_group_id = serializers.IntegerField(required=False)
        data_label = serializers.CharField(required=True)

    METRIC_DATA_LABEL_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_\.]*$")

    def perform_request(self, params: dict):
        if params["data_label"].strip() == "":
            raise CustomValidationLabelError(msg=_("自定义指标英文名不允许为空"))

        data_labels = params["data_label"].strip().split(",")
        for dl in data_labels:
            if not self.METRIC_DATA_LABEL_PATTERN.match(dl):
                raise CustomValidationLabelError(
                    msg=_("自定义指标英文名仅允许包含字母、数字、下划线、点号，且必须以字母开头")
                )
        params["data_label"] = ",".join(data_labels)
        return True


class CreateCustomTimeSeries(Resource):
    """
    创建自定义时序
    注: esb 开放接口，需要维持入参出参一致性
    """

    CUSTOM_TS_NAME = "custom_time_series"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label=_("业务 ID"), required=True)
        name = serializers.CharField(label=_("名称"), required=True, max_length=128)
        scenario = serializers.CharField(label=_("对象"), required=True)
        table_id = serializers.CharField(label=_("表名"), required=False, default="")
        metric_info_list = serializers.ListField(label=_("预定义表结构"), required=False, default=[])
        is_platform = serializers.BooleanField(label=_("平台级"), required=False, default=False)
        data_label = serializers.CharField(label=_("数据标签"), required=True)
        protocol = serializers.CharField(label=_("上报协议"), required=False, default="json")
        desc = serializers.CharField(label=_("说明"), required=False, default="", allow_blank=True)
        is_split_measurement = serializers.BooleanField(label=_("是否启动自动分表逻辑"), required=False, default=True)

        def validate(self, attrs):
            ValidateCustomTsGroupName().request(name=attrs["name"], bk_biz_id=attrs["bk_biz_id"])
            ValidateCustomTsGroupLabel().request(data_label=attrs["data_label"], bk_biz_id=attrs["bk_biz_id"])
            return attrs

    def data_name(self, bk_biz_id, ts_name):
        return f"{bk_biz_id}_{self.CUSTOM_TS_NAME}_{ts_name}"

    def table_id(self, bk_biz_id, data_id):
        database_name = f"{bk_biz_id}_{self.CUSTOM_TS_NAME}_{data_id}"
        return "{}.{}".format(database_name, "base")

    @staticmethod
    def get_data_id(bk_biz_id: int, data_name: str, operator: str, space_uid: str | None = None):
        try:
            data_id_info = api.metadata.get_data_id({"data_name": data_name, "with_rt_info": False})
        except BKAPIError:
            param = {
                "bk_biz_id": bk_biz_id,
                "data_name": data_name,
                "etl_config": ETL_CONFIG.CUSTOM_TS,
                "operator": operator,
                "data_description": data_name,
                "type_label": DataTypeLabel.TIME_SERIES,
                "source_label": DataSourceLabel.CUSTOM,
                "option": {"inject_local_time": True},
            }
            if space_uid:
                param.update(space_uid=space_uid)
            data_id_info = api.metadata.create_data_id(param)
        else:
            raise CustomValidationNameError(
                data=data_id_info["bk_data_id"], msg=_("数据源名称[{}]已存在").format(data_name)
            )
        bk_data_id = data_id_info["bk_data_id"]
        return bk_data_id

    @staticmethod
    def get_space_uid(bk_biz_id):
        """
        获取空间uid
        :param bk_biz_id:
        :return:
        """
        if bk_biz_id > 0:
            space_uid = f"{SpaceTypeEnum.BKCC.value}__{bk_biz_id}"
        else:
            space_data = api.metadata.get_space_detail({"id": abs(bk_biz_id)})
            space_uid = space_data.get("space_uid", "")
        return space_uid

    @atomic()
    def perform_request(self, validated_request_data):
        # 如果是平台级，则ts_group 及对应表的业务id为0
        # 当前业务为关联的平台级业务id，内置到data_id的data_name里面
        # data_id有个业务归属，而对应的table可以在各业务下使用
        input_bk_biz_id = 0 if validated_request_data["is_platform"] else validated_request_data["bk_biz_id"]
        operator = get_request_username() or get_admin_username(bk_tenant_id=get_request_tenant_id())

        # 当前业务
        data_name = self.data_name(validated_request_data["bk_biz_id"], validated_request_data["name"])
        # 如果 bk_biz_id 为 0，意味着是全局业务配置，这种情况不需要空间
        space_uid = (
            None
            if validated_request_data["bk_biz_id"] == 0
            else self.get_space_uid(int(validated_request_data["bk_biz_id"]))
        )
        try:
            # 保证 data id 已存在
            bk_data_id = self.get_data_id(
                bk_biz_id=validated_request_data["bk_biz_id"],
                data_name=data_name,
                operator=operator,
                space_uid=space_uid,
            )
        except CustomValidationNameError as e:
            # dataid 已存在，判定 ts 是否存在：
            bk_data_id = e.data
            if api.metadata.query_time_series_group(
                time_series_group_name=validated_request_data["name"], bk_biz_id=input_bk_biz_id
            ):
                # ts group 已存在，不需要再额外创建
                raise CustomValidationNameError(msg=_("数据源名称[{}]已存在").format(data_name))

        # data_id 存在，但 ts group 不存在，继续执行
        # 2. 调用接口创建 time_series_group
        params = {
            "operator": operator,
            "bk_data_id": bk_data_id,
            # 平台级接入，ts_group 业务id对应为0
            "bk_biz_id": input_bk_biz_id,
            "time_series_group_name": validated_request_data["name"],
            "label": validated_request_data["scenario"],
            "metric_info_list": validated_request_data["metric_info_list"],
            "is_split_measurement": validated_request_data["is_split_measurement"],
            "data_label": validated_request_data["data_label"],
        }
        if validated_request_data["table_id"]:
            params["table_id"] = validated_request_data["table_id"]
        group_info = api.metadata.create_time_series_group(params)

        CustomTSTable.objects.create(
            bk_tenant_id=get_request_tenant_id(),
            bk_biz_id=validated_request_data["bk_biz_id"],
            time_series_group_id=group_info["time_series_group_id"],
            scenario=group_info["label"],
            name=group_info["time_series_group_name"],
            bk_data_id=group_info["bk_data_id"],
            table_id=group_info["table_id"],
            is_platform=validated_request_data["is_platform"],
            data_label=validated_request_data["data_label"],
            protocol=validated_request_data["protocol"],
            desc=validated_request_data["desc"],
        )
        return {"time_series_group_id": group_info["time_series_group_id"], "bk_data_id": group_info["bk_data_id"]}


class ModifyCustomTimeSeries(Resource):
    """
    修改自定义时序
    注: esb 开放接口，需要维持入参出参一致性
    """

    class RequestSerializer(BaseCustomTSTableSerializer):
        name = serializers.CharField(label=_("名称"), required=False, max_length=128)
        is_platform = serializers.BooleanField(required=False, label=_("平台级"))
        data_label = serializers.CharField(label=_("数据标签"), required=False)
        desc = serializers.CharField(label=_("说明"), required=False, allow_blank=True)
        auto_discover = serializers.BooleanField(required=False, label=_("自动发现"))

        class MetricListSerializer(serializers.Serializer):
            class FieldSerializer(serializers.Serializer):
                unit = serializers.CharField(label=_("字段单位"), required=True, allow_blank=True)
                name = serializers.CharField(label=_("字段名"), required=True)
                description = serializers.CharField(label=_("字段描述"), required=True, allow_blank=True)
                monitor_type = serializers.CharField(label=_("字段类型，指标或维度"), required=True)

            fields = FieldSerializer(label=_("字段信息"), required=True, many=True)

        # 向前兼容字段，后续页面不再使用
        metric_json = serializers.ListField(label=_("指标配置"), child=MetricListSerializer(), required=False)

        def validate(self, attrs):
            attrs = super().validate(attrs)
            if attrs.get("name"):
                ValidateCustomTsGroupName().request(
                    name=attrs["name"], bk_biz_id=attrs["bk_biz_id"], time_series_group_id=attrs["time_series_group_id"]
                )
            if attrs.get("data_label"):
                ValidateCustomTsGroupLabel().request(
                    data_label=attrs["data_label"],
                    bk_biz_id=attrs["bk_biz_id"],
                    time_series_group_id=attrs["time_series_group_id"],
                )
            return attrs

    def update_fields(self, table: CustomTSTable, params: dict):
        """
        更新自定义时序字段信息
        """
        if not params.get("metric_json"):
            return

        # 组装字段信息
        metric_map: dict[tuple[str, str], dict[str, Any]] = {}
        dimension_map: dict[str, dict[str, Any]] = {}
        for field_dict in params["metric_json"][0]["fields"]:
            if field_dict["monitor_type"] == CustomTSMetricType.METRIC:
                metric_map[(DEFAULT_FIELD_SCOPE, field_dict["name"])] = {
                    "alias": field_dict["description"],
                    "unit": field_dict["unit"],
                }
            else:
                dimension_map[field_dict["name"]] = {
                    "alias": field_dict["description"],
                }

        time_series_group_id: int = params["time_series_group_id"]
        converter = ScopeQueryConverter(time_series_group_id)
        scope_objs: list[ScopeQueryResponseDTO] = converter.query_time_series_scope()
        field_modify_service = FieldsModifyService(time_series_group_id=time_series_group_id)
        default_scope_id: int | None = None
        for scope_obj in scope_objs:
            if scope_obj.name == UNGROUP_SCOPE_NAME:
                default_scope_id = scope_obj.id
            # 更新和删除指标
            for metric_obj in scope_obj.metric_list:
                if metric_obj.field_scope != DEFAULT_FIELD_SCOPE:
                    continue
                update_config = metric_map.pop((DEFAULT_FIELD_SCOPE, metric_obj.name), None)
                if update_config:
                    metric_config = asdict(metric_obj.config)
                    metric_config.update(update_config)
                    field_modify_service.add_metric(
                        ModifyMetric(
                            id=metric_obj.id, scope_id=scope_obj.id, config=ModifyMetricConfig.from_dict(metric_config)
                        )
                    )
                else:
                    field_modify_service.delete_metric(ModifyMetric(id=metric_obj.id, scope_id=scope_obj.id))
            # 更新和删除维度
            for dimension_name, config_obj in scope_obj.dimension_config.items():
                update_config = dimension_map.get(dimension_name)
                if update_config:
                    dimension_config = asdict(config_obj)
                    dimension_config.update(update_config)
                    field_modify_service.add_dimension(
                        ModifyDimension(
                            scope_id=scope_obj.id,
                            name=dimension_name,
                            config=ModifyDimensionConfig.from_dict(dimension_config),
                        )
                    )
                else:
                    field_modify_service.delete_dimension(ModifyDimension(scope_id=scope_obj.id, name=dimension_name))
            # 新增维度
            for dimension_name, config in dimension_map.items():
                if dimension_name not in scope_obj.dimension_config:
                    field_modify_service.add_dimension(
                        ModifyDimension(
                            scope_id=scope_obj.id,
                            name=dimension_name,
                            config=ModifyDimensionConfig.from_dict(config),
                        )
                    )

        # 新增指标
        if metric_map and default_scope_id:
            for (field_scope, metric_name), metric_config in metric_map.items():
                field_modify_service.add_metric(
                    ModifyMetric(
                        id=None,
                        name=metric_name,
                        scope_id=default_scope_id,
                        config=ModifyMetricConfig.from_dict(metric_config),
                    )
                )
        field_modify_service.apply_change()

    def perform_request(self, params: dict):
        bk_biz_id: int = params["bk_biz_id"]
        time_series_group_id: int = params["time_series_group_id"]
        ts_table = CustomTSTable.objects.get(
            bk_biz_id=bk_biz_id,
            time_series_group_id=time_series_group_id,
        )

        # 更新自定义时序表信息
        update_fields = ["name", "is_platform", "data_label", "desc", "auto_discover"]
        for field in update_fields:
            if field in params:
                setattr(ts_table, field, params[field])
        ts_table.save()

        # 更新自定义时序字段信息
        self.update_fields(ts_table, params)

        # 更新metadata指标信息
        ts_table.save_to_metadata()

        return resource.custom_report.custom_time_series_detail(
            bk_biz_id=bk_biz_id, time_series_group_id=time_series_group_id
        )


class DeleteCustomTimeSeries(Resource):
    """
    删除自定义时序
    注: esb 开放接口，需要维持入参出参一致性
    """

    class RequestSerializer(BaseCustomTSTableSerializer):
        pass

    def perform_request(self, params: dict):
        ts_table = CustomTSTable.objects.get(
            bk_biz_id=params["bk_biz_id"], time_series_group_id=params["time_series_group_id"]
        )
        operator = get_request_username()
        api.metadata.delete_time_series_group(
            {"operator": operator, "time_series_group_id": ts_table.time_series_group_id}
        )
        ts_table.delete()
        return {"time_series_group_id": params["time_series_group_id"]}


class CustomTimeSeriesList(Resource):
    """
    自定义时序列表
    注: esb 开放接口，需要维持入参出参一致性
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label=_("业务 ID"), default=0)
        search_key = serializers.CharField(label=_("名称"), required=False)
        page_size = serializers.IntegerField(label=_("获取的条数"), default=10)
        page = serializers.IntegerField(label=_("页数"), default=1)
        # 新增参数用以判定是否需要查询平台级 dataid
        is_platform = serializers.BooleanField(label=_("是否平台级"), required=False)

    def perform_request(self, validated_request_data):
        queryset = CustomTSTable.objects.filter(bk_tenant_id=get_request_tenant_id()).order_by("-update_time")
        context = {"request_bk_biz_id": validated_request_data["bk_biz_id"]}
        # 区分本空间 和 全平台
        if validated_request_data.get("is_platform"):
            # 只查全平台, 不关注业务
            queryset = queryset.filter(is_platform=True)

        elif validated_request_data.get("bk_biz_id"):
            # 非全平台，查当前业务(0表示全部业务)
            queryset = queryset.filter(bk_biz_id=validated_request_data["bk_biz_id"])

        if validated_request_data.get("search_key"):
            search_key = validated_request_data["search_key"]
            conditions = models.Q(name__contains=search_key)
            try:
                search_key = int(search_key)
            except ValueError:
                pass
            else:
                conditions = conditions | models.Q(pk=search_key) | models.Q(bk_data_id=search_key)
            queryset = queryset.filter(conditions)
        paginator = Paginator(queryset, validated_request_data["page_size"])
        serializer = CustomTSTableSerializer(paginator.page(validated_request_data["page"]), many=True, context=context)
        tables = serializer.data

        table_ids = [table["table_id"] for table in tables]
        strategy_count_mapping = count_rt_bound_strategies(
            table_ids,
            data_source_label=DataSourceLabel.CUSTOM,
            data_type_label=DataTypeLabel.TIME_SERIES,
            bk_biz_id=validated_request_data.get("bk_biz_id"),
        )

        label_display_dict = get_label_display_dict()
        for table in tables:
            table["scenario_display"] = label_display_dict.get(table["scenario"], [table["scenario"]])
            table["related_strategy_count"] = strategy_count_mapping.get(table["table_id"], 0)
        return {
            "list": tables,
            "total": queryset.count(),
        }


class CustomTimeSeriesDetail(Resource):
    """
    自定义时序详情
    注: esb 开放接口，需要维持入参出参一致性
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label=_("业务 ID"))
        time_series_group_id = serializers.IntegerField(label=_("自定义时序 ID"))
        model_only = serializers.BooleanField(label=_("是否只查询自定义时序表信息"), default=False)
        with_target = serializers.BooleanField(label=_("是否查询 target"), default=False)
        with_metrics = serializers.BooleanField(label=_("是否查询指标信息"), default=True)
        empty_if_not_found = serializers.BooleanField(
            label=_("是否返回空数据"),
            required=False,
            default=False,
            help_text=_("如果自定义时序表不存在，是否返回空数据"),
        )

    def perform_request(self, params: dict[str, Any]):
        bk_biz_id: int = params["bk_biz_id"]
        time_series_group_id: int = params["time_series_group_id"]
        # 获取自定义时序表信息
        config: CustomTSTable | None = CustomTSTable.objects.filter(
            bk_biz_id=bk_biz_id, pk=time_series_group_id
        ).first()
        if not config:
            # 如果自定义时序表不存在，则返回空数据
            if params.get("empty_if_not_found"):
                return {}
            raise ValidationError(f"custom time series table not found, time_series_group_id: {time_series_group_id}")

        # 如果是平台自定义时序，则需要校验业务是否匹配
        if not config.is_platform and config.bk_biz_id != bk_biz_id:
            raise ValidationError(f"custom time series not found, bk_biz_id: {bk_biz_id}")

        # 序列化自定义时序表信息
        data = CustomTSTableSerializer(config, context={"request_bk_biz_id": bk_biz_id}).data

        # 如果只查询自定义时序表信息，则直接返回
        if params.get("model_only"):
            return data

        data["scenario_display"] = get_label_display_dict().get(data["scenario"], [data["scenario"]])
        data["access_token"] = config.token

        # 如果需要查询指标信息，则将指标信息写入到metric_json中
        data["metric_json"] = [{"fields": list(config.get_metrics().values())}] if params.get("with_metrics") else []
        # 新增查询target参数，自定义指标详情页面不需要target，默认不查询
        data["target"] = config.query_target(bk_biz_id=bk_biz_id) if params.get("with_target") else []

        return data


class GetCustomTsFields(CustomTSScopeMixin, Resource):
    """
    获取自定义指标字段
    """

    class RequestSerializer(BaseCustomTSSerializer):
        pass

    class ResponseSerializer(serializers.Serializer):
        class BaseFieldSerializer(serializers.Serializer):
            type = serializers.ChoiceField(label=_("字段类型"), choices=CustomTSMetricType.choices())
            scope = BasicScopeSerializer(label=_("分组信息"))
            name = serializers.CharField(label=_("字段名称"))

        class DimensionSerializer(BaseFieldSerializer):
            config = DimensionConfigResponseSerializer(label=_("维度配置"))

        class MetricSerializer(BaseFieldSerializer):
            id = serializers.IntegerField(label=_("指标 ID"))
            movable = serializers.BooleanField(label=_("是否可移动"))
            field_scope = serializers.CharField(label=_("数据分组"))
            config = MetricConfigResponseSerializer(label=_("指标配置"))
            dimensions = serializers.ListField(label=_("维度列表"), child=serializers.CharField())
            create_time = serializers.FloatField(label=_("创建时间"), allow_null=True)
            update_time = serializers.FloatField(label=_("更新时间"), allow_null=True)

        dimensions = serializers.ListField(label=_("维度列表"), child=DimensionSerializer())
        metrics = serializers.ListField(label=_("指标列表"), child=MetricSerializer())

    def get_movable(self, metric_obj: ScopeQueryMetricResponseDTO, params: dict) -> bool:
        return metric_obj.field_scope == DEFAULT_FIELD_SCOPE

    def perform_request(self, params: dict):
        time_series_group_id: int = params["time_series_group_id"]
        converter = ScopeQueryConverter(time_series_group_id)
        scope_objs: list[ScopeQueryResponseDTO] = converter.query_time_series_scope(
            **self.get_query_scope_filters(params)
        )
        scope_objs = converter.filter_disabled_metric(scope_objs)

        dimensions: list[dict[str, Any]] = []
        metrics: list[dict[str, Any]] = []
        for scope_obj in scope_objs:
            for metric_obj in scope_obj.metric_list:
                metric_dict: dict[str, Any] = {
                    "scope": {"id": scope_obj.id, "name": scope_obj.name},
                    "type": CustomTSMetricType.METRIC,
                    "movable": self.get_movable(metric_obj, params),
                }
                metric_dict.update(asdict(metric_obj))
                metrics.append(metric_dict)
            for dimension_name, dimension_obj in scope_obj.dimension_config.items():
                dimensions.append(
                    {
                        "scope": {"id": scope_obj.id, "name": scope_obj.name},
                        "name": dimension_name,
                        "type": CustomTSMetricType.DIMENSION,
                        "config": asdict(dimension_obj),
                    }
                )
        return {"dimensions": dimensions, "metrics": metrics}


class ModifyCustomTsFields(CustomTSScopeMixin, Resource):
    """
    修改自定义指标字段
    """

    class RequestSerializer(BaseCustomTSSerializer):
        class DeleteFieldSerializer(serializers.Serializer):
            type = serializers.ChoiceField(label=_("字段类型"), choices=CustomTSMetricType.choices())
            scope = BasicScopeSerializer(label=_("分组信息"))

            class DeleteMetricSerializer(serializers.Serializer):
                id = serializers.IntegerField(label=_("指标 ID"))

            class DeleteDimensionSerializer(serializers.Serializer):
                name = serializers.CharField(label=_("维度名称"))

            def to_internal_value(self, data: dict[str, Any]) -> dict[str, Any]:
                validated_data = super().to_internal_value(data)
                if validated_data["type"] == CustomTSMetricType.DIMENSION:
                    s = self.DeleteDimensionSerializer(data=data)
                else:
                    s = self.DeleteMetricSerializer(data=data)
                s.is_valid(raise_exception=True)
                validated_data.update(s.validated_data)
                return validated_data

        class CUFieldSerializer(serializers.Serializer):
            type = serializers.ChoiceField(label=_("字段类型"), choices=CustomTSMetricType.choices())
            scope = BasicScopeSerializer(label=_("分组信息"))

            class CMetricSerializer(serializers.Serializer):
                id = serializers.IntegerField(label=_("指标 ID"), allow_null=True, default=None)
                name = serializers.CharField(label=_("指标名称"))
                config = MetricConfigRequestSerializer(label=_("指标配置"), default={})
                dimensions = serializers.ListField(label=_("维度列表"), child=serializers.CharField(), required=False)

            class UMetricSerializer(serializers.Serializer):
                id = serializers.IntegerField(label=_("指标 ID"))
                config = MetricConfigRequestSerializer(label=_("指标配置"), default={})
                dimensions = serializers.ListField(label=_("维度列表"), child=serializers.CharField(), required=False)

            class CUDimensionSerializer(serializers.Serializer):
                config = DimensionConfigRequestSerializer(label=_("维度配置"), default={})
                name = serializers.CharField(label=_("维度名称"))

            def to_internal_value(self, data: dict[str, Any]) -> dict[str, Any]:
                validated_data = super().to_internal_value(data)
                if validated_data["type"] == CustomTSMetricType.DIMENSION:
                    s = self.CUDimensionSerializer(data=data)
                else:
                    if data.get("id"):
                        s = self.UMetricSerializer(data=data)
                    else:
                        s = self.CMetricSerializer(data=data)
                s.is_valid(raise_exception=True)
                validated_data.update(s.validated_data)
                return validated_data

        update_fields = serializers.ListField(label=_("更新字段列表"), child=CUFieldSerializer(), default=list)
        delete_fields = serializers.ListField(label=_("删除字段列表"), child=DeleteFieldSerializer(), default=list)

    def perform_request(self, params: dict[str, Any]):
        field_modify_service = FieldsModifyService(time_series_group_id=params["time_series_group_id"])
        for field_dict in params["update_fields"]:
            modify_dict: dict[str, Any] = {
                "scope_id": field_dict["scope"]["id"],
            }
            if field_dict["type"] == CustomTSMetricType.METRIC:
                modify_dict.update(
                    {
                        "config": ModifyMetricConfig(**field_dict["config"]),
                        "id": field_dict["id"],
                        "field_scope": self.get_default_scope_name(params),  # 仅创建时起作用
                    }
                )
                if field_dict.get("name"):
                    modify_dict["name"] = field_dict["name"]
                if "dimensions" in field_dict:
                    modify_dict["dimensions"] = field_dict["dimensions"]
                field_modify_service.add_metric(ModifyMetric(**modify_dict))
            else:
                modify_dict.update(
                    {
                        "config": ModifyDimensionConfig(**field_dict["config"]),
                        "name": field_dict["name"],
                    }
                )
                field_modify_service.add_dimension(ModifyDimension(**modify_dict))

        for field_dict in params["delete_fields"]:
            modify_dict: dict[str, Any] = {
                "scope_id": field_dict["scope"]["id"],
            }
            if field_dict["type"] == CustomTSMetricType.METRIC:
                modify_dict["id"] = field_dict["id"]
                field_modify_service.delete_metric(ModifyMetric(**modify_dict))
            else:
                modify_dict["name"] = field_dict["name"]
                field_modify_service.delete_dimension(ModifyDimension(**modify_dict))
        field_modify_service.apply_change()


class AddCustomMetricResource(Resource):
    """
    添加自定义指标
    1. 由于获取指标列表存在过滤失效问题，先确认该指标是否存在
    2. 请求metadata api添加该指标
    3. 新增至指标缓存，并返回metric item
    """

    class RequestSerializer(serializers.Serializer):
        metric_field = serializers.CharField(required=True, label=_("指标名"))
        result_table_id = serializers.CharField(required=True, label=_("结果表 ID"))
        bk_biz_id = serializers.IntegerField(required=True, label=_("业务 ID"))

    def perform_request(self, params: dict):
        queryset = CustomTSTable.objects.filter(bk_biz_id=params["bk_biz_id"])

        # 查询该任务是否已有执行任务
        table = queryset.filter(table_id__startswith=params["result_table_id"])
        if not table.exists():
            table = queryset.filter(data_label=params["result_table_id"])
            if not table.exists():
                raise ValidationError(f"结果表或datalabel({params['result_table_id']})不存在")

        # 手动添加的自定义指标metric_md5特殊处理为0
        filter_params = {
            "data_source_label": DataSourceLabel.CUSTOM,
            "data_type_label": DataTypeLabel.TIME_SERIES,
            "bk_biz_id": params["bk_biz_id"],
            "result_table_id": table.first().table_id,
            "bk_tenant_id": get_request_tenant_id(),
        }
        metric_list = MetricListCache.objects.filter(**filter_params)
        if metric_list.filter(metric_field=params["metric_field"]).exists():
            raise ValidationError(f"指标({params['result_table_id']}.{params['metric_field']})已存在")
        create_params = {
            "metric_field": params["metric_field"],
            "metric_field_name": params["metric_field"],
            "metric_md5": "0",
            "data_label": table.first().data_label,
            **filter_params,
        }
        if metric_list.first():
            extra_params = {
                "result_table_label_name": metric_list.first().result_table_label_name,
                "result_table_name": metric_list.first().result_table_name,
                "result_table_label": metric_list.first().result_table_label,
                "related_name": metric_list.first().related_name,
                "related_id": metric_list.first().related_id,
                "extend_fields": metric_list.first().extend_fields,
            }
        else:
            extra_params = {
                "result_table_label_name": table.first().scenario,
                "result_table_name": table.first().name,
                "result_table_label": table.first().scenario,
                "related_name": table.first().name,
                "related_id": table.first().time_series_group_id,
                "extend_fields": {"bk_data_id": table.first().bk_data_id},
            }
        create_params.update(extra_params)
        new_metric = MetricListCache(**create_params)
        new_metric.save()
        return GetMetricListV2Resource.get_metric_list(
            params["bk_biz_id"], MetricListCache.objects.filter(id=new_metric.id)
        )


class CustomTsGroupingRuleList(CustomTSScopeMixin, Resource):
    """
    获取自定义指标分组规则列表
    """

    class RequestSerializer(BaseCustomTSSerializer):
        pass

    many_response_data = True

    class ResponseSerializer(CustomTSScopeResponseSerializer):
        dimension_config = None

    def perform_request(self, params: dict):
        converter = ScopeQueryConverter(params["time_series_group_id"])
        scope_objs: list[ScopeQueryResponseDTO] = converter.query_time_series_scope(
            **self.get_query_scope_filters(params)
        )
        scope_objs = converter.filter_disabled_metric(scope_objs)
        result: list[dict[str, Any]] = [asdict(scope_obj) for scope_obj in scope_objs]
        result.sort(key=lambda x: (x["name"] != UNGROUP_SCOPE_NAME, x["name"].lower()))
        return result


class CreateOrUpdateGroupingRule(CustomTSScopeMixin, Resource):
    """
    更新自定义指标分组规则
    """

    class RequestSerializer(BaseCustomTSSerializer, CustomTSScopeRequestSerializer):
        pass

    class ResponseSerializer(CustomTSScopeResponseSerializer):
        pass

    def _merge_scope_ids(self, params: dict, scope_id: int) -> dict:
        """合并 scope_ids 参数，避免冲突"""
        query_filters = self.get_query_scope_filters(params)
        scope_ids = query_filters.get("scope_ids", [])
        if scope_id not in scope_ids:
            scope_ids.append(scope_id)
        query_filters["scope_ids"] = scope_ids
        return query_filters

    def perform_request(self, params: dict):
        scope_request_obj = ScopeCURequestDTO(
            id=params.get("scope_id"),
            name=params["name"],
            auto_rules=params["auto_rules"],
        )
        time_series_group_id = params["time_series_group_id"]
        scope_converter = ScopeQueryConverter(time_series_group_id)
        scope_cu_obj = scope_converter.create_or_update_time_series_scope([scope_request_obj])[0]

        # 找出默认分组
        default_scope_obj = scope_converter.get_default_scope_obj(
            default_scope_name=self.get_default_scope_name(params), include_metrics=False
        )

        # 查询分组信息
        scope_obj = scope_converter.query_time_series_scope(**self._merge_scope_ids(params, scope_cu_obj.id))[0]

        origin_metric_ids: set[int] = {metric_obj.id for metric_obj in scope_obj.metric_list}
        update_metric_ids: set[int] = {metric_dict["id"] for metric_dict in params["metric_list"]}
        remove_metric_ids: set[int] = origin_metric_ids - update_metric_ids
        update_metric_ids: set[int] = update_metric_ids - origin_metric_ids

        field_modify_service = FieldsModifyService(time_series_group_id=params["time_series_group_id"])
        for metric_id in remove_metric_ids:
            field_modify_service.add_metric(ModifyMetric(id=metric_id, scope_id=default_scope_obj.id))
        for metric_id in update_metric_ids:
            field_modify_service.add_metric(ModifyMetric(id=metric_id, scope_id=scope_obj.id))
        field_modify_service.apply_change()

        updated_scope_obj: ScopeQueryResponseDTO = scope_converter.filter_disabled_metric(
            scope_converter.query_time_series_scope(**self._merge_scope_ids(params, scope_obj.id))
        )[0]
        return asdict(updated_scope_obj)


class PreviewGroupingRule(CustomTSScopeMixin, Resource):
    """
    预览自定义指标分组
    """

    class RequestSerializer(BaseCustomTSSerializer):
        auto_rules = serializers.ListField(label=_("自动分组的匹配规则列表"), child=serializers.CharField(), default=[])

    def perform_request(self, params: dict):
        # 预编译正则表达式
        rule_compile_map: dict[str, re.Pattern] = {rule: re.compile(rule) for rule in params["auto_rules"]}
        converter = ScopeQueryConverter(params["time_series_group_id"])
        default_scope_obj = converter.get_default_scope_obj(
            default_scope_name=self.get_default_scope_name(params), include_metrics=True
        )
        default_scope_obj = converter.filter_disabled_metric([default_scope_obj])[0]
        auto_metrics: dict[str, list[str]] = defaultdict(list)
        for metric_obj in default_scope_obj.metric_list:
            metric_name: str = metric_obj.name
            for rule, pattern in rule_compile_map.items():
                if pattern.match(metric_name):
                    auto_metrics[rule].append(metric_name)

        return {
            "auto_metrics": [
                {
                    "auto_rule": auto_rule,
                    "metrics": metrics,
                }
                for auto_rule, metrics in auto_metrics.items()
            ],
        }


class DeleteGroupingRule(Resource):
    """
    删除自定义指标分组规则
    """

    class RequestSerializer(BaseCustomTSSerializer):
        name = serializers.CharField(label=_("分组规则名称"))

    def perform_request(self, params: dict):
        api.metadata.delete_time_series_scope(
            group_id=params["time_series_group_id"], scopes=[{"scope_name": params["name"]}]
        )


# 破坏性变更，计划移除
class UpdateGroupingRuleOrder(Resource):
    """
    更新自定义指标分组规则排序
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label=_("业务 ID"))
        time_series_group_id = serializers.IntegerField(required=True, label=_("自定义时序 ID"))
        group_names = serializers.ListField(required=True, label=_("分组规则名称列表"))

    def perform_request(self, params: dict):
        return


class ImportCustomTimeSeriesFields(CustomTSScopeMixin, Resource):
    """
    导入自定义时序字段信息
    """

    class RequestSerializer(BaseCustomTSSerializer):
        scopes = serializers.ListField(label=_("分组列表"), child=ImportExportScopeSerializer())

    def is_default_field_scope(self, field_scope: str, params: dict) -> bool:
        return field_scope == DEFAULT_FIELD_SCOPE

    def perform_request(self, params: dict[str, Any]):
        time_series_group_id: int = params["time_series_group_id"]
        converter = ScopeQueryConverter(time_series_group_id=time_series_group_id)
        origin_scopes = converter.query_time_series_scope(**self.get_query_scope_filters(params))

        # 构建已有数据的数据结构
        scope_name_id_map: dict[str, int] = {}
        metric_obj_map: dict[tuple[str, str], ScopeQueryMetricResponseDTO] = {}
        metric_scope_id_map: dict[tuple[str, str], int] = {}
        for scope_obj in origin_scopes:
            scope_name_id_map[scope_obj.name] = scope_obj.id
            for metric_obj in scope_obj.metric_list:
                map_key = (metric_obj.field_scope, metric_obj.name)
                metric_obj_map[map_key] = metric_obj
                metric_scope_id_map[map_key] = scope_obj.id

        # 导入分组
        scope_request_dto_list: list[ScopeCURequestDTO] = []
        for scope_dict in params["scopes"]:
            scope_name = scope_dict["name"]
            scope_id = scope_name_id_map.get(scope_name)
            scope_cu_obj = ScopeCURequestDTO(
                id=scope_id,
                name=scope_name,
                auto_rules=scope_dict["auto_rules"],
            )
            scope_request_dto_list.append(scope_cu_obj)
        create_scope_objs = converter.create_or_update_time_series_scope(scope_request_dto_list)

        # 补充新创建的分组数据结构
        for scope_obj in create_scope_objs:
            scope_name_id_map[scope_obj.name] = scope_obj.id

        # 字段修改
        field_modify_service = FieldsModifyService(time_series_group_id=time_series_group_id)
        for scope_dict in params["scopes"]:
            scope_name = scope_dict["name"]
            scope_id = scope_name_id_map[scope_name]
            for metric_dict in scope_dict["metric_list"]:
                field_scope = metric_dict["field_scope"]
                metric_name = metric_dict["name"]
                map_key = (field_scope, metric_name)
                metric_obj = metric_obj_map.get(map_key)
                modify_scope_id = scope_id
                # 如果 field_scope 不是 default 的话不支持新建
                if not self.is_default_field_scope(field_scope, params):
                    if not metric_obj:
                        continue
                    modify_scope_id = metric_scope_id_map[map_key]
                metric_id: int | None = metric_obj and metric_obj.id
                field_modify_service.add_metric(
                    ModifyMetric(
                        id=metric_id,
                        scope_id=modify_scope_id,
                        config=ModifyMetricConfig.from_dict(metric_dict["config"]),
                        name=metric_name,
                        dimensions=metric_dict["dimensions"],
                        field_scope=field_scope,
                    )
                )
            for dimension_name, config_dict in scope_dict["dimension_config"].items():
                field_modify_service.add_dimension(
                    ModifyDimension(
                        scope_id=scope_id,
                        name=dimension_name,
                        config=ModifyDimensionConfig.from_dict(config_dict),
                    )
                )
        field_modify_service.apply_change()


class ExportCustomTimeSeriesFields(CustomTSScopeMixin, Resource):
    """
    导出自定义时序字段信息
    """

    class RequestSerializer(BaseCustomTSSerializer):
        pass

    class ResponseSerializer(serializers.Serializer):
        scopes = serializers.ListField(label=_("分组列表"), child=ImportExportScopeSerializer())

    def perform_request(self, params: dict):
        time_series_group_id: int = params["time_series_group_id"]
        # 获取自定义时序表
        converter = ScopeQueryConverter(time_series_group_id=time_series_group_id)
        scope_objs = converter.query_time_series_scope(**self.get_query_scope_filters(params))
        converter.filter_disabled_metric(scope_objs)
        return {
            "scopes": [asdict(scope_obj) for scope_obj in scope_objs],
        }


# 最后实现
class GetCustomTimeSeriesLatestDataByFields(Resource):
    """
    查询自定义时序数据最新的一条数据
    """

    class RequestSerializer(serializers.Serializer):
        result_table_id = serializers.CharField(required=True, label="结果表ID")
        metric_list = serializers.ListField(label=_("指标列表"), child=BasicMetricRequestSerializer(), default=[])

    def perform_request(self, validated_request_data):
        # TODO: 修改响应格式
        result_table_id = validated_request_data["result_table_id"]
        fields_list = [str(i) for i in validated_request_data["metric_list"]]

        result = {}
        field_values, latest_time = self.get_latest_data(table_id=result_table_id, fields_list=fields_list)
        result["fields_value"] = field_values
        result["last_time"] = latest_time
        result["table_id"] = result_table_id
        return result

    @classmethod
    def get_latest_data(cls, table_id, fields_list):
        if not fields_list:
            return {}, None

        now_timestamp = int(time.time())
        # unify query 已不支持该接口，推荐使用 query/ts/info/series 接口
        data = api.unify_query.query_data_by_table(
            table_id=table_id,
            keys=fields_list,
            start_time=now_timestamp - 300,
            end_time=now_timestamp,
            limit=1,
            slimit=0,
        )

        result = {}
        latest_time = ""

        if data["series"]:
            for row in data["series"]:
                for point in row["values"]:
                    for key, value in zip(row["columns"], point):
                        if key == "time" or key in result or value is None:
                            continue

                        if key in ["value", "metric_value"] and row["metric_name"]:
                            result[row["metric_name"]] = value
                            continue

                        result[key] = value

                for key, value in zip(row["group_keys"], row["group_values"]):
                    if key in result or value is None:
                        continue
                    result[key] = value

                if row["values"]:
                    time_value = row["values"][-1][0]
                    if latest_time < time_value:
                        latest_time = time_value

        if latest_time:
            latest_time = arrow.get(latest_time).timestamp
        else:
            latest_time = None
        return result, latest_time


# 计划移除
class ModifyCustomTimeSeriesDesc(Resource):
    """
    修改自定义时序描述信息
    """

    class RequestSerializer(serializers.Serializer):
        time_series_group_id = serializers.IntegerField(required=True, label="自定义时序ID")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        desc = serializers.CharField(max_length=1024, default="", label="描述信息")

    class ResponseSerializer(serializers.ModelSerializer):
        class Meta:
            model = CustomTSTable
            fields = "__all__"

    def perform_request(self, validated_request_data):
        ts_table = CustomTSTable.objects.filter(
            bk_biz_id=validated_request_data["bk_biz_id"],
            time_series_group_id=validated_request_data["time_series_group_id"],
        ).first()
        if not ts_table:
            raise ValidationError(
                "custom time series table not found, "
                f"time_series_group_id: {validated_request_data['time_series_group_id']}"
            )

        ts_table.desc = validated_request_data["desc"]
        ts_table.save()
        return ts_table


# 等前端自定义指标适配 APM 时处理，计划移除
class ModifyCustomTsGroupingRuleList(Resource):
    """
    修改全量自定义指标分组规则列表
    """

    class RequestSerializer(serializers.Serializer):
        # 计划移除
        class CustomTSGroupingRuleSerializer(serializers.Serializer):
            name = serializers.CharField(label=_("分组名称"), required=True)
            manual_list = serializers.ListField(label=_("手动分组的指标列表"), default=list)
            auto_rules = serializers.ListField(label=_("自动分组的匹配规则列表"), default=list)

            def validate(self, attrs: dict) -> dict:
                attrs["name"] = attrs["name"].strip()
                return attrs

        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        time_series_group_id = serializers.IntegerField(required=True, label="自定义时序ID")
        group_list = serializers.ListField(label="分组列表", child=CustomTSGroupingRuleSerializer(), default=[])

    def perform_request(self, validated_request_data):
        return resource.custom_report.custom_ts_grouping_rule_list(
            time_series_group_id=validated_request_data["time_series_group_id"]
        )
